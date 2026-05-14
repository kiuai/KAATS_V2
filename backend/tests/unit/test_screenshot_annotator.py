"""
Unit tests for ScreenshotAnnotator.

These tests create minimal in-memory PNG images via Pillow and verify the
annotated output has the expected pixel properties.

No filesystem I/O; no external services.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from app.agents.screenshot_annotator import ScreenshotAnnotator, get_annotator


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_png(width: int = 800, height: int = 600, colour: tuple = (200, 200, 200)) -> bytes:
    """Create a solid-colour PNG image and return its bytes."""
    img = Image.new("RGB", (width, height), colour)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_image(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes)).convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Annotator contract tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScreenshotAnnotator:
    @pytest.fixture
    def annotator(self) -> ScreenshotAnnotator:
        return ScreenshotAnnotator()

    @pytest.fixture
    def base_png(self) -> bytes:
        return _make_png()

    # ── Output format ─────────────────────────────────────────────────────────

    def test_output_is_valid_png(self, annotator, base_png) -> None:
        result = annotator.annotate(base_png, 1, "Navigate to login", "passed")
        img = _load_image(result)
        assert img.format is None  # already opened; verify no exception

    def test_output_dimensions_preserved(self, annotator, base_png) -> None:
        result = annotator.annotate(base_png, 1, "Click button", "passed")
        img = _load_image(result)
        # Dimensions must match original
        assert img.size == (800, 600)

    def test_non_standard_dimensions_preserved(self, annotator) -> None:
        png = _make_png(1280, 720)
        result = annotator.annotate(png, 3, "Screenshot", "failed")
        img = _load_image(result)
        assert img.size == (1280, 720)

    # ── Top banner (dark grey) ────────────────────────────────────────────────

    def test_top_banner_is_dark(self, annotator, base_png) -> None:
        """
        The top 48px banner should be darker than the original grey background.
        The original image is (200, 200, 200); the banner is (30, 30, 30) blended.
        """
        result = annotator.annotate(base_png, 1, "Test step", "passed")
        img = _load_image(result)
        # Sample the centre of the top banner (y=24, x=400)
        r, g, b = img.getpixel((400, 24))
        # Must be significantly darker than the original 200,200,200 background
        assert r < 150 and g < 150 and b < 150, (
            f"Top banner pixel ({r},{g},{b}) not dark enough"
        )

    # ── Bottom banner (outcome colour) ───────────────────────────────────────

    def test_bottom_banner_green_for_passed(self, annotator, base_png) -> None:
        """Passed outcome → green (34, 197, 94) blended banner."""
        result = annotator.annotate(base_png, 1, "Test", "passed")
        img = _load_image(result)
        w, h = img.size
        # Centre of bottom banner
        r, g, b = img.getpixel((w // 2, h - 24))
        # Green channel should dominate
        assert g > r and g > b, f"Bottom banner {(r, g, b)} should be green for 'passed'"

    def test_bottom_banner_red_for_failed(self, annotator, base_png) -> None:
        """Failed outcome → red (239, 68, 68) blended banner."""
        result = annotator.annotate(base_png, 2, "Test", "failed")
        img = _load_image(result)
        w, h = img.size
        r, g, b = img.getpixel((w // 2, h - 24))
        # Red channel should dominate
        assert r > g and r > b, f"Bottom banner {(r, g, b)} should be red for 'failed'"

    def test_bottom_banner_orange_for_blocked(self, annotator, base_png) -> None:
        """Blocked outcome → orange (249, 115, 22) blended banner."""
        result = annotator.annotate(base_png, 3, "Test", "blocked")
        img = _load_image(result)
        w, h = img.size
        r, g, b = img.getpixel((w // 2, h - 24))
        # Orange: red > green > blue
        assert r > g > b, f"Bottom banner {(r, g, b)} should be orange for 'blocked'"

    # ── Border ────────────────────────────────────────────────────────────────

    def test_border_present_for_passed(self, annotator, base_png) -> None:
        """The outer border should be coloured (green) for passed."""
        result = annotator.annotate(base_png, 1, "Test", "passed")
        img = _load_image(result)
        w, h = img.size
        # Top-left corner pixel (inside 4px border)
        r, g, b = img.getpixel((2, 2))
        # Should be noticeably green
        assert g > r and g > b, f"Border corner pixel {(r, g, b)} should be green"

    # ── Step numbers ──────────────────────────────────────────────────────────

    def test_high_step_number_does_not_crash(self, annotator, base_png) -> None:
        result = annotator.annotate(base_png, 999, "Last step", "passed")
        assert isinstance(result, bytes)
        assert len(result) > 0

    # ── Description truncation ────────────────────────────────────────────────

    def test_very_long_description_does_not_crash(self, annotator, base_png) -> None:
        long_desc = "A" * 500
        result = annotator.annotate(base_png, 1, long_desc, "passed")
        assert isinstance(result, bytes)
        assert len(result) > 0

    # ── Timestamp ─────────────────────────────────────────────────────────────

    def test_custom_timestamp_accepted(self, annotator, base_png) -> None:
        ts = datetime(2026, 1, 15, 9, 30, 0, tzinfo=timezone.utc)
        result = annotator.annotate(base_png, 1, "Test", "passed", timestamp=ts)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_no_timestamp_uses_current_time(self, annotator, base_png) -> None:
        # Just verify it doesn't crash with no timestamp
        result = annotator.annotate(base_png, 1, "Test", "passed")
        assert isinstance(result, bytes)

    # ── Unknown outcome ───────────────────────────────────────────────────────

    def test_unknown_outcome_uses_fallback_colour(self, annotator, base_png) -> None:
        result = annotator.annotate(base_png, 1, "Test", "unknown_outcome")
        img = _load_image(result)
        w, h = img.size
        # Should not crash; bottom banner should exist (greyish fallback)
        r, g, b = img.getpixel((w // 2, h - 24))
        # Any colour is fine; just confirm not the original background exactly
        assert (r, g, b) != (200, 200, 200)

    # ── Output is PNG ─────────────────────────────────────────────────────────

    def test_output_starts_with_png_magic_bytes(self, annotator, base_png) -> None:
        result = annotator.annotate(base_png, 1, "Test", "passed")
        # PNG magic bytes: \x89PNG\r\n\x1a\n
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    # ── All supported outcomes ────────────────────────────────────────────────

    @pytest.mark.parametrize("outcome", ["passed", "failed", "blocked", "error", "skipped"])
    def test_all_defined_outcomes_produce_output(self, annotator, base_png, outcome) -> None:
        result = annotator.annotate(base_png, 1, "Step", outcome)
        assert isinstance(result, bytes)
        assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

def test_get_annotator_returns_instance() -> None:
    a = get_annotator()
    assert isinstance(a, ScreenshotAnnotator)


def test_get_annotator_is_singleton() -> None:
    a1 = get_annotator()
    a2 = get_annotator()
    assert a1 is a2
