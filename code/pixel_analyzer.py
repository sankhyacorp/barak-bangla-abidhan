# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Detailed pixel column analyzer for dictionary page images.
For each image, prints the mean pixel intensity for every column
in the center region, so we can see exactly where the divider is
and where text begins/ends.

Also generates a visual intensity profile as a PNG image.
"""
import sys
import os
import numpy as np
from PIL import Image, ImageDraw

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
IMAGE_DIR = os.path.join(BASE_DIR, r'Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
ANALYSIS_DIR = os.path.join(BASE_DIR, 'Analysis')
os.makedirs(ANALYSIS_DIR, exist_ok=True)


def analyze_image(img_num):
    basename = f'IMG_{img_num:04d}'
    img_path = os.path.join(IMAGE_DIR, f'{basename}.jpg')
    if not os.path.exists(img_path):
        print(f'{basename}: NOT FOUND')
        return

    image = Image.open(img_path)
    w, h = image.size
    gray = np.array(image.convert('L'))

    # Body region (skip header/footer)
    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    body_h = body.shape[0]

    # Full width column means
    col_means = body.mean(axis=0).astype(float)

    # Also compute at multiple height bands to see variation
    n_bands = 5
    band_h = body_h // n_bands
    band_means = []
    for b in range(n_bands):
        y0 = b * band_h
        y1 = min(y0 + band_h, body_h)
        band_means.append(body[y0:y1, :].mean(axis=0).astype(float))

    # Focus on center 30% of width
    center_start = int(w * 0.35)
    center_end = int(w * 0.65)

    print(f'\n{"="*80}')
    print(f'{basename}: {w}x{h}  body={body_h}px  center=[{center_start}-{center_end}]')
    print(f'{"="*80}')

    # Find the darkest column (potential line)
    center_means = col_means[center_start:center_end]
    darkest_idx = int(np.argmin(center_means))
    darkest_x = center_start + darkest_idx
    darkest_val = center_means[darkest_idx]

    # Find the brightest column (potential gap center)
    brightest_idx = int(np.argmax(center_means))
    brightest_x = center_start + brightest_idx
    brightest_val = center_means[brightest_idx]

    print(f'Darkest column: x={darkest_x} mean={darkest_val:.1f}')
    print(f'Brightest column: x={brightest_x} mean={brightest_val:.1f}')

    # Dark pixel ratio analysis (for LINE detection)
    dark_ratio = (body[:, center_start:center_end] < 80).mean(axis=0)
    max_dark_ratio = float(np.max(dark_ratio))
    max_dark_x = center_start + int(np.argmax(dark_ratio))
    print(f'Max dark-pixel ratio: {max_dark_ratio:.3f} at x={max_dark_x}')
    has_line = max_dark_ratio > 0.4
    print(f'Has drawn line: {has_line}')

    # Print detailed column data around the likely divider
    if has_line:
        focus_x = max_dark_x
    else:
        # Find longest white run
        is_white = center_means > 245
        best_start, best_len = 0, 0
        cur_start, cur_len = 0, 0
        for i, v in enumerate(is_white):
            if v:
                if cur_len == 0: cur_start = i
                cur_len += 1
            else:
                if cur_len > best_len:
                    best_start, best_len = cur_start, cur_len
                cur_len = 0
        if cur_len > best_len:
            best_start, best_len = cur_start, cur_len
        if best_len >= 3:
            focus_x = center_start + best_start + best_len // 2
        else:
            focus_x = brightest_x

    print(f'\nFocus point: x={focus_x}')
    print(f'\nDetailed column intensities around x={focus_x} (±60 columns):')
    print(f'{"x":>6} {"mean":>7} {"dark%":>6} {"band1":>6} {"band2":>6} {"band3":>6} {"band4":>6} {"band5":>6} {"marker"}')
    print('-' * 75)

    range_start = max(0, focus_x - 60)
    range_end = min(w, focus_x + 61)

    for x in range(range_start, range_end):
        mean_val = col_means[x]
        dr = (body[:, x] < 80).mean()
        bands = [band_means[b][x] for b in range(n_bands)]
        marker = ''
        if dr > 0.4:
            marker = ' <<<LINE'
        elif mean_val > 248:
            marker = ' .white'
        elif mean_val > 240:
            marker = ' .light'
        elif mean_val < 200:
            marker = ' *TEXT*'
        elif mean_val < 210:
            marker = ' ~text~'

        print(f'{x:>6} {mean_val:>7.1f} {dr:>6.3f} {bands[0]:>6.1f} {bands[1]:>6.1f} {bands[2]:>6.1f} {bands[3]:>6.1f} {bands[4]:>6.1f}{marker}')

    # === Generate visual profile image ===
    profile_w = w
    profile_h = 300
    profile = Image.new('RGB', (profile_w, profile_h), (255, 255, 255))
    draw = ImageDraw.Draw(profile)

    # Draw column mean intensity as a graph
    for x in range(w):
        y = int((1 - col_means[x] / 255.0) * (profile_h - 20)) + 10
        # Color: red in center region, gray outside
        if center_start <= x <= center_end:
            color = (200, 0, 0)
        else:
            color = (150, 150, 150)
        draw.line([(x, profile_h - 10), (x, y)], fill=color)

    # Mark the focus point
    draw.line([(focus_x, 0), (focus_x, profile_h)], fill=(0, 0, 255), width=2)

    # Draw threshold lines
    for thresh, color in [(210, (0, 200, 0)), (230, (200, 200, 0)), (248, (0, 200, 200))]:
        y = int((1 - thresh / 255.0) * (profile_h - 20)) + 10
        draw.line([(0, y), (profile_w, y)], fill=color)

    profile_path = os.path.join(ANALYSIS_DIR, f'{basename}_profile.png')
    profile.save(profile_path)
    print(f'\nProfile saved: {profile_path}')

    # === Also save a version of the original with the split line drawn ===
    annotated = image.copy()
    draw2 = ImageDraw.Draw(annotated)
    draw2.line([(focus_x, 0), (focus_x, h)], fill=(255, 0, 0), width=3)

    # Also draw current gap edges
    # Walk left from focus to find text
    gap_left = focus_x
    for x in range(focus_x - 1, max(0, focus_x - 100), -1):
        if has_line and col_means[x] < 230:
            continue  # skip line penumbra
        if col_means[x] > 210:
            gap_left = x
        else:
            break

    gap_right = focus_x
    for x in range(focus_x + 1, min(w, focus_x + 100)):
        if has_line and col_means[x] < 230:
            continue
        if col_means[x] > 210:
            gap_right = x
        else:
            break

    draw2.line([(gap_left, 0), (gap_left, h)], fill=(0, 255, 0), width=2)
    draw2.line([(gap_right, 0), (gap_right, h)], fill=(0, 0, 255), width=2)

    annotated_path = os.path.join(ANALYSIS_DIR, f'{basename}_annotated.jpg')
    annotated.save(annotated_path, quality=95)
    print(f'Annotated saved: {annotated_path}')
    print(f'  Red line = detected divider center (x={focus_x})')
    print(f'  Green line = gap left edge (x={gap_left})')
    print(f'  Blue line = gap right edge (x={gap_right})')
    print(f'  Gap width = {gap_right - gap_left}px')

    return focus_x, gap_left, gap_right


def main():
    if len(sys.argv) > 1:
        images = [int(x) for x in sys.argv[1:]]
    else:
        # Default: analyze a sample of images that had issues before
        images = [41, 42, 53, 56, 57, 60, 65, 80, 100]

    for img_num in images:
        analyze_image(img_num)


if __name__ == '__main__':
    main()
