# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Careful image splitter for dictionary pages.
Split ONLY — no OCR. Focuses on accuracy of the cut.

Strategy (v4 — dark pixel ratio based):
1. Dark line detection: Look for columns with >40% dark pixels (a drawn vertical line).
   Sample at 10 height bands, take median for tilt handling.
2. Gap detection using dark pixel ratio: Find runs of columns with near-zero dark
   pixel ratio (< 0.008), pick the run closest to page center.
   This is much more reliable than mean intensity, since Bengali text columns
   can have means of 230-245 but always have >2% dark pixels.

Gap edge detection:
- Walk outward from gap center until dark_ratio > 0.02 (text present).
- Require 2 of 3 consecutive text columns for robustness.
- This gives tight, accurate gaps (15-60px) instead of inflated ones.
"""
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
IMAGE_DIR = os.path.join(BASE_DIR, r'Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
SPLIT_DIR = os.path.join(BASE_DIR, 'SplitImages')

os.makedirs(SPLIT_DIR, exist_ok=True)

# Header/footer crop percentages
HEADER_CROP = 0.05
FOOTER_CROP = 0.95

# Overlap: extra pixels each side extends past the gap edge into the other column
OVERLAP_PX = 25

# Dark pixel ratio thresholds
TEXT_THRESHOLD = 0.02   # Column has text if >2% of pixels are dark
GAP_THRESHOLD = 0.008   # Column is empty if <0.8% of pixels are dark
DARK_PIXEL_LEVEL = 80   # Pixel intensity below this = dark (text stroke)


def find_all_white_runs(dark_ratio_arr, threshold, min_length=5):
    """Find all runs of columns where dark_ratio < threshold.
    Returns list of (start_idx, length) tuples.
    """
    runs = []
    cur_start = 0
    cur_len = 0
    for i, dr in enumerate(dark_ratio_arr):
        if dr < threshold:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
        else:
            if cur_len >= min_length:
                runs.append((cur_start, cur_len))
            cur_len = 0
    if cur_len >= min_length:
        runs.append((cur_start, cur_len))
    return runs


def find_text_boundary(col_dark_ratio, start_x, direction, max_dist=120):
    """Walk from start_x in direction (-1 left, +1 right) until text is found.
    Text = dark_ratio > TEXT_THRESHOLD for 2 of 3 consecutive columns.
    Returns the last gap column (one before text starts).
    """
    w = len(col_dark_ratio)
    last_gap = start_x
    for i in range(1, max_dist):
        x = start_x + i * direction
        if x < 1 or x >= w - 1:
            break
        # Check if this column and neighbors indicate text
        # Look at current and next 2 in the walk direction
        x1 = x
        x2 = x + direction
        x3 = x + 2 * direction
        if x2 < 0 or x2 >= w or x3 < 0 or x3 >= w:
            if col_dark_ratio[x] >= TEXT_THRESHOLD:
                break
            last_gap = x
            continue
        # Count how many of the 3 columns have text
        text_count = sum(1 for cx in [x1, x2, x3]
                        if col_dark_ratio[cx] >= TEXT_THRESHOLD)
        if text_count >= 2:
            break
        last_gap = x
    return last_gap


def find_divider_and_gap(image):
    """Find the divider position AND the full gap extent using dark pixel ratio.
    
    Returns: (gap_left_edge, gap_right_edge, divider_center, method)
    - gap_left_edge: last column before text starts on the left
    - gap_right_edge: last column before text starts on the right
    - The left image should end at gap_left_edge
    - The right image should start at gap_right_edge
    """
    w, h = image.size
    gray = np.array(image.convert('L'))

    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    body_h = body.shape[0]

    # Compute per-column dark pixel ratio across full width
    col_dark_ratio = (body < DARK_PIXEL_LEVEL).mean(axis=0).astype(float)

    center_start = int(w * 0.35)
    center_end = int(w * 0.65)
    center_dark = col_dark_ratio[center_start:center_end]

    # === Method 1: Dark line detection ===
    max_dr = float(np.max(center_dark))

    divider_center = None
    method = None

    if max_dr > 0.4:
        # Multi-band sampling for tilt
        n_bands = 10
        band_h = body_h // n_bands
        positions = []
        for band in range(n_bands):
            y0 = band * band_h
            y1 = min(y0 + band_h, body_h)
            strip = body[y0:y1, center_start:center_end]
            strip_dark = (strip < DARK_PIXEL_LEVEL).mean(axis=0)
            best = int(np.argmax(strip_dark))
            if float(strip_dark[best]) > 0.3:
                positions.append(center_start + best)
        if len(positions) >= 3:
            divider_center = int(np.median(positions))
            method = 'LINE'

    if divider_center is None:
        # === Method 2: Find white runs using dark pixel ratio ===
        # Find all runs of near-empty columns (dark ratio < GAP_THRESHOLD)
        page_center = w // 2

        # Try progressively looser thresholds
        for thresh in [0.005, GAP_THRESHOLD, 0.012, 0.015]:
            runs = find_all_white_runs(center_dark, thresh, min_length=3)
            if runs:
                # Pick the run closest to page center
                best_run = min(runs, key=lambda r:
                    abs((center_start + r[0] + r[1] // 2) - page_center))
                divider_center = center_start + best_run[0] + best_run[1] // 2
                method = f'GAP_DR@{thresh}'
                break

    if divider_center is None:
        # Fallback: smooth dark ratio profile, find the minimum
        kernel = np.ones(21) / 21
        smoothed = np.convolve(center_dark, kernel, mode='valid')
        offset = 21 // 2
        divider_center = center_start + int(np.argmin(smoothed)) + offset
        method = 'FALLBACK'

    # === Find gap edges using dark pixel ratio ===
    if method == 'LINE':
        # Skip past the drawn line (columns with dark_ratio > 0.05)
        line_left = divider_center
        for x in range(divider_center - 1, max(0, divider_center - 25), -1):
            if col_dark_ratio[x] > 0.05:
                line_left = x
            else:
                break
        line_right = divider_center
        for x in range(divider_center + 1, min(w, divider_center + 25)):
            if col_dark_ratio[x] > 0.05:
                line_right = x
            else:
                break
        # From outside the line, find where text starts on each side
        gap_left = find_text_boundary(col_dark_ratio, line_left, -1)
        gap_right = find_text_boundary(col_dark_ratio, line_right, +1)
    else:
        # For GAP type: walk outward from divider center
        gap_left = find_text_boundary(col_dark_ratio, divider_center, -1)
        gap_right = find_text_boundary(col_dark_ratio, divider_center, +1)

    # Safety: ensure minimum gap of 6px
    if gap_right - gap_left < 6:
        gap_left = divider_center - 3
        gap_right = divider_center + 3

    return gap_left, gap_right, divider_center, method


def split_image(img_path, basename):
    """Split one image into left/right columns at the gap edges."""
    image = Image.open(img_path)
    w, h = image.size
    header_cut = int(h * HEADER_CROP)
    footer_cut = int(h * FOOTER_CROP)

    gap_left, gap_right, div_center, method = find_divider_and_gap(image)

    # Left column: extends OVERLAP_PX past gap_left into the gap
    # Right column: extends OVERLAP_PX past gap_right into the gap
    left_end = min(gap_left + OVERLAP_PX, w)
    right_start = max(gap_right - OVERLAP_PX, 0)
    left_col = image.crop((0, header_cut, left_end, footer_cut))
    right_col = image.crop((right_start, header_cut, w, footer_cut))

    left_path = os.path.join(SPLIT_DIR, f'{basename}_left.jpg')
    right_path = os.path.join(SPLIT_DIR, f'{basename}_right.jpg')
    left_col.save(left_path, quality=95)
    right_col.save(right_path, quality=95)

    gap_width = gap_right - gap_left
    return basename, div_center, gap_left, gap_right, gap_width, method, w


def main():
    start_img = int(sys.argv[1]) if len(sys.argv) > 1 else 41
    end_img = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    # Collect images
    images = []
    for i in range(start_img, end_img + 1):
        basename = f'IMG_{i:04d}'
        img_path = os.path.join(IMAGE_DIR, f'{basename}.jpg')
        if os.path.exists(img_path):
            images.append((img_path, basename))

    total = len(images)
    print(f'Splitting {total} images (IMG_{start_img:04d} to IMG_{end_img:04d})')
    print(f'Output: {SPLIT_DIR}')
    print()

    # Split all images in parallel
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(split_image, p, b) for p, b in images]
        for f in futures:
            try:
                result = f.result()
                results.append(result)
                bn, dc, gl, gr, gw, method, w = result
                print(f'  {bn}: w={w} divider={dc} gap=[{gl}-{gr}] width={gw}px ({method})')
            except Exception as e:
                print(f'  ERROR: {e}')

    print(f'\nDone! Split {len(results)} images.')

    # Summary stats
    gap_widths = [r[4] for r in results]
    if gap_widths:
        print(f'Gap widths: min={min(gap_widths)}px, max={max(gap_widths)}px, avg={sum(gap_widths)/len(gap_widths):.0f}px')

    # Flag any suspiciously narrow gaps
    narrow = [r for r in results if r[4] < 10]
    if narrow:
        print(f'\nWARNING: {len(narrow)} images have very narrow gaps (<10px):')
        for r in narrow:
            print(f'  {r[0]}: gap_width={r[4]}px')


if __name__ == '__main__':
    main()
