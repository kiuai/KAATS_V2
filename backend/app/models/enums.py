"""Central enum definitions for all domain models.

These Python enums are used in SQLAlchemy models (via String columns with
check constraints) and re-exported in Pydantic schemas for API validation.
"""

from __future__ import annotations

from enum import Enum

# ── Tenancy & Users ───────────────────────────────────────────────────────────


class ExportFormat(str, Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    PYTEST = "pytest"
    ROBOT_FRAMEWORK = "robot_framework"
    GHERKIN = "gherkin"
    MANUAL_STEPS = "manual_steps"


class UserRoleEnum(str, Enum):
    GLOBAL_ADMIN = "global_admin"
    ENTERPRISE_ADMIN = "enterprise_admin"
    COMPANY_ADMIN = "company_admin"
    SYSTEM_MANAGER = "system_manager"
    VALIDATION_LEAD = "validation_lead"
    QA = "qa"
    VALIDATION_TESTER = "validation_tester"
    BPO = "bpo"


# ── System ────────────────────────────────────────────────────────────────────


class SystemType(str, Enum):
    WEB_APPLICATION = "web_application"
    SAP_FIORI = "sap_fiori"
    SAP_GUI = "sap_gui"
    REST_API = "rest_api"
    DESKTOP_APP = "desktop_app"
    MOBILE_APP = "mobile_app"
    HYBRID = "hybrid"
    OTHER = "other"


# ── Requirements ─────────────────────────────────────────────────────────────


class RequirementSourceType(str, Enum):
    MANUAL = "manual"
    FILE_IMPORT = "file_import"
    CRAWL_GENERATED = "crawl_generated"
    API = "api"


class RequirementPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


# ── Test Scripts ──────────────────────────────────────────────────────────────


class TestScriptStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


# ── Test Cycles & Assignments ─────────────────────────────────────────────────


class TestCycleStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TestAssignmentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


# ── Test & Execution Outcomes ─────────────────────────────────────────────────


class TestOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class StepOutcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    ERROR = "error"


# ── Crawl ─────────────────────────────────────────────────────────────────────


class CrawlerType(str, Enum):
    WEB = "web"
    SAP_FIORI = "sap_fiori"


class CrawlJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlTriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class PageType(str, Enum):
    FORM = "form"
    LIST = "list"
    DETAIL = "detail"
    DASHBOARD = "dashboard"
    NAVIGATION = "navigation"
    UNKNOWN = "unknown"


# ── Scheduler ─────────────────────────────────────────────────────────────────


class AgentType(str, Enum):
    CRAWL = "crawl"
    GENERATION = "generation"
    EXECUTION = "execution"


class ScheduleType(str, Enum):
    ONE_SHOT = "one_shot"
    RECURRING = "recurring"


class ScheduledJobRunStatus(str, Enum):
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    FAILED = "failed"


class LastRunStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# ── Onboarding & Invitations ──────────────────────────────────────────────────


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ── Agent Runs ────────────────────────────────────────────────────────────────


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
