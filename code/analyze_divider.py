# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""Analyze the vertical divider in IMG_0056 by looking at RGB pixel values."""
from PIL import Image
import numpy as np

base = r'c:\Users\sankhyac\Downloads\Dict\Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy'

img = Image.open(f'{base}\\IMG_0056.jpg')
w, h = img.size
print(f'IMG_0056: {w}x{h}')

# Convert to RGB array
rgb = np.array(img)  # shape: (h, w, 3)
gray = np.array(img.convert('L'))

header = int(h * 0.08)
footer = int(h * 0.92)
body_rgb = rgb[header:footer, :, :]
body_gray = gray[header:footer, :]

center_start = int(w * 0.35)
center_end = int(w * 0.65)

print(f'\nCenter search region: x={center_start} to {center_end}')
print(f'Midpoint: {w//2}')

# === Grayscale analysis ===
center_gray = body_gray[:, center_start:center_end]
dark_ratio = (center_gray < 80).mean(axis=0)
col_means = center_gray.mean(axis=0)

# Top 10 darkest columns by ratio
top10 = np.argsort(dark_ratio)[-10:][::-1]
print('\nTop 10 columns by dark-pixel ratio (grayscale < 80):')
for idx in top10:
    x = center_start + idx
    print(f'  x={x}: dark_ratio={dark_ratio[idx]:.3f}, mean_gray={col_means[idx]:.1f}')

# === RGB analysis ===
# The divider line is likely BLACK - look for pixels where R,G,B are all low
center_rgb = body_rgb[:, center_start:center_end, :]
r_chan = center_rgb[:, :, 0].astype(float)
g_chan = center_rgb[:, :, 1].astype(float)
b_chan = center_rgb[:, :, 2].astype(float)

# Black pixel: all channels < 100
is_black = (r_chan < 100) & (g_chan < 100) & (b_chan < 100)
black_ratio = is_black.mean(axis=0)

# Also check for dark pixels that are NOT part of text by looking at 
# the ratio of very dark pixels (< 50) vs somewhat dark pixels
is_very_dark = (r_chan < 50) & (g_chan < 50) & (b_chan < 50)
very_dark_ratio = is_very_dark.mean(axis=0)

top10_black = np.argsort(black_ratio)[-10:][::-1]
print('\nTop 10 columns by BLACK pixel ratio (R,G,B all < 100):')
for idx in top10_black:
    x = center_start + idx
    print(f'  x={x}: black_ratio={black_ratio[idx]:.3f}, very_dark_ratio={very_dark_ratio[idx]:.3f}')

# === Column intensity profile around likely divider area ===
# Check every column in the center and look for the one with highest
# percentage of continuously dark pixels from top to bottom
print('\n=== Looking for continuous vertical dark structure ===')

best_continuous = 0
best_continuous_x = center_start

for col_idx in range(center_end - center_start):
    col = body_gray[:, center_start + col_idx]
    # Count longest run of dark pixels (< 120)
    is_dark = col < 120
    max_run = 0
    cur_run = 0
    for v in is_dark:
        if v:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0
    if max_run > best_continuous:
        best_continuous = max_run
        best_continuous_x = center_start + col_idx

body_height = footer - header
print(f'Best continuous dark run: x={best_continuous_x}, length={best_continuous}px ({best_continuous/body_height*100:.1f}% of body height)')

# Check a range around the best position
print(f'\nColumns around x={best_continuous_x}:')
for dx in range(-15, 16):
    x = best_continuous_x + dx
    if center_start <= x < center_end:
        col_idx = x - center_start
        r = float(body_rgb[:, x, 0].mean())
        g = float(body_rgb[:, x, 1].mean())
        b = float(body_rgb[:, x, 2].mean())
        dr = dark_ratio[col_idx]
        print(f'  x={x}: R={r:.0f} G={g:.0f} B={b:.0f} dark_ratio={dr:.3f}')

# === What the current detection found ===
print('\n=== Current GAP detection result ===')
thresh = float(np.percentile(col_means, 75))
is_white = col_means > thresh
best_start_w = 0; best_len_w = 0; cur_start_w = 0; cur_len_w = 0
for i, v in enumerate(is_white):
    if v:
        if cur_len_w == 0: cur_start_w = i
        cur_len_w += 1
    else:
        if cur_len_w > best_len_w: best_start_w = cur_start_w; best_len_w = cur_len_w
        cur_len_w = 0
if cur_len_w > best_len_w: best_start_w = cur_start_w; best_len_w = cur_len_w
gap_center = center_start + best_start_w + best_len_w // 2
print(f'White gap: x=[{center_start + best_start_w}-{center_start + best_start_w + best_len_w}], center={gap_center}, width={best_len_w}px')
