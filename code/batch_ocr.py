# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Batch OCR script for processing multiple dictionary page images.
Loads Surya OCR models once, then processes all images in sequence.
Splits each image into two columns (removing header/footer) before OCR.
"""
import sys, os, time
import numpy as np
from PIL import Image
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
IMAGE_DIR = os.path.join(BASE_DIR, r'Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
SPLIT_DIR = os.path.join(BASE_DIR, 'SplitImages')
TEXT_DIR = os.path.join(BASE_DIR, 'ExtractedText')

os.makedirs(SPLIT_DIR, exist_ok=True)
os.makedirs(TEXT_DIR, exist_ok=True)

def find_divider(image):
    """Auto-detect the vertical divider between two columns.
    Uses dark-pixel ratio with multi-band sampling for tilt handling,
    or white-gap detection as fallback."""
    w, h = image.size
    gray = np.array(image.convert('L'))
    header = int(h * 0.08)
    footer = int(h * 0.92)
    body = gray[header:footer, :]
    body_h = body.shape[0]
    center_start = int(w * 0.35)
    center_end = int(w * 0.65)
    center_cols = body[:, center_start:center_end]

    dark_ratio = (center_cols < 80).mean(axis=0)
    max_ratio = float(np.max(dark_ratio))

    if max_ratio > 0.4:
        n_bands = 10
        band_h = body_h // n_bands
        positions = []
        for band in range(n_bands):
            y_start = band * band_h
            y_end = min(y_start + band_h, body_h)
            strip = body[y_start:y_end, center_start:center_end]
            strip_dark = (strip < 80).mean(axis=0)
            best = int(np.argmax(strip_dark))
            if float(strip_dark[best]) > 0.3:
                positions.append(center_start + best)
        if len(positions) >= 3:
            return int(np.median(positions)), 'LINE'

    col_means = body[:, center_start:center_end].mean(axis=0).astype(float)
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
            return center_start + best_start + best_len // 2, 'GAP'

    window = 10
    windowed = np.convolve(col_means, np.ones(window) / window, mode='valid')
    return center_start + int(np.argmax(windowed)) + window // 2, 'GAP'


def split_image(image):
    """Crop header/footer and split into left/right columns using auto-detected divider."""
    w, h = image.size
    header_cut = int(h * 0.05)
    footer_cut = int(h * 0.95)
    divider_x, method = find_divider(image)
    padding = 8 if method == 'LINE' else 3
    left_col = image.crop((0, header_cut, divider_x - padding, footer_cut))
    right_col = image.crop((divider_x + padding, header_cut, w, footer_cut))
    return left_col, right_col, divider_x

def process_image(image_path, basename, recognition_predictor, detection_predictor):
    """Process a single image: split, OCR, save results."""
    image = Image.open(image_path)
    left_col, right_col, divider_x = split_image(image)
    w = image.size[0]

    # Save split images
    left_col.save(os.path.join(SPLIT_DIR, f'{basename}_left.jpg'))
    right_col.save(os.path.join(SPLIT_DIR, f'{basename}_right.jpg'))

    # OCR each column
    pred_left = recognition_predictor([left_col], det_predictor=detection_predictor)
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

    # Save text
    out_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(output_text)

    return out_path

def main():
    start_img = int(sys.argv[1]) if len(sys.argv) > 1 else 41
    end_img = int(sys.argv[2]) if len(sys.argv) > 2 else 99

    # Collect image paths
    images_to_process = []
    for i in range(start_img, end_img + 1):
        img_name = f'IMG_{i:04d}.jpg'
        img_path = os.path.join(IMAGE_DIR, img_name)
        if os.path.exists(img_path):
            images_to_process.append((img_path, f'IMG_{i:04d}'))
        else:
            print(f'[SKIP] {img_name} not found')

    total = len(images_to_process)
    print(f'Processing {total} images (IMG_{start_img:04d} to IMG_{end_img:04d})')
    print('Loading models (one-time)...')

    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    detection_predictor = DetectionPredictor()

    print('Models loaded. Starting batch OCR...\n')

    for idx, (img_path, basename) in enumerate(images_to_process, 1):
        # Skip if already processed
        out_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        if os.path.exists(out_path):
            print(f'[{idx}/{total}] {basename} — already exists, skipping.')
            continue

        t0 = time.time()
        print(f'[{idx}/{total}] {basename} — processing...', end=' ', flush=True)
        try:
            out = process_image(img_path, basename, recognition_predictor, detection_predictor)
            elapsed = time.time() - t0
            print(f'done ({elapsed:.1f}s)')
        except Exception as e:
            print(f'ERROR: {e}')

    print(f'\nBatch complete. Text files saved to: {TEXT_DIR}')

if __name__ == '__main__':
    main()
