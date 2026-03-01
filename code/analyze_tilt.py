# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
from PIL import Image
import numpy as np

base = r'c:\Users\sankhyac\Downloads\Dict\Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy'

for num in [42, 50, 53, 55, 85, 90, 101]:
    img = Image.open(f'{base}\\IMG_{num:04d}.jpg')
    w, h = img.size
    gray = np.array(img.convert('L'))

    center_start = int(w * 0.35)
    center_end = int(w * 0.65)

    # Check line position in 5 horizontal bands
    band_h = (h * 0.84) / 5
    positions = []
    for band in range(5):
        y_start = int(h * 0.08 + band * band_h)
        y_end = int(y_start + band_h)
        strip = gray[y_start:y_end, center_start:center_end]
        dark_ratio = (strip < 80).mean(axis=0)
        best = int(np.argmax(dark_ratio))
        best_x = center_start + best
        best_ratio = float(dark_ratio[best])
        positions.append((best_x, best_ratio))

    xs = [p[0] for p in positions]
    tilt = max(xs) - min(xs)
    ratios = [f"{p[1]:.2f}" for p in positions]
    print(f'IMG_{num:04d}: positions={xs}, tilt={tilt}px, ratios={ratios}')

# Now check pages WITHOUT a clear line
print("\n--- Pages without clear lines ---")
for num in [41, 44, 60, 65, 75, 80, 99, 100]:
    img = Image.open(f'{base}\\IMG_{num:04d}.jpg')
    w, h = img.size
    gray = np.array(img.convert('L'))

    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    center_start = int(w * 0.35)
    center_end = int(w * 0.65)
    center_cols = body[:, center_start:center_end]

    # Dark pixel ratio
    dark_ratio = (center_cols < 80).mean(axis=0)
    max_ratio = float(np.max(dark_ratio))

    # For no-line pages, use column projection (sum of white pixels)
    # The gap between columns will be the whitest vertical band
    col_means = body[:, center_start:center_end].mean(axis=0)

    # Find widest white gap: threshold at 95th percentile
    thresh = float(np.percentile(col_means, 75))
    is_white = col_means > thresh

    # Find longest white run
    best_start = 0
    best_len = 0
    cur_start = 0
    cur_len = 0
    for i, v in enumerate(is_white):
        if v:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
        else:
            if cur_len > best_len:
                best_start = cur_start
                best_len = cur_len
            cur_len = 0
    if cur_len > best_len:
        best_start = cur_start
        best_len = cur_len

    gap_center = center_start + best_start + best_len // 2
    print(f'IMG_{num:04d}: w={w} mid={w//2} max_dark_ratio={max_ratio:.3f} gap_center={gap_center} gap_width={best_len}px')
