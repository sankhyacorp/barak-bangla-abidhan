# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
OCR script for ভাষাতত্ত্ব (Linguistics) pages.
Full-page Surya OCR (no column splitting) — same approach as intro.

Sections are defined below and can be extended as new pages are added.

Usage:
  python ocr_bhashatattwa.py                 # OCR all defined pages
  python ocr_bhashatattwa.py 587 590         # OCR pages 587-590 only
"""
import sys, os, time, gc
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
IMAGE_DIR = os.path.join(PARENT_DIR, 'Images',
    'Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
TEXT_DIR = os.path.join(BASE_DIR, 'ExtractedText')

os.makedirs(TEXT_DIR, exist_ok=True)

# ─── Section definitions ─────────────────────────────────────
# Add new sections here as you process more pages.
SECTIONS = {
    'charya_o_srikrishnakirtaner_bhasha': {
        'title_bn': 'চর্যা ও শ্রীকৃষ্ণকীর্তনের ভাষা',
        'pages': list(range(587, 589)),   # IMG_0587 – IMG_0588
    },
    # Example future sections:
    # 'dhwanitatwa': {
    #     'title_bn': 'ধ্বনিতত্ত্ব',
    #     'pages': list(range(589, 595)),
    # },
}

ALL_PAGES = sorted(set(p for s in SECTIONS.values() for p in s['pages']))


def ocr_full_page(image, recognition_predictor, detection_predictor):
    """Run OCR on full page, cropping header/footer margins."""
    w, h = image.size
    header_cut = int(h * 0.03)
    footer_cut = int(h * 0.97)
    cropped = image.crop((0, header_cut, w, footer_cut))
    pred = recognition_predictor([cropped], det_predictor=detection_predictor)
    lines = [line.text for line in pred[0].text_lines]
    return lines


def main():
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor

    pages = ALL_PAGES
    if len(sys.argv) >= 3:
        pages = list(range(int(sys.argv[1]), int(sys.argv[2]) + 1))

    images_to_process = []
    for i in pages:
        img_name = f'IMG_{i:04d}.jpg'
        img_path = os.path.join(IMAGE_DIR, img_name)
        if os.path.exists(img_path):
            images_to_process.append((img_path, f'IMG_{i:04d}'))
        else:
            print(f'[SKIP] {img_name} not found')

    if not images_to_process:
        print('No images found to process.')
        return

    total = len(images_to_process)
    print(f'Processing {total} bhashatattwa page(s)')
    print('Loading models...')

    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    detection_predictor = DetectionPredictor()
    print('Models loaded. Starting OCR...\n')

    for idx, (img_path, basename) in enumerate(images_to_process, 1):
        out_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        if os.path.exists(out_path):
            print(f'[{idx}/{total}] {basename} — already exists, skipping.')
            continue

        t0 = time.time()
        print(f'[{idx}/{total}] {basename} — processing...', end=' ', flush=True)
        try:
            image = Image.open(img_path)
            lines = ocr_full_page(image, recognition_predictor, detection_predictor)
            output_text = '\n'.join(lines)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(output_text)
            elapsed = time.time() - t0
            print(f'done ({elapsed:.1f}s, {len(lines)} lines)')
        except Exception as e:
            print(f'ERROR: {e}')
        finally:
            gc.collect()

    print(f'\nOCR complete. Text files → {TEXT_DIR}')


if __name__ == '__main__':
    main()
