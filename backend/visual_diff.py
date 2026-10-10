"""
Visual Regression Monitor Agent using Pixelmatch and Pillow.
Compares baseline vs candidate UI screenshots, produces diff heatmap and regression statistics.
"""

import os
from typing import Dict, Any, Tuple
from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch


def compare_images(
    baseline_path: str,
    candidate_path: str,
    output_diff_path: str,
    threshold: float,
    tolerance_percent: float,
) -> Dict[str, Any]:
    """
    Compares two screenshots using pixelmatch.
    
    :param baseline_path: Path to baseline golden screenshot.
    :param candidate_path: Path to newly captured candidate screenshot.
    :param output_diff_path: Where to save the diff heatmap image.
    :param threshold: Matching threshold (0.0 to 1.0). Smaller is more sensitive.
    :param tolerance_percent: Percentage of mismatched pixels tolerated before flagging regression.
    :return: Dict containing diff metrics and pass/fail status.
    """
    if not os.path.exists(baseline_path):
        return {
            "status": "ERROR",
            "error": f"Baseline image not found: {baseline_path}",
            "passed": False,
        }
    if not os.path.exists(candidate_path):
        return {
            "status": "ERROR",
            "error": f"Candidate image not found: {candidate_path}",
            "passed": False,
        }

    img1 = Image.open(baseline_path).convert("RGBA")
    img2 = Image.open(candidate_path).convert("RGBA")

    # If image dimensions differ, resize or crop canvas to max width & height with transparent padding
    max_w = max(img1.width, img2.width)
    max_h = max(img1.height, img2.height)

    if img1.size != (max_w, max_h):
        padded1 = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        padded1.paste(img1, (0, 0))
        img1 = padded1

    if img2.size != (max_w, max_h):
        padded2 = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        padded2.paste(img2, (0, 0))
        img2 = padded2

    diff_img = Image.new("RGBA", (max_w, max_h))
    total_pixels = max_w * max_h

    mismatched_pixels = pixelmatch(
        img1,
        img2,
        diff_img,
        threshold=threshold,
        diff_color=(255, 0, 96),  # Neon Pink/Magenta for diffs
        diff_mask=True,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_diff_path)), exist_ok=True)
    diff_img.save(output_diff_path, "PNG")

    mismatch_ratio = (mismatched_pixels / total_pixels) * 100.0
    has_passed = mismatch_ratio <= tolerance_percent

    return {
        "status": "COMPLETED",
        "passed": has_passed,
        "total_pixels": total_pixels,
        "mismatched_pixels": mismatched_pixels,
        "mismatch_percentage": round(mismatch_ratio, 3),
        "tolerance_threshold": tolerance_percent,
        "diff_image_path": output_diff_path,
        "baseline_path": baseline_path,
        "candidate_path": candidate_path,
        "summary": (
            f"Visual check PASSED with {mismatch_ratio:.2f}% shift (below {tolerance_percent}% tolerance)."
            if has_passed
            else f"Visual REGRESSION DETECTED! {mismatch_ratio:.2f}% pixel shift exceeds {tolerance_percent}% threshold."
        ),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        result = compare_images(sys.argv[1], sys.argv[2], sys.argv[3])
        print(result)
    else:
        print("Usage: python visual_diff.py <baseline_img> <candidate_img> <output_diff_png>")
