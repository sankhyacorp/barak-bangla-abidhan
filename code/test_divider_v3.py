# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""Quick test of improved find_divider v3 on all images 40-101."""
from PIL import Image
import numpy as np

base = r'c:\Users\sankhyac\Downloads\Dict\Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy'

def find_divider(image):
    w, h = image.size
    gray = np.array(image.convert('L'))
    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    body_h = body.shape[0]
    center_start = int(w * 0.35)
    center_end = int(w * 0.65)
    center_cols = body[:, center_start:center_end]

    # Method 1: Dark line
    dark_ratio = (center_cols < 80).mean(axis=0)
    max_dr = float(np.max(dark_ratio))
    if max_dr > 0.4:
        n_bands = 10
        band_h = body_h // n_bands
        positions = []
        for band in range(n_bands):
            y0 = band * band_h
            y1 = min(y0 + band_h, body_h)
            strip = body[y0:y1, center_start:center_end]
            strip_dark = (strip < 80).mean(axis=0)
            best = int(np.argmax(strip_dark))
            if float(strip_dark[best]) > 0.3:
                positions.append(center_start + best)
        if len(positions) >= 3:
            return int(np.median(positions)), 'LINE', w

    # Method 2: Strict white gap with progressive threshold
    col_means = center_cols.mean(axis=0).astype(float)
    for threshold in [248, 240, 230, 220]:
        is_white = col_means > threshold
        best_start = 0; best_len = 0; cur_start = 0; cur_len = 0
        for i, v in enumerate(is_white):
            if v:
                if cur_len == 0: cur_start = i
                cur_len += 1
            else:
                if cur_len > best_len: best_start = cur_start; best_len = cur_len
                cur_len = 0
        if cur_len > best_len: best_start = cur_start; best_len = cur_len
        if best_len >= 5:
            gap_center = center_start + best_start + best_len // 2
            return gap_center, f'GAP@{threshold}', w

    # Fallback
    window = 10
    windowed = np.convolve(col_means, np.ones(window)/window, mode='valid')
    return center_start + int(np.argmax(windowed)) + window // 2, 'FALLBACK', w

for num in range(40, 102):
    path = f'{base}\\IMG_{num:04d}.jpg'
    try:
        img = Image.open(path)
        div_x, method, w = find_divider(img)
        print(f'IMG_{num:04d}: w={w} mid={w//2} div={div_x} ({method}) diff={div_x-w//2:+d}')
    except FileNotFoundError:
        pass
