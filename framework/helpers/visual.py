"""Visual regression — compare a page screenshot against a stored baseline.

Baselines live in visual-baselines/<ENV>/<name>.png (commit them). The first
run creates the baseline and passes; later runs fail when more than
VISUAL_THRESHOLD percent of pixels differ (default 2.0). On failure the
actual + diff images are saved under reports/ and attached to the report.
"""
import io
import os
import re
from pathlib import Path

from PIL import Image, ImageChops

from .logger import logger

ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "visual-baselines"
REPORTS_DIR = ROOT / "reports"

PIXEL_TOLERANCE = 16  # per-channel delta below this is "same" (anti-aliasing noise)


def _diff_percent(baseline: Image.Image, actual: Image.Image) -> tuple[float, Image.Image]:
    diff = ImageChops.difference(baseline.convert("RGB"), actual.convert("RGB")).convert("L")
    mask = diff.point(lambda p: 255 if p > PIXEL_TOLERANCE else 0)
    histogram = mask.histogram()
    changed = sum(histogram[1:])
    total = mask.width * mask.height
    return (changed / total) * 100, mask


def assert_visual_match(page, name: str, context=None, threshold: float | None = None):
    threshold = threshold if threshold is not None else float(os.environ.get("VISUAL_THRESHOLD", 2.0))
    env = os.environ.get("ENV", "qa")
    baseline_path = BASELINE_DIR / env / f"{name}.png"

    actual_bytes = page.screenshot(animations="disabled")
    actual = Image.open(io.BytesIO(actual_bytes))

    if not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_bytes(actual_bytes)
        logger.info(f'Visual baseline created: {baseline_path} — future runs compare against it')
        return

    baseline = Image.open(baseline_path)
    if baseline.size != actual.size:
        raise AssertionError(
            f'Visual "{name}": size changed {baseline.size} -> {actual.size} '
            f"(viewport or layout shift; delete the baseline to re-record)"
        )

    percent, mask = _diff_percent(baseline, actual)
    logger.info(f'Visual "{name}": {percent:.2f}% pixels differ (threshold {threshold}%)')
    if percent > threshold:
        slug = re.sub(r"\W+", "_", name)
        out_dir = REPORTS_DIR / "screenshots" / f"visual_{slug}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "actual.png").write_bytes(actual_bytes)
        mask.save(out_dir / "diff.png")
        if context is not None and hasattr(context, "attachments"):
            for label, file in (("Visual actual", "actual.png"), ("Visual diff", "diff.png")):
                context.attachments.append(
                    {
                        "type": "image/png",
                        "name": f"{label}: {name}",
                        "path": str((out_dir / file).relative_to(REPORTS_DIR)),
                    }
                )
        raise AssertionError(
            f'Visual "{name}": {percent:.2f}% of pixels differ (threshold {threshold}%). '
            f"Actual/diff saved under {out_dir}"
        )
