# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
import sys, os
import numpy as np
from PIL import Image
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor

def find_divider(image):
    """Auto-detect the vertical divider between two columns.

    Strategy:
    1. Compute per-column dark-pixel ratio (pixels < 80) in the center 30%.
       A drawn vertical line will have ratio > 0.4 while text columns are < 0.25.
    2. If a line is found, sample its position in 10 horizontal bands and take
       the median — this handles slight tilt from manual scanning.
    3. If no drawn line, find the widest continuous white gap.

    Returns: (divider_x, method)  where method is 'LINE' or 'GAP'
    """
    w, h = image.size
    gray = np.array(image.convert('L'))

    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    body_h = body.shape[0]

    center_start = int(w * 0.35)
    center_end = int(w * 0.65)
    center_cols = body[:, center_start:center_end]

    # === Method 1: Dark line detection ===
    dark_ratio = (center_cols < 80).mean(axis=0)
    max_ratio = float(np.max(dark_ratio))

    if max_ratio > 0.4:
        # Found a drawn line. Sample position at multiple heights for tilt.
        n_bands = 10
        band_h = body_h // n_bands
        positions = []
        for band in range(n_bands):
            y_start = band * band_h
            y_end = min(y_start + band_h, body_h)
            strip = body[y_start:y_end, center_start:center_end]
            strip_dark = (strip < 80).mean(axis=0)
            best = int(np.argmax(strip_dark))
            best_ratio = float(strip_dark[best])
            if best_ratio > 0.3:
                positions.append(center_start + best)

        if len(positions) >= 3:
            divider_x = int(np.median(positions))
            return divider_x, 'LINE'

    # === Method 2: White gap detection with strict threshold ===
    col_means = body[:, center_start:center_end].mean(axis=0).astype(float)

    # Try progressively lower thresholds to find the clearest white gap
    for threshold in [248, 240, 230, 220]:
        is_white = col_means > threshold

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

        if best_len >= 5:
            gap_center = center_start + best_start + best_len // 2
            return gap_center, 'GAP'

    # === Fallback: whitest 10px window ===
    window = 10
    windowed = np.convolve(col_means, np.ones(window) / window, mode='valid')
    best_offset = int(np.argmax(windowed)) + window // 2
    return center_start + best_offset, 'GAP'


image_path = sys.argv[1] if len(sys.argv) > 1 else r'c:\Users\sankhyac\Downloads\Dict\Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy\IMG_0100.jpg'
image = Image.open(image_path)

base_dir = r'c:\Users\sankhyac\Downloads\Dict'
split_dir = os.path.join(base_dir, 'SplitImages')
text_dir = os.path.join(base_dir, 'ExtractedText')
os.makedirs(split_dir, exist_ok=True)
os.makedirs(text_dir, exist_ok=True)

basename = os.path.splitext(os.path.basename(image_path))[0]

w, h = image.size
print(f'Image size: {w}x{h}')

# Crop out header (~5% from top) and footer (~5% from bottom)
header_cut = int(h * 0.05)
footer_cut = int(h * 0.95)

# Auto-detect the vertical divider between columns
divider_x, method = find_divider(image)
print(f'Detected divider at x={divider_x} ({method}, midpoint would be {w//2})')

# Wider padding for drawn lines, narrower for white gaps
padding = 8 if method == 'LINE' else 3
left_col = image.crop((0, header_cut, divider_x - padding, footer_cut))
right_col = image.crop((divider_x + padding, header_cut, w, footer_cut))

# Save cropped columns
left_path = os.path.join(split_dir, f'{basename}_left.jpg')
right_path = os.path.join(split_dir, f'{basename}_right.jpg')
left_col.save(left_path)
right_col.save(right_path)
print(f'Saved cropped columns: left={left_col.size}, right={right_col.size}')

print('Loading models...')
foundation_predictor = FoundationPredictor()
recognition_predictor = RecognitionPredictor(foundation_predictor)
detection_predictor = DetectionPredictor()

print('Running OCR on LEFT column...')
pred_left = recognition_predictor([left_col], det_predictor=detection_predictor)

print('Running OCR on RIGHT column...')
pred_right = recognition_predictor([right_col], det_predictor=detection_predictor)

# Build output text
lines = []
lines.append('=== বাম কলাম (LEFT COLUMN) ===\n')
for line in pred_left[0].text_lines:
    lines.append(line.text)
lines.append('\n\n=== ডান কলাম (RIGHT COLUMN) ===\n')
for line in pred_right[0].text_lines:
    lines.append(line.text)

output_text = '\n'.join(lines)

# Save to ExtractedText folder
out_path = os.path.join(text_dir, f'{basename}_extracted_text.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(output_text)

print(f'\nSaved extracted text to: {out_path}')
print('\n' + output_text)
