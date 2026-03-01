# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
OCR + Parse pipeline for split dictionary page images.
Reads pre-split images from SplitImages/, runs Surya OCR in batches,
filters headers/footers, parses dictionary entries into JSON.

Usage: python ocr_and_parse.py [start_page] [end_page]
  Default: 40 49 (first 10 pages)
"""
import sys
import os
import re
import json
import time
import gc
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from PIL import Image
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
SPLIT_DIR = os.path.join(BASE_DIR, 'SplitImages')
TEXT_DIR = os.path.join(BASE_DIR, 'ExtractedText')
JSON_DIR = os.path.join(BASE_DIR, 'ParsedJSON')

os.makedirs(TEXT_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

OCR_BATCH_SIZE = 8  # Number of column images per OCR batch call (4 pages)
PAGES_PER_BATCH = OCR_BATCH_SIZE // 2  # Each page has left + right

# ── Header / Footer filtering ──────────────────────────────────────────────

FOOTER_STRINGS = [
    'বরাক উপত্যকার আঞ্চলিক বাংলা ভাষার অভিধান ও ভাষাতত্ত্ব',
    'বরাক উপত্যকার আঞ্চলি',
    'াঞ্চলিক বাংলা ভাষার অভিধান',
    'ভাষার অভিধান ও ভাষাতত্ত্ব',
    'বাংলা ভাষার অভিধান ও ভাষাতত্ত্ব',
    'বরাক উপত্যকার আঞ্চলিক বাংলা ভ',
    'উপত্যকার আঞ্চলিক বাংলা',
    'আঞ্চলিক বাংলা ভাষার',
]


def is_footer_line(line):
    """Check if a line is part of the footer text."""
    stripped = line.strip()
    if not stripped:
        return False
    for fp in FOOTER_STRINGS:
        if fp in stripped:
            return True
    return False


def is_page_number(line):
    """Check if a line is just a page number (Bengali or Arabic digits)."""
    stripped = line.strip()
    return bool(re.match(r'^[০-৯0-9]+$', stripped))


def is_header_line(line):
    """Check if a line looks like a header word (single short Bengali word, no markers)."""
    stripped = line.strip()
    if len(stripped) > 25:
        return False
    # Pure Bengali word(s), no brackets, no dash, no transliteration
    if re.match(r'^[\u0980-\u09FF\s]+$', stripped):
        # No POS markers or definition indicators
        if not any(c in stripped for c in ['—', '[', ']', '⇒', '≫', '→', '.']):
            return True
    return False


def filter_lines(lines):
    """
    Remove header lines (first 1-2 lines if they look like headers/page numbers)
    and footer lines (last few lines matching footer pattern).
    Returns filtered list of lines.
    """
    if not lines:
        return lines

    # ── Remove footer lines from the end ──
    # Walk backwards, remove footer and page-number lines
    end = len(lines)
    while end > 0:
        line = lines[end - 1].strip()
        if not line or is_footer_line(lines[end - 1]) or is_page_number(lines[end - 1]):
            end -= 1
        else:
            break
    lines = lines[:end]

    # ── Remove header lines from the start ──
    # First 1-2 lines: skip page numbers and single header words
    start = 0
    headers_skipped = 0
    while start < len(lines) and headers_skipped < 3:
        line = lines[start].strip()
        if not line:
            start += 1
            continue
        if is_page_number(lines[start]):
            start += 1
            headers_skipped += 1
            continue
        if headers_skipped < 2 and is_header_line(lines[start]):
            start += 1
            headers_skipped += 1
            continue
        break

    return lines[start:]


# ── Dictionary entry parsing ───────────────────────────────────────────────

# Part of speech abbreviations
POS_MARKERS = [
    'বি.', 'বিণ.', 'ক্রি.', 'অনম্ব.', 'অনন্ব.', 'ক্রিবিণ.', 'সক্রি.',
    'ক্রিভক্তি.', 'বাগধা. বি.', 'প্রাতি.', 'যোজ.', 'সর্ব.', 'ধাতু',
    'অব্য.', 'না.', 'সংযো.', 'নি.', 'ক্রিবিশ.', 'অ.', 'স.',
    'বাগধা. ক্রি.', 'বাগধা.',
]

# Regex to detect <b>headword</b> followed by transliteration (a new entry inline)
# Examples:
#   <b>অধ দেবা</b> odh deba [<ববাং অধ + √ দে]
#   <b>অনতে</b> ɔnte [<বাং অন্তরে = তরে]
#   <b>আউকির বাদা</b> — বাগধা.
#   <b>আরা</b>, ara  (comma between tag and transliteration)
#   <b>আওআ</b>্ব aŏa  (Bengali char stuck after closing tag)
BOLD_ENTRY_RE = re.compile(
    r'<b>([\u0980-\u09FF][\u0980-\u09FF\s\u09CD`,.।\'-]*?)</b>'  # bold Bengali headword
    r'([\u0980-\u09FF\u09CD]*)'    # possible trailing Bengali chars stuck to </b>
    r'\s*'
    r'(.*)',  # rest of line (transliteration, etymology, POS, etc.)
    re.UNICODE
)

# A headword line typically has: Bengali word + roman transliteration + optional [etymology]
# Examples:
#   "কেউচা keuca [< বাং কিঁউচা]"
#   "হংগা, hunga [< ববাং √হং..."  (comma after headword)
#   "আরা¸ ara [<ববাং হারা..."     (cedilla after headword)
#   "আটি, ați [<বাং আঁটি]"
HEADWORD_RE = re.compile(
    r'^([\u0980-\u09FF][\u0980-\u09FF\s\u09CD]*?)'   # Bengali headword
    r'[,।¸\.]*'                                        # optional trailing punctuation (comma, cedilla, period, danda)
    r'\s+'
    r'([a-zA-Zɔəŏŭĭǔɪʒţțⅆ∫⊃∭ɛāīūṛṭḍṇśṣñôêŋ]+(?:\s+[a-zA-Zɔəŏŭĭǔɪʒţțⅆ∫⊃∭ɛāīūṛṭḍṇśṣñôêŋ]+)*)'  # transliteration
    r'(.*)',                                            # rest of line
    re.UNICODE
)

SENSE_NUM_RE = re.compile(r'^([১২৩৪৫৬৭৮৯০]+)\.\s*(.*)')

# Regex to detect POS marker + em-dash — (sense boundary within an entry)
# Sorted longest-first so compound POS like "বাগধা. বি." match before "বি."
_pos_pattern = '|'.join(re.escape(p) for p in sorted(POS_MARKERS, key=len, reverse=True))
POS_DASH_RE = re.compile(
    r'(' + _pos_pattern + r')\s*—\s*(.*)',
    re.UNICODE
)


def split_bold_entries(lines):
    """Pre-process OCR lines: split lines at <b>headword</b> boundaries.
    
    When a line contains <b>word</b> followed by transliteration or POS,
    the text before the <b> tag belongs to the previous entry, and
    <b>word</b> ... starts a new entry.
    
    Returns a new list of lines with bold entries on separate lines,
    and <b>/<\b> tags stripped.
    """
    result = []
    for line in lines:
        # Find all <b>...</b> occurrences that look like new entries
        # We search for <b>BengaliWord</b> followed by either
        #   - a transliteration (roman chars)
        #   - a POS marker (— বি., etc.)
        #   - nothing substantial (just the bold word as sub-entry header)
        
        # First, strip any <b>...</b> that appears at the very start of the line
        # (these are primary headwords, already at line start)
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        
        # Look for <b>...</b> patterns that indicate new entries
        # Split the line at these boundaries
        parts = re.split(r'(?=<b>[\u0980-\u09FF])', stripped)
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Check if this part starts with a bold entry marker
            m = BOLD_ENTRY_RE.match(part)
            if m:
                # Extract headword + any trailing Bengali chars stuck to </b>
                headword = m.group(1).strip() + m.group(2)
                rest = m.group(3).strip()
                # Strip leading punctuation/noise between headword and transliteration
                # e.g. "<b>আরা</b>, ara" → rest starts with ", ara"
                rest = rest.lstrip(',.;:।¸ ')
                if i > 0:
                    # This is a new entry that was inline — emit as new line
                    result.append(f'{headword} {rest}' if rest else headword)
                else:
                    # Bold entry at start of line — just clean the tags
                    result.append(f'{headword} {rest}' if rest else headword)
            else:
                # Regular text, strip any stray <b>/<\/b> tags
                clean = re.sub(r'</?b>', '', part).strip()
                if clean:
                    result.append(clean)
    
    return result


def parse_entries(lines):
    """Parse filtered OCR lines into a list of dictionary entry dicts.
    First splits at <b>headword</b> boundaries, then parses entries.
    """
    # Pre-process: split at bold entry boundaries
    lines = split_bold_entries(lines)
    
    entries = []
    current = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip noise: pure numbers, very short garbage
        if re.match(r'^[0-9\s]+$', stripped):
            continue

        # Try matching a headword line
        m = HEADWORD_RE.match(stripped)
        if m:
            # Save previous entry
            if current:
                entries.append(finalize_entry(current))

            headword = m.group(1).strip()
            translit = m.group(2).strip()
            rest = m.group(3).strip()

            current = {
                'headword': headword,
                'transliteration': translit,
                'rest_lines': [rest] if rest else [],
            }
        elif current:
            current['rest_lines'].append(stripped)
        else:
            # Lines before first headword — continuation from previous page
            current = {
                'headword': '_continuation',
                'transliteration': '',
                'rest_lines': [stripped],
            }

    if current:
        entries.append(finalize_entry(current))

    return entries


def extract_cross_refs(text):
    """Extract cross-reference words from text containing দ্র."""
    refs = []
    for m in re.finditer(r'দ্র\.\s*([\u0980-\u09FF\s০-৯ৢ]+)', text):
        raw = m.group(1).strip()
        for r in re.split(r'[,;]', raw):
            r = r.strip().rstrip('।').strip()
            if r and len(r) > 1:
                refs.append(r)
    return refs


def finalize_entry(entry):
    """Extract structured fields from raw entry lines.

    Returns dict with:
      headword, transliteration, etymology (optional),
      senses: [{part_of_speech, definition, examples[], cross_references[]}]

    Each POS + — boundary in the OCR text starts a new sense.
    """
    clean_lines = [re.sub(r'</?b>', '', l) for l in entry.get('rest_lines', [])]
    all_text = ' '.join(l.strip() for l in clean_lines if l.strip())

    result = {
        'headword': re.sub(r'</?b>', '', entry['headword']).strip(),
        'transliteration': entry['transliteration'],
    }

    # ── Etymology (entry-level, appears once) ──
    etym_match = re.search(r'\[([^\]]*)\]', all_text)
    if etym_match:
        result['etymology'] = '[' + etym_match.group(1) + ']'
    else:
        # Fallback: OCR missed closing ] — take [< ... up to first POS—
        open_match = re.search(r'\[<', all_text)
        if open_match:
            rest = all_text[open_match.start():]
            end_match = POS_DASH_RE.search(rest)
            if end_match:
                etym_text = rest[:end_match.start()].strip()
                if etym_text:
                    result['etymology'] = etym_text + ']'

    # ── Build senses array by walking lines sequentially ──
    senses = []
    current_sense = None
    last_was_example = False

    for line in clean_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for POS + — pattern (new sense boundary)
        pos_match = POS_DASH_RE.search(stripped)
        if pos_match:
            # Save previous sense
            if current_sense:
                senses.append(current_sense)

            pos = pos_match.group(1).strip()
            definition = pos_match.group(2).strip()
            current_sense = {'part_of_speech': pos}
            if definition:
                current_sense['definition'] = definition
                # Inline cross-references in definition
                if 'দ্র.' in definition:
                    xrefs = extract_cross_refs(definition)
                    if xrefs:
                        current_sense['cross_references'] = xrefs
            last_was_example = False
            continue

        # Example line (⇒)
        if stripped.startswith('⇒'):
            example = stripped[1:].strip()
            if current_sense and example:
                current_sense.setdefault('examples', []).append(example)
            last_was_example = True
            continue

        # Reference/note line (≫)
        if stripped.startswith('≫'):
            note = stripped[1:].strip()
            if current_sense and 'দ্র.' in note:
                xrefs = extract_cross_refs(note)
                current_sense.setdefault('cross_references', []).extend(xrefs)
            last_was_example = False
            continue

        # Standalone cross-reference line (দ্র. ...)
        if stripped.startswith('দ্র.') and current_sense:
            xrefs = extract_cross_refs(stripped)
            current_sense.setdefault('cross_references', []).extend(xrefs)
            last_was_example = False
            continue

        # Skip etymology-only lines (already extracted above)
        if stripped.startswith('[') or stripped.startswith('< '):
            continue

        # Continuation of previous content
        if current_sense:
            if last_was_example and current_sense.get('examples'):
                # Append to last example
                current_sense['examples'][-1] += ' ' + stripped
            else:
                # Append to definition
                if current_sense.get('definition'):
                    current_sense['definition'] += ' ' + stripped
                else:
                    current_sense['definition'] = stripped
                last_was_example = False
        # else: pre-POS text (etymology continuation etc.) — skip

    # Save last sense
    if current_sense:
        senses.append(current_sense)

    # Fallback if no senses found
    if not senses and all_text.strip():
        senses.append({'raw_text': all_text.strip()})

    result['senses'] = senses
    return result


# ── OCR pipeline ───────────────────────────────────────────────────────────

def run_ocr_batch(images, recognition_predictor, detection_predictor):
    """Run Surya OCR on a batch of PIL images.
    Returns list of lists of text lines (one per image).
    """
    preds = recognition_predictor(images, det_predictor=detection_predictor)
    results = []
    for pred in preds:
        lines = [tl.text for tl in pred.text_lines]
        results.append(lines)
    return results


def process_pages(start_page, end_page):
    """Full pipeline: load split images → OCR → filter → parse → JSON.
    Uses batched OCR (4 pages = 8 images at once) for speed,
    with threaded image pre-loading and background saving.
    Saves results page-by-page for crash safety.
    """
    print(f'Processing pages {start_page}-{end_page}')
    print(f'Split images from: {SPLIT_DIR}')

    # Verify which pages have split images
    pages = []
    for page_num in range(start_page, end_page + 1):
        basename = f'IMG_{page_num:04d}'
        left = os.path.join(SPLIT_DIR, f'{basename}_left.jpg')
        right = os.path.join(SPLIT_DIR, f'{basename}_right.jpg')
        if os.path.exists(left) or os.path.exists(right):
            pages.append(page_num)

    print(f'Found {len(pages)} pages with split images')

    if not pages:
        print('No images found!')
        return

    # ── Load OCR models ──
    print('\nLoading OCR models...')
    t0 = time.time()
    foundation = FoundationPredictor()
    rec_predictor = RecognitionPredictor(foundation)
    det_predictor = DetectionPredictor()
    print(f'Models loaded in {time.time() - t0:.1f}s')

    # ── Helper: load images for a batch of pages ──
    def load_batch_images(page_batch):
        """Load left+right images for a list of page numbers.
        Returns list of (page_num, side, PIL.Image) tuples.
        """
        jobs = []
        for page_num in page_batch:
            basename = f'IMG_{page_num:04d}'
            for side in ['left', 'right']:
                path = os.path.join(SPLIT_DIR, f'{basename}_{side}.jpg')
                if os.path.exists(path):
                    jobs.append((page_num, side, Image.open(path)))
        return jobs

    # ── Helper: save results for one page ──
    def save_page_results(page_num, side_lines):
        """Filter, parse, save text and JSON for a single page."""
        basename = f'IMG_{page_num:04d}'

        # Save extracted text
        text_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        with open(text_path, 'w', encoding='utf-8') as f:
            left_lines = side_lines.get('left', [])
            right_lines = side_lines.get('right', [])
            f.write('=== বাম কলাম (LEFT COLUMN) ===\n')
            f.write('\n'.join(left_lines))
            f.write('\n\n=== ডান কলাম (RIGHT COLUMN) ===\n')
            f.write('\n'.join(right_lines))

        # Filter and parse entries
        page_entries = []
        for side in ['left', 'right']:
            if side not in side_lines:
                continue
            filtered = filter_lines(side_lines[side])
            entries = parse_entries(filtered)
            page_entries.extend(entries)

        # Save per-page JSON
        json_path = os.path.join(JSON_DIR, f'{basename}_entries.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(page_entries, f, ensure_ascii=False, indent=2)

        return page_entries

    # ── Split pages into batches of PAGES_PER_BATCH ──
    page_batches = []
    for i in range(0, len(pages), PAGES_PER_BATCH):
        page_batches.append(pages[i:i + PAGES_PER_BATCH])

    all_entries = []
    page_entry_counts = []
    failed_pages = []
    total_ocr_time = 0

    # Use thread pool for concurrent I/O (image loading + result saving)
    with ThreadPoolExecutor(max_workers=2) as io_pool:
        # Pre-load first batch
        preload_future = io_pool.submit(load_batch_images, page_batches[0])

        for batch_idx, page_batch in enumerate(page_batches):
            batch_desc = f'IMG_{page_batch[0]:04d}-IMG_{page_batch[-1]:04d}'
            print(f'\n── Batch {batch_idx+1}/{len(page_batches)}: {batch_desc} ({len(page_batch)} pages) ──')

            try:
                # Get pre-loaded images (or load synchronously if first/error)
                if preload_future is not None:
                    jobs = preload_future.result()
                    preload_future = None
                else:
                    jobs = load_batch_images(page_batch)

                if not jobs:
                    print('  SKIP (no images)')
                    continue

                # Start pre-loading NEXT batch in background
                if batch_idx + 1 < len(page_batches):
                    preload_future = io_pool.submit(load_batch_images, page_batches[batch_idx + 1])

                # Run OCR on all images in this batch at once
                batch_images = [img for _, _, img in jobs]
                print(f'  OCR on {len(batch_images)} images...', end=' ', flush=True)
                t1 = time.time()
                ocr_results = run_ocr_batch(batch_images, rec_predictor, det_predictor)
                ocr_time = time.time() - t1
                total_ocr_time += ocr_time
                print(f'{ocr_time:.1f}s')

                # Group results by page
                page_side_lines = {}  # page_num → {side: [lines]}
                for (page_num, side, _), lines in zip(jobs, ocr_results):
                    if page_num not in page_side_lines:
                        page_side_lines[page_num] = {}
                    page_side_lines[page_num][side] = lines

                # Close all images to free memory
                for _, _, img in jobs:
                    img.close()
                del jobs, batch_images
                gc.collect()

                # Save each page's results (use threads for I/O parallelism)
                save_futures = []
                for page_num in page_batch:
                    if page_num not in page_side_lines:
                        continue
                    save_futures.append(
                        (page_num, io_pool.submit(save_page_results, page_num, page_side_lines[page_num]))
                    )

                # Collect results from saves
                for page_num, future in save_futures:
                    try:
                        page_entries = future.result()
                        basename = f'IMG_{page_num:04d}'
                        all_entries.extend(page_entries)
                        page_entry_counts.append((basename, len(page_entries)))
                        print(f'  {basename}: {len(page_entries)} entries')
                    except Exception as e:
                        basename = f'IMG_{page_num:04d}'
                        print(f'  {basename}: SAVE ERROR: {e}')
                        failed_pages.append((basename, str(e)))

                del page_side_lines
                gc.collect()

            except Exception as e:
                print(f'  BATCH ERROR: {e}')
                traceback.print_exc()
                for pn in page_batch:
                    failed_pages.append((f'IMG_{pn:04d}', str(e)))
                gc.collect()
                # Reset preload for next batch
                if batch_idx + 1 < len(page_batches):
                    preload_future = io_pool.submit(load_batch_images, page_batches[batch_idx + 1])
                continue

    # Save combined JSON
    combined_path = os.path.join(JSON_DIR, f'entries_pages_{start_page:04d}_{end_page:04d}.json')
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*50}')
    print(f'Done! {len(all_entries)} entries from {len(page_entry_counts)} pages.')
    print(f'Total OCR time: {total_ocr_time:.1f}s (avg {total_ocr_time/max(len(page_entry_counts),1):.1f}s/page)')
    print(f'Per-page JSONs: {JSON_DIR}/')
    print(f'Combined JSON:  {combined_path}')
    if failed_pages:
        print(f'\nFailed pages ({len(failed_pages)}):')
        for name, err in failed_pages:
            print(f'  {name}: {err}')
    print(f'\nPer-page breakdown:')
    for name, count in page_entry_counts:
        print(f'  {name}: {count} entries')


def reparse_pages(start_page, end_page):
    """Re-parse existing extracted text files without re-running OCR.
    Reads ExtractedText/*.txt, applies updated parser, saves new JSONs.
    """
    print(f'Re-parsing pages {start_page}-{end_page} (no OCR)')

    all_entries = []
    page_entry_counts = []

    for page_num in range(start_page, end_page + 1):
        basename = f'IMG_{page_num:04d}'
        text_path = os.path.join(TEXT_DIR, f'{basename}_extracted_text.txt')
        if not os.path.exists(text_path):
            continue

        with open(text_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the extracted text file format:
        # === বাম কলাম (LEFT COLUMN) ===
        # ...lines...
        #
        # === ডান কলাম (RIGHT COLUMN) ===
        # ...lines...
        page_entries = []
        for section in content.split('=== '):
            if not section.strip():
                continue
            # Skip the header line (e.g. "বাম কলাম (LEFT COLUMN) ===")
            lines = section.split('\n')
            if lines:
                lines = lines[1:]  # skip section header
            filtered = filter_lines(lines)
            entries = parse_entries(filtered)
            page_entries.extend(entries)

        # Save per-page JSON
        json_path = os.path.join(JSON_DIR, f'{basename}_entries.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(page_entries, f, ensure_ascii=False, indent=2)

        all_entries.extend(page_entries)
        page_entry_counts.append((basename, len(page_entries)))
        print(f'  {basename}: {len(page_entries)} entries')

    # Save combined JSON
    combined_path = os.path.join(JSON_DIR, f'entries_pages_{start_page:04d}_{end_page:04d}.json')
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*50}')
    print(f'Done! {len(all_entries)} entries from {len(page_entry_counts)} pages.')
    print(f'Combined JSON:  {combined_path}')
    print(f'\nPer-page breakdown:')
    for name, count in page_entry_counts:
        print(f'  {name}: {count} entries')


if __name__ == '__main__':
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 49

    # --reparse flag: re-parse existing text without OCR
    if '--reparse' in sys.argv:
        reparse_pages(start, end)
    else:
        process_pages(start, end)
