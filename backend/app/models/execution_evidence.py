from __future__ import annotations

# Execution evidence models are defined in test_result.py (EvidenceScreenshot)
# alongside TestStepResult to keep the ORM relationships co-located.
# This module re-exports them for convenience.

from app.models.test_result import EvidenceScreenshot as EvidenceScreenshot  # noqa: F401
