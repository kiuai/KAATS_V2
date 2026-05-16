"""Annotate Playwright screenshots with step metadata using Pillow."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Final

from PIL import Image, ImageDraw, ImageFont

# ── Outcome colours ───────────────────────────────────────────────────────────
_OUTCOME_COLOURS: dict[str, tuple[int, int, int]] = {
    "passed": (34, 197, 94),  # green-500
    "failed": (239, 68, 68),  # red-500
    "blocked": (249, 115, 22),  # orange-500
    "error": (239, 68, 68),
    "skipped": (148, 163, 184),  # slate-400
}
_DARK_GREY: Final = (30, 30, 30)
_WHITE: Final = (255, 255, 255)
_BANNER_HEIGHT: Final = 48  # px
_BORDER_PX: Final = 4  # px
_ALPHA: Final = 210  # 0-255 overlay transparency


def _colour(outcome: str) -> tuple[int, int, int]:
    return _OUTCOME_COLOURS.get(outcome.lower(), (100, 100, 100))


def _load_font(size: int) -> ImageFont.ImageFont:
    """Try to load a decent font; fall back to PIL default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    # PIL default bitmap font — no size parameter
    return ImageFont.load_default()


class ScreenshotAnnotator:
    """
    Applies step metadata overlays to a PNG screenshot.

    Overlays:
    - Top banner (dark grey, semi-transparent): "Step {N}: {description}"
    - Bottom banner (outcome colour, semi-transparent): outcome label + timestamp
    - Thin coloured border around the full image
    """

    def annotate(
        self,
        image_bytes: bytes,
        step_number: int,
        description: str,
        outcome: str,
        timestamp: datetime | None = None,
    ) -> bytes:
        """
        Return annotated PNG bytes.

        Parameters
        ----------
        image_bytes:  Raw PNG bytes from Playwright.
        step_number:  1-based step index.
        description:  Short description of the step action.
        outcome:      "passed" | "failed" | "blocked" | "error" | "skipped"
        timestamp:    Capture time (defaults to now UTC).
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        colour = _colour(outcome)

        # ── Load and convert to RGBA ──────────────────────────────────────────
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = img.size

        # ── Fonts ─────────────────────────────────────────────────────────────
        font_large = _load_font(18)
        font_small = _load_font(13)

        # ── Top banner ────────────────────────────────────────────────────────
        top_overlay = Image.new("RGBA", (w, _BANNER_HEIGHT), (*_DARK_GREY, _ALPHA))
        draw_top = ImageDraw.Draw(top_overlay)
        step_label = f"Step {step_number:03d}: {description}"
        # Truncate long descriptions
        max_chars = max(10, (w // 10))
        if len(step_label) > max_chars:
            step_label = step_label[: max_chars - 3] + "..."
        draw_top.text((12, 14), step_label, font=font_large, fill=_WHITE)
        img.alpha_composite(top_overlay, (0, 0))

        # ── Bottom banner ─────────────────────────────────────────────────────
        bot_overlay = Image.new("RGBA", (w, _BANNER_HEIGHT), (*colour, _ALPHA))
        draw_bot = ImageDraw.Draw(bot_overlay)
        outcome_label = outcome.upper()
        draw_bot.text((12, 8), outcome_label, font=font_large, fill=_WHITE)
        draw_bot.text((w - 220, 16), ts_str, font=font_small, fill=_WHITE)
        img.alpha_composite(bot_overlay, (0, h - _BANNER_HEIGHT))

        # ── Coloured border ───────────────────────────────────────────────────
        draw = ImageDraw.Draw(img)
        for i in range(_BORDER_PX):
            draw.rectangle(
                [i, i, w - 1 - i, h - 1 - i],
                outline=(*colour, 255),
            )

        # ── Encode back to PNG ────────────────────────────────────────────────
        out = io.BytesIO()
        img.convert("RGB").save(out, format="PNG", optimize=False)
        return out.getvalue()


# Module-level singleton
_annotator: ScreenshotAnnotator | None = None


def get_annotator() -> ScreenshotAnnotator:
    global _annotator
    if _annotator is None:
        _annotator = ScreenshotAnnotator()
    return _annotator
