"""Requirement service — filtered list, import, quality check, generate-script dispatch."""
from __future__ import annotations

import io
import time
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from app.models.enums import RequirementStatus, TestScriptStatus, UserRoleEnum
from app.schemas.common import Page, encode_cursor, decode_cursor
from app.schemas.requirement import (
    QualityCheckResult,
    RequirementCreate,
    RequirementImportPreview,
    RequirementRead,
    RequirementUpdate,
    RequirementWithScripts,
)

log = structlog.get_logger(__name__)

# Simple in-memory quality-check cache: { requirement_id_str: (expiry_ts, QualityCheckResult) }
_quality_cache: dict[str, tuple[float, QualityCheckResult]] = {}
_QUALITY_TTL = 3600.0  # 1 hour


class RequirementService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_for_system(self, system_id: UUID) -> list[RequirementRead]:
        """Backwards-compat unfiltered list."""
        result = await self._db.execute(
            select(Requirement).where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
        )
        return [RequirementRead.model_validate(r) for r in result.scalars().all()]

    async def list_for_system_paginated(
        self,
        system_id: UUID,
        bpo_domain: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        business_domain: str | None = None,
        source_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        cursor: str | None = None,
    ) -> Page[RequirementRead]:
        """
        Filtered, paginated list.
        bpo_domain: when set, restricts results to that business_domain.
        cursor: if provided, used for keyset pagination (overrides offset).
        """
        q = select(Requirement).where(
            Requirement.system_id == system_id,
            Requirement.deleted_at.is_(None),
        )

        effective_domain = bpo_domain or business_domain
        if effective_domain:
            q = q.where(Requirement.business_domain == effective_domain)
        if status_filter:
            q = q.where(Requirement.status == status_filter)
        if priority:
            q = q.where(Requirement.priority == priority)
        if source_type:
            q = q.where(Requirement.source_type == source_type)
        if search:
            q = q.where(Requirement.title.ilike(f"%{search}%"))

        q = q.order_by(Requirement.created_at.desc())

        # Total count (before cursor/offset)
        count_q = select(func.count()).select_from(q.subquery())
        total = await self._db.scalar(count_q) or 0

        # Cursor pagination
        if cursor:
            try:
                cutoff = decode_cursor(cursor)
                q = q.where(Requirement.created_at < cutoff)
            except ValueError:
                pass  # ignore bad cursor, fall through to offset
        else:
            q = q.offset(offset)

        q = q.limit(limit)
        result = await self._db.execute(q)
        items = result.scalars().all()

        next_cursor = None
        if len(items) == limit and items:
            next_cursor = encode_cursor(items[-1].created_at)

        return Page(
            items=[RequirementRead.model_validate(r) for r in items],
            total=total,
            limit=limit,
            offset=offset,
            next_cursor=next_cursor,
        )

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(self, system_id: UUID, body: RequirementCreate) -> RequirementRead:
        req = Requirement(system_id=system_id, **body.model_dump())
        self._db.add(req)
        await self._db.flush()
        return RequirementRead.model_validate(req)

    async def create_with_context(
        self,
        system_id: UUID,
        body: RequirementCreate,
        company_id: UUID,
        created_by: UUID,
    ) -> RequirementRead:
        req = Requirement(
            system_id=system_id,
            company_id=company_id,
            created_by=created_by,
            **body.model_dump(),
        )
        self._db.add(req)
        await self._db.flush()
        return RequirementRead.model_validate(req)

    async def bulk_create(
        self,
        system_id: UUID,
        previews: list[RequirementImportPreview],
        company_id: UUID,
        created_by: UUID,
        source_reference: str | None = None,
        default_domain: str | None = None,
    ) -> list[RequirementRead]:
        """Save a list of import previews as Requirement records."""
        created: list[RequirementRead] = []
        for p in previews:
            req = Requirement(
                system_id=system_id,
                company_id=company_id,
                created_by=created_by,
                title=p.title,
                description=p.description,
                source_type=p.source_type or "import",
                source_reference=source_reference,
                business_domain=p.business_domain or default_domain,
                priority=p.priority or "medium",
                tags=p.tags,
                status=RequirementStatus.DRAFT.value,
            )
            self._db.add(req)
            created.append(req)
        await self._db.flush()
        return [RequirementRead.model_validate(r) for r in created]

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get(self, requirement_id: UUID) -> RequirementRead:
        req = await self._load(requirement_id)
        return RequirementRead.model_validate(req)

    async def get_with_scripts(self, requirement_id: UUID) -> RequirementWithScripts:
        """Return requirement with script counts."""
        from app.models.test_script import TestScript

        req = await self._load(requirement_id)
        total = await self._db.scalar(
            select(func.count()).where(
                TestScript.requirement_id == requirement_id,
                TestScript.deleted_at.is_(None),
            )
        ) or 0
        approved = await self._db.scalar(
            select(func.count()).where(
                TestScript.requirement_id == requirement_id,
                TestScript.status == TestScriptStatus.APPROVED.value,
                TestScript.deleted_at.is_(None),
            )
        ) or 0

        out = RequirementWithScripts.model_validate(req)
        out.script_count = total
        out.approved_script_count = approved
        return out

    # ── Update ────────────────────────────────────────────────────────────────

    async def update(self, requirement_id: UUID, body: RequirementUpdate) -> RequirementRead:
        req = await self._load(requirement_id)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(req, field, value)
        await self._db.flush()
        # Invalidate quality cache
        _quality_cache.pop(str(requirement_id), None)
        return RequirementRead.model_validate(req)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete(self, requirement_id: UUID) -> None:
        """Backwards-compat hard delete."""
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
            )
        await self._db.delete(req)
        await self._db.flush()

    async def soft_delete(self, requirement_id: UUID) -> None:
        """
        Soft-delete. Raises 409 if there are APPROVED test scripts linked.
        """
        from app.models.test_script import TestScript
        from datetime import datetime, timezone

        req = await self._load(requirement_id)

        approved_count = await self._db.scalar(
            select(func.count()).where(
                TestScript.requirement_id == requirement_id,
                TestScript.status == TestScriptStatus.APPROVED.value,
                TestScript.deleted_at.is_(None),
            )
        ) or 0
        if approved_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete requirement with {approved_count} approved "
                    "test script(s). Deprecate them first."
                ),
            )

        req.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.flush()

    # ── Status transitions ────────────────────────────────────────────────────

    async def approve(self, requirement_id: UUID) -> RequirementRead:
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
            )
        req.status = RequirementStatus.ACTIVE.value
        await self._db.flush()
        return RequirementRead.model_validate(req)

    # ── Quality check ─────────────────────────────────────────────────────────

    async def quality_check(self, requirement_id: UUID) -> QualityCheckResult:
        """
        Score a requirement's quality. Result is cached for 1 hour.
        """
        cache_key = str(requirement_id)
        now = time.time()

        cached = _quality_cache.get(cache_key)
        if cached and cached[0] > now:
            return QualityCheckResult(
                score=cached[1].score,
                grade=cached[1].grade,
                suggestions=cached[1].suggestions,
                cached=True,
            )

        req = await self._load(requirement_id)
        result = _compute_quality(req.title, req.description)
        _quality_cache[cache_key] = (now + _QUALITY_TTL, result)
        return result

    # ── Generate script shortcut ──────────────────────────────────────────────

    async def generate_script(
        self,
        requirement_id: UUID,
        export_format: str,
        company_id: UUID,
        triggered_by_user_id: UUID,
    ) -> dict:
        """
        Dispatch GenerationAgent for a single requirement.
        Returns { agent_run_id }.
        """
        from app.services.agent_dispatcher import AgentDispatcher

        req = await self._load(requirement_id)
        dispatcher = AgentDispatcher(self._db)
        agent_run = await dispatcher.dispatch_generation(
            company_id=company_id,
            system_id=req.system_id,
            requirement_ids=[requirement_id],
            target_formats=[export_format],
            triggered_by_user_id=triggered_by_user_id,
        )
        return {"agent_run_id": str(agent_run.id)}

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _load(self, requirement_id: UUID) -> Requirement:
        result = await self._db.execute(
            select(Requirement).where(
                Requirement.id == requirement_id,
                Requirement.deleted_at.is_(None),
            )
        )
        req = result.scalar_one_or_none()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found"
            )
        return req


# ── File parsing ──────────────────────────────────────────────────────────────

def parse_requirement_file(
    filename: str,
    content: bytes,
) -> list[RequirementImportPreview]:
    """
    Parse an uploaded file into a list of RequirementImportPreview.
    Supported: .txt, .csv, .json, .docx, .pdf
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    if ext == "json":
        return _parse_json(content)
    if ext == "csv":
        return _parse_csv(content)
    if ext == "docx":
        return _parse_docx(content)
    if ext == "pdf":
        return _parse_pdf(content)
    # Default: plain text
    return _parse_text(content)


def _parse_text(content: bytes) -> list[RequirementImportPreview]:
    text = content.decode("utf-8", errors="replace")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    results: list[RequirementImportPreview] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0][:500]
        description = " ".join(lines[1:]) if len(lines) > 1 else title
        results.append(RequirementImportPreview(title=title, description=description))
    return results or [RequirementImportPreview(title="Imported requirement", description=text[:1000])]


def _parse_csv(content: bytes) -> list[RequirementImportPreview]:
    import csv
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    results: list[RequirementImportPreview] = []
    for row in reader:
        title = row.get("title") or row.get("Title") or row.get("name") or ""
        desc = row.get("description") or row.get("Description") or row.get("desc") or title
        domain = row.get("business_domain") or row.get("domain") or None
        priority = row.get("priority") or "medium"
        if title:
            results.append(RequirementImportPreview(
                title=title[:500],
                description=desc,
                business_domain=domain,
                priority=priority.lower(),
            ))
    return results


def _parse_json(content: bytes) -> list[RequirementImportPreview]:
    import json
    data = json.loads(content)
    if isinstance(data, dict):
        data = data.get("requirements", data.get("items", [data]))
    results: list[RequirementImportPreview] = []
    for item in data:
        if isinstance(item, str):
            results.append(RequirementImportPreview(title=item[:500], description=item))
        elif isinstance(item, dict):
            title = item.get("title") or item.get("name") or ""
            desc = item.get("description") or item.get("desc") or title
            results.append(RequirementImportPreview(
                title=title[:500],
                description=desc,
                business_domain=item.get("business_domain"),
                priority=item.get("priority", "medium"),
                tags=item.get("tags"),
            ))
    return results


def _parse_docx(content: bytes) -> list[RequirementImportPreview]:
    try:
        from docx import Document  # type: ignore[import]
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            return [RequirementImportPreview(title="Imported", description="No content")]
        # Treat heading-level paragraphs as titles, rest as description
        results: list[RequirementImportPreview] = []
        current_title: str | None = None
        current_desc_lines: list[str] = []
        for para in paragraphs:
            if len(para) < 150 and not para.endswith("."):
                if current_title:
                    results.append(RequirementImportPreview(
                        title=current_title, description=" ".join(current_desc_lines) or current_title
                    ))
                current_title = para[:500]
                current_desc_lines = []
            else:
                current_desc_lines.append(para)
        if current_title:
            results.append(RequirementImportPreview(
                title=current_title, description=" ".join(current_desc_lines) or current_title
            ))
        return results or [RequirementImportPreview(title=paragraphs[0][:500], description=" ".join(paragraphs))]
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DOCX parsing requires python-docx — not installed",
        )


def _parse_pdf(content: bytes) -> list[RequirementImportPreview]:
    try:
        import pypdf  # type: ignore[import]
        reader = pypdf.PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return _parse_text(text.encode())
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF parsing requires pypdf — not installed",
        )


# ── Quality scoring ───────────────────────────────────────────────────────────

def _compute_quality(title: str, description: str) -> QualityCheckResult:
    score = 100
    suggestions: list[str] = []

    # Title length
    if len(title) < 10:
        score -= 20
        suggestions.append("Title is too short — aim for 10+ characters")
    elif len(title) > 200:
        score -= 10
        suggestions.append("Title is too long — keep it under 200 characters")

    # Description length
    if len(description) < 50:
        score -= 25
        suggestions.append("Description is too brief — add measurable acceptance criteria")
    elif len(description) < 100:
        score -= 10
        suggestions.append("Description could be more detailed")

    # Testability indicators
    testable = ["must", "shall", "should", "verify", "when", "given", "if", "then",
                "assert", "expect", "ensure", "validate"]
    if not any(w in description.lower() for w in testable):
        score -= 15
        suggestions.append("Add testability criteria (must/shall/when/then/verify)")

    # Measurability (numbers or thresholds)
    if not any(c.isdigit() for c in description):
        score -= 5
        suggestions.append("Consider adding measurable thresholds (numbers, percentages, timeouts)")

    # Avoid vague language
    vague = ["it should", "it must", "the system", "the user", "maybe", "possibly"]
    vague_found = [v for v in vague if v in description.lower()]
    if vague_found:
        suggestions.append(f"Replace vague language: {', '.join(vague_found[:3])!r}")

    score = max(0, score)
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    return QualityCheckResult(score=score, grade=grade, suggestions=suggestions)
