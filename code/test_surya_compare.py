# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Compare Surya (raw) vs Marker on pages 587-588.
Run Surya OCR on these pages using the same approach as our existing pipeline.
"""
import os
import gc
import time
from PIL import Image

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
IMAGE_DIR = os.path.join(BASE_DIR, 'Images',
    'Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
OUT_DIR = os.path.join(BASE_DIR, 'marker_test')
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [587, 588]

def main():
    print("Loading Surya models...")
    t0 = time.time()
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor

    foundation = FoundationPredictor()
    det = DetectionPredictor()
    rec = RecognitionPredictor(foundation)
    print(f"Models loaded in {time.time()-t0:.1f}s\n")

    for page_num in PAGES:
        img_name = f'IMG_{page_num:04d}.jpg'
        img_path = os.path.join(IMAGE_DIR, img_name)
        if not os.path.exists(img_path):
            print(f"[SKIP] {img_name} not found")
            continue

        print(f"Processing {img_name}...", end=' ', flush=True)
        t1 = time.time()

        img = Image.open(img_path)
        w, h = img.size
        # Crop header/footer (3%/97%)
        crop_top = int(h * 0.03)
        crop_bot = int(h * 0.97)
        cropped = img.crop((0, crop_top, w, crop_bot))

        det_results = rec([cropped], det_predictor=det)

        lines = []
        for line in det_results[0].text_lines:
            text = line.text.strip()
            if text:
                lines.append(text)

        result_text = '\n'.join(lines)
        out_path = os.path.join(OUT_DIR, f'IMG_{page_num:04d}_surya.txt')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(result_text)

        elapsed = time.time() - t1
        print(f"done ({elapsed:.1f}s, {len(lines)} lines)")
        print(f"  → {out_path}")
        print(f"  Preview:\n{'='*60}")
        print(result_text[:2000])
        if len(result_text) > 2000:
            print(f"  ... ({len(result_text) - 2000} more chars)")
        print('='*60 + '\n')

        gc.collect()

    print("Done.")

if __name__ == '__main__':
    main()
