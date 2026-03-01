# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Parallel Batch OCR script for dictionary page images.
Speeds up by:
  1. Pre-splitting all images (CPU, threaded)
  2. Batching multiple column images into single OCR calls
"""
import sys, os, time
from concurrent.futures import ThreadPoolExecutor
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

# How many column images to OCR in a single batch call
OCR_BATCH_SIZE = 8  # 8 columns = 4 pages at a time


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


def split_and_save(img_path, basename):
    """Split one image into left/right columns using auto-detected divider."""
    image = Image.open(img_path)
    w, h = image.size
    header_cut = int(h * 0.05)
    footer_cut = int(h * 0.95)

    divider_x, method = find_divider(image)

    # Wider padding for drawn lines (exclude the line), narrower for white gaps
    padding = 8 if method == 'LINE' else 3

    left_col = image.crop((0, header_cut, divider_x - padding, footer_cut))
    right_col = image.crop((divider_x + padding, header_cut, w, footer_cut))

    left_col.save(os.path.join(SPLIT_DIR, f'{basename}_left.jpg'))
    right_col.save(os.path.join(SPLIT_DIR, f'{basename}_right.jpg'))

    return basename, left_col, right_col, divider_x, method


def main():
    start_img = int(sys.argv[1]) if len(sys.argv) > 1 else 41
    end_img = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    # Collect images, skip already processed
    images_to_process = []
    skipped = 0
    for i in range(start_img, end_img + 1):
        basename = f'IMG_{i:04d}'
        img_path = os.path.join(IMAGE_DIR, f'{basename}.jpg')
        out_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        if not os.path.exists(img_path):
            print(f'[SKIP] {basename}.jpg not found')
            continue
        if os.path.exists(out_path):
            skipped += 1
            continue
        images_to_process.append((img_path, basename))

    total = len(images_to_process)
    print(f'Processing {total} images (skipped {skipped} already done)')
    if total == 0:
        print('Nothing to do.')
        return

    # === Step 1: Pre-split all images in parallel threads ===
    print(f'\n[Step 1] Splitting {total} images into columns (threaded)...')
    t0 = time.time()

    split_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(split_and_save, p, b) for p, b in images_to_process]
        for f in futures:
            basename, left, right, div_x, method = f.result()
            split_results.append((basename, left, right))
            print(f'  {basename}: divider={div_x} ({method})')

    print(f'  Splitting done in {time.time() - t0:.1f}s')

    # === Step 2: Load OCR models ===
    print('\n[Step 2] Loading OCR models...')
    t0 = time.time()
    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    detection_predictor = DetectionPredictor()
    print(f'  Models loaded in {time.time() - t0:.1f}s')

    # === Step 3: Batch OCR — process multiple columns at once ===
    print(f'\n[Step 3] Running batched OCR (batch_size={OCR_BATCH_SIZE})...')
    t_ocr_start = time.time()

    # Build a flat list of (basename, side, image)
    all_columns = []
    for basename, left_img, right_img in split_results:
        all_columns.append((basename, 'left', left_img))
        all_columns.append((basename, 'right', right_img))

    # Process in batches
    ocr_results = {}  # basename -> {'left': [...], 'right': [...]}
    num_batches = (len(all_columns) + OCR_BATCH_SIZE - 1) // OCR_BATCH_SIZE

    for batch_idx in range(num_batches):
        batch_start = batch_idx * OCR_BATCH_SIZE
        batch_end = min(batch_start + OCR_BATCH_SIZE, len(all_columns))
        batch = all_columns[batch_start:batch_end]

        batch_images = [item[2] for item in batch]

        t0 = time.time()
        predictions = recognition_predictor(batch_images, det_predictor=detection_predictor)
        elapsed = time.time() - t0

        # Map predictions back to basenames
        for (basename, side, _), pred in zip(batch, predictions):
            if basename not in ocr_results:
                ocr_results[basename] = {}
            ocr_results[basename][side] = [line.text for line in pred.text_lines]

        pages_in_batch = set(item[0] for item in batch)
        print(f'  Batch {batch_idx+1}/{num_batches}: {len(batch)} columns '
              f'({", ".join(sorted(pages_in_batch))}) — {elapsed:.1f}s')

    # === Step 4: Save text files ===
    print(f'\n[Step 4] Saving {len(ocr_results)} text files...')
    for basename in sorted(ocr_results):
        lines = []
        lines.append('=== বাম কলাম (LEFT COLUMN) ===\n')
        lines.extend(ocr_results[basename].get('left', []))
        lines.append('\n\n=== ডান কলাম (RIGHT COLUMN) ===\n')
        lines.extend(ocr_results[basename].get('right', []))

        out_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    total_time = time.time() - t_ocr_start
    print(f'\nDone! OCR completed in {total_time:.1f}s ({total_time/total:.1f}s per page)')
    print(f'Text files: {TEXT_DIR}')
    print(f'Split images: {SPLIT_DIR}')


if __name__ == '__main__':
    main()
