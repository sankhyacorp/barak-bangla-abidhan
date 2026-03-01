# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Test Marker OCR on images 587-588 (linguistics pages with tables/lists).
Converts images to PDF first (Marker requires PDF input), then extracts
structured Markdown preserving layout (tables, lists, columns).
"""
import os
import io
import gc
import time
from PIL import Image

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
IMAGE_DIR = os.path.join(BASE_DIR, 'Images',
    'Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy')
OUT_DIR = os.path.join(BASE_DIR, 'marker_test')
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [588]  # 587 already done


def image_to_pdf_bytes(img_path):
    """Convert a single image to an in-memory PDF."""
    img = Image.open(img_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='PDF')
    buf.seek(0)
    return buf


def main():
    print("Loading Marker models (first run may download models)...")
    t0 = time.time()

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    config_parser = ConfigParser({"output_format": "markdown"})
    artifact_dict = create_model_dict()
    converter = PdfConverter(
        artifact_dict=artifact_dict,
        config=config_parser.generate_config_dict(),
    )
    print(f"Models loaded in {time.time()-t0:.1f}s\n")

    for page_num in PAGES:
        img_name = f'IMG_{page_num:04d}.jpg'
        img_path = os.path.join(IMAGE_DIR, img_name)
        if not os.path.exists(img_path):
            print(f"[SKIP] {img_name} not found")
            continue

        print(f"Processing {img_name}...", end=' ', flush=True)
        t1 = time.time()

        try:
            # Convert image → PDF in memory, pass BytesIO to Marker
            pdf_buf = image_to_pdf_bytes(img_path)
            result = converter(pdf_buf)
            md_text = result.markdown

            out_path = os.path.join(OUT_DIR, f'IMG_{page_num:04d}_marker.md')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(md_text)

            elapsed = time.time() - t1
            lines = md_text.count('\n') + 1
            print(f"done ({elapsed:.1f}s, {lines} lines)")
            print(f"  → {out_path}")
            print(f"  Preview:\n{'='*60}")
            preview = md_text[:2000]
            print(preview)
            if len(md_text) > 2000:
                print(f"  ... ({len(md_text) - 2000} more chars)")
            print('='*60 + '\n')

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        # Free memory between pages
        gc.collect()

    print("Done.")

if __name__ == '__main__':
    main()
