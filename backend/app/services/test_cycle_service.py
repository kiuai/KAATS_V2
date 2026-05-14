"""Test cycle service — system-scoped cycles, bulk assign, submit result, execute-all."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_cycle import TestAssignment, TestCycle, TestExecution
from app.models.enums import (
    TestAssignmentStatus,
    TestCycleStatus,
    TestOutcome,
    UserRoleEnum,
)
from app.schemas.test_cycle import (
    TestAssignmentCreate,
    TestAssignmentRead,
    TestAssignmentUpdate,
    TestCycleCreate,
    TestCycleRead,
    TestCycleUpdate,
    TestExecutionRead,
    TestResultRead,
)

log = structlog.get_logger(__name__)

# Roles that may act as testers on assignments
_TESTER_ROLES: frozenset[str] = frozenset({
    UserRoleEnum.VALIDATION_TESTER.value,
    UserRoleEnum.QA.value,
    UserRoleEnum.VALIDATION_LEAD.value,
})


class TestCycleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Legacy execution methods (backwards compat) ───────────────────────────

    async def list_for_script(self, script_id: UUID) -> list[TestExecutionRead]:
        result = await self._db.execute(
            select(TestExecution)
            .where(TestExecution.script_id == script_id)
            .options(selectinload(TestExecution.step_results))
            .order_by(TestExecution.started_at.desc())
        )
        return [TestExecutionRead.model_validate(e) for e in result.scalars().all()]

    async def get(self, execution_id: UUID) -> TestExecutionRead:
        result = await self._db.execute(
            select(TestExecution)
            .where(TestExecution.id == execution_id)
            .options(selectinload(TestExecution.step_results))
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        return TestExecutionRead.model_validate(execution)

    async def rerun(self, execution_id: UUID) -> TestExecutionRead:
        original = await self._db.get(TestExecution, execution_id)
        if not original:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        new_execution = TestExecution(
            script_id=original.script_id,
            system_id=original.system_id,
            company_id=original.company_id,
            triggered_by=original.triggered_by,
            status="pending",
        )
        self._db.add(new_execution)
        await self._db.flush()
        return TestExecutionRead.model_validate(new_execution)

    async def delete(self, execution_id: UUID) -> None:
        execution = await self._db.get(TestExecution, execution_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        await self._db.delete(execution)
        await self._db.flush()

    # ── Test Cycles (system-scoped) ───────────────────────────────────────────

    async def list_for_system(self, system_id: UUID) -> list[dict]:
        """List cycles with progress stats (assignment counts by status)."""
        result = await self._db.execute(
            select(TestCycle)
            .where(TestCycle.system_id == system_id)
            .options(selectinload(TestCycle.assignments))
            .order_by(TestCycle.created_at.desc())
        )
        cycles = result.scalars().all()
        out: list[dict] = []
        for cycle in cycles:
            base = TestCycleRead.model_validate(cycle)
            assignments = cycle.assignments or []
            out.append({
                **base.model_dump(),
                "progress": {
                    "total": len(assignments),
                    "passed": sum(1 for a in assignments if a.status == TestAssignmentStatus.PASSED.value),
                    "failed": sum(1 for a in assignments if a.status == TestAssignmentStatus.FAILED.value),
                    "pending": sum(1 for a in assignments if a.status == TestAssignmentStatus.PENDING.value),
                    "blocked": sum(1 for a in assignments if a.status == TestAssignmentStatus.BLOCKED.value),
                },
            })
        return out

    async def create_cycle(
        self,
        system_id: UUID,
        body: TestCycleCreate,
        company_id: UUID,
        created_by: UUID,
    ) -> TestCycleRead:
        cycle = TestCycle(
            system_id=system_id,
            company_id=company_id,
            created_by=created_by,
            **body.model_dump(exclude={"system_id"}),
        )
        self._db.add(cycle)
        await self._db.flush()
        return TestCycleRead.model_validate(cycle)

    async def get_cycle_detail(self, cycle_id: UUID) -> dict:
        """Return cycle with assignments and progress summary."""
        result = await self._db.execute(
            select(TestCycle)
            .where(TestCycle.id == cycle_id)
            .options(selectinload(TestCycle.assignments))
        )
        cycle = result.scalar_one_or_none()
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test cycle not found")
        base = TestCycleRead.model_validate(cycle)
        assignments = cycle.assignments or []
        return {
            **base.model_dump(),
            "assignments": [TestAssignmentRead.model_validate(a) for a in assignments],
            "progress": {
                "total": len(assignments),
                "passed": sum(1 for a in assignments if a.status == TestAssignmentStatus.PASSED.value),
                "failed": sum(1 for a in assignments if a.status == TestAssignmentStatus.FAILED.value),
                "pending": sum(1 for a in assignments if a.status == TestAssignmentStatus.PENDING.value),
                "blocked": sum(1 for a in assignments if a.status == TestAssignmentStatus.BLOCKED.value),
                "skipped": sum(1 for a in assignments if a.status == TestAssignmentStatus.SKIPPED.value),
            },
        }

    async def update_cycle(self, cycle_id: UUID, body: TestCycleUpdate) -> TestCycleRead:
        cycle = await self._load_cycle(cycle_id)
        for field, value in body.model_dump(exclude_none=True).items():
            if hasattr(value, "value"):
                value = value.value
            setattr(cycle, field, value)
        await self._db.flush()
        return TestCycleRead.model_validate(cycle)

    async def cancel_cycle(self, cycle_id: UUID) -> TestCycleRead:
        cycle = await self._load_cycle(cycle_id)
        if cycle.status == TestCycleStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot cancel a completed cycle",
            )
        cycle.status = TestCycleStatus.ABORTED.value
        cycle.actual_end = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.flush()
        return TestCycleRead.model_validate(cycle)

    # ── Assignments ───────────────────────────────────────────────────────────

    async def bulk_assign(
        self,
        cycle_id: UUID,
        assignments_data: list[TestAssignmentCreate],
        assigned_by: UUID,
        company_id: UUID,
    ) -> list[TestAssignmentRead]:
        """
        Bulk create test assignments.
        Guards:
        - Scripts must be APPROVED.
        - Assigned users must have a tester role (VALIDATION_TESTER/QA/VALIDATION_LEAD).
        """
        from app.models.test_script import TestScript
        from app.models.role import UserRole
        from app.models.enums import TestScriptStatus

        cycle = await self._load_cycle(cycle_id)
        if cycle.status not in (
            TestCycleStatus.PLANNED.value,
            TestCycleStatus.IN_PROGRESS.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot assign to a cycle with status '{cycle.status}'",
            )

        created: list[TestAssignmentRead] = []
        for item in assignments_data:
            # Validate script is APPROVED
            script = await self._db.scalar(
                select(TestScript).where(
                    TestScript.id == item.test_script_id,
                    TestScript.status == TestScriptStatus.APPROVED.value,
                    TestScript.deleted_at.is_(None),
                )
            )
            if not script:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Script {item.test_script_id} is not APPROVED",
                )

            # Validate user has a tester role (system-level or company-level)
            tester_role = await self._db.scalar(
                select(UserRole).where(
                    UserRole.user_id == item.assigned_to,
                    UserRole.role.in_(list(_TESTER_ROLES)),
                )
            )
            if not tester_role:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"User {item.assigned_to} does not have a tester role",
                )

            assignment = TestAssignment(
                test_cycle_id=cycle_id,
                test_script_id=item.test_script_id,
                assigned_to=item.assigned_to,
                assigned_by=assigned_by,
                due_date=item.due_date,
                status=TestAssignmentStatus.PENDING.value,
            )
            self._db.add(assignment)
            created.append(assignment)

        await self._db.flush()
        return [TestAssignmentRead.model_validate(a) for a in created]

    async def list_assignments(
        self,
        cycle_id: UUID,
        current_user=None,
    ) -> list[TestAssignmentRead]:
        """
        List assignments. Testers (VALIDATION_TESTER) see only their own.
        """
        await self._load_cycle(cycle_id)

        q = select(TestAssignment).where(TestAssignment.test_cycle_id == cycle_id)

        if current_user and _is_tester_only(current_user):
            q = q.where(TestAssignment.assigned_to == current_user.user.id)

        result = await self._db.execute(q.order_by(TestAssignment.assigned_at))
        return [TestAssignmentRead.model_validate(a) for a in result.scalars().all()]

    async def update_assignment(
        self,
        cycle_id: UUID,
        assignment_id: UUID,
        body: TestAssignmentUpdate,
    ) -> TestAssignmentRead:
        assignment = await self._load_assignment(cycle_id, assignment_id)
        for field, value in body.model_dump(exclude_none=True).items():
            if hasattr(value, "value"):
                value = value.value
            setattr(assignment, field, value)
        await self._db.flush()
        return TestAssignmentRead.model_validate(assignment)

    # ── Submit result ─────────────────────────────────────────────────────────

    async def submit_result(
        self,
        cycle_id: UUID,
        assignment_id: UUID,
        outcome: str,
        actual_result: str | None,
        notes: str | None,
        executed_by: UUID,
        company_id: UUID,
        evidence_blob_paths: list[str] | None = None,
    ) -> TestResultRead:
        from app.models.test_result import TestResult

        assignment = await self._load_assignment(cycle_id, assignment_id)

        # Validate outcome
        try:
            TestOutcome(outcome)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid outcome '{outcome}'. Valid: {[o.value for o in TestOutcome]}",
            )

        result = TestResult(
            assignment_id=assignment_id,
            test_script_id=assignment.test_script_id,
            company_id=company_id,
            executed_by=executed_by,
            outcome=outcome,
            actual_result=actual_result,
            notes=notes,
        )
        self._db.add(result)

        # Update assignment status to match outcome
        outcome_to_status = {
            TestOutcome.PASSED.value: TestAssignmentStatus.PASSED.value,
            TestOutcome.FAILED.value: TestAssignmentStatus.FAILED.value,
            TestOutcome.BLOCKED.value: TestAssignmentStatus.BLOCKED.value,
            TestOutcome.SKIPPED.value: TestAssignmentStatus.SKIPPED.value,
        }
        assignment.status = outcome_to_status.get(outcome, TestAssignmentStatus.IN_PROGRESS.value)

        await self._db.flush()
        log.info(
            "test.result_submitted",
            assignment_id=str(assignment_id),
            outcome=outcome,
            executed_by=str(executed_by),
        )
        return TestResultRead.model_validate(result)

    # ── Execute all ───────────────────────────────────────────────────────────

    async def execute_all(
        self,
        cycle_id: UUID,
        company_id: UUID,
        triggered_by_user_id: UUID,
    ) -> list[dict]:
        """
        Dispatch ExecutionAgent for all APPROVED scripts in this cycle.
        Creates one AgentRun per script. Returns list of { script_id, agent_run_id }.
        """
        from app.models.test_script import TestScript
        from app.models.enums import TestScriptStatus
        from app.services.agent_dispatcher import AgentDispatcher

        cycle = await self._load_cycle(cycle_id)

        result = await self._db.execute(
            select(TestAssignment.test_script_id)
            .distinct()
            .where(TestAssignment.test_cycle_id == cycle_id)
        )
        script_ids = [r for r in result.scalars().all()]

        if not script_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No scripts assigned to this cycle",
            )

        dispatched: list[dict] = []
        dispatcher = AgentDispatcher(self._db)

        for script_id in script_ids:
            script = await self._db.scalar(
                select(TestScript).where(
                    TestScript.id == script_id,
                    TestScript.status == TestScriptStatus.APPROVED.value,
                    TestScript.deleted_at.is_(None),
                )
            )
            if not script:
                continue

            try:
                agent_run = await dispatcher.dispatch_execution(
                    company_id=company_id,
                    system_id=cycle.system_id,
                    script_id=script_id,
                    triggered_by_user_id=triggered_by_user_id,
                )
                dispatched.append({
                    "script_id": str(script_id),
                    "agent_run_id": str(agent_run.id),
                })
            except Exception as exc:
                log.warning(
                    "test_cycle.execute_all.script_skipped",
                    script_id=str(script_id),
                    error=str(exc),
                )

        if not dispatched:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No approved scripts could be dispatched",
            )

        # Transition cycle to IN_PROGRESS
        if cycle.status == TestCycleStatus.PLANNED.value:
            cycle.status = TestCycleStatus.IN_PROGRESS.value
            cycle.actual_start = datetime.now(timezone.utc).replace(tzinfo=None)

        await self._db.flush()
        log.info("test_cycle.execute_all", cycle_id=str(cycle_id), dispatched=len(dispatched))
        return dispatched

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load_cycle(self, cycle_id: UUID) -> TestCycle:
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test cycle not found")
        return cycle

    async def _load_assignment(self, cycle_id: UUID, assignment_id: UUID) -> TestAssignment:
        result = await self._db.execute(
            select(TestAssignment).where(
                TestAssignment.id == assignment_id,
                TestAssignment.test_cycle_id == cycle_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )
        return assignment


def _is_tester_only(current_user) -> bool:
    """True if user's roles are only tester-level (no lead/admin)."""
    role_values = {r.role for r in current_user.roles}
    lead_or_above = {
        UserRoleEnum.VALIDATION_LEAD.value,
        UserRoleEnum.QA.value,
        UserRoleEnum.COMPANY_ADMIN.value,
        UserRoleEnum.ENTERPRISE_ADMIN.value,
        UserRoleEnum.GLOBAL_ADMIN.value,
    }
    return (
        UserRoleEnum.VALIDATION_TESTER.value in role_values
        and not role_values.intersection(lead_or_above)
    )
