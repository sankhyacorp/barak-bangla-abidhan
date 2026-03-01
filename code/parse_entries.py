# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Parse extracted OCR text from dictionary pages into structured JSON entries.
Handles two-column layout, filters headers/footers/noise, identifies entry boundaries.
"""
import os, re, json, sys, glob

BASE_DIR = r'c:\Users\sankhyac\Downloads\Dict'
TEXT_DIR = os.path.join(BASE_DIR, 'ExtractedText')
JSON_DIR = os.path.join(BASE_DIR, 'ParsedJSON')
os.makedirs(JSON_DIR, exist_ok=True)

# Footer pattern to filter out
FOOTER_PATTERNS = [
    r'বরাক উপত্যকার আঞ্চলি',
    r'াঞ্চলিক বাংলা ভাষার অভিধান',
    r'ক বাংলা ভাষার অভিধান',
    r'লক বাংলা ভাষার অভিধান',
    r'ভাষার অভিধান ও ভাষাতত্ত্ব',
    r'বাংলা ভাষার অভিধান ও ভাষাতত্ত্ব',
    r'বরাক উপত্যকার আঞ্চলিক বাংলা ভ',
]

# Part of speech abbreviations used in this dictionary
POS_MARKERS = [
    'বি.', 'বিণ.', 'ক্রি.', 'অনম্ব.', 'অনন্ব.', 'ক্রিবিণ.', 'সক্রি.',
    'ক্রিভক্তি.', 'বাগধা. বি.', 'প্রাতি.', 'যোজ.', 'সর্ব.', 'ধাতু',
    'অব্য.', 'না.', 'সংযো.', 'নি.', 'ক্রিবিশ.',
]

# Pattern to detect a headword line: Bengali word followed by transliteration
# Examples: "কেওলা keŏla [< ববাং শব্দ কেওলা]"
# or: "অআ oa [<বাং √ হ]"
HEADWORD_PATTERN = re.compile(
    r'^(?:<b>)?'                          # optional bold tag
    r'([\u0980-\u09FF\s\.]+?)'            # Bengali headword (group 1)
    r'(?:</b>)?'                          # optional bold close
    r'[\s,¸]*'                            # optional whitespace/punctuation
    r'([a-zA-Zɔəŏŭĭǔɪʒţțⅆ∫⊃∭ɛ]+(?:\s+[a-zA-Zɔəŏŭĭǔɪʒţțⅆ∫⊃∭ɛ]+)*)'  # transliteration (group 2)
    r'\s*'
    r'(\[.*)?$'                           # optional etymology bracket (group 3)
)

# Pattern for sense numbers like "১." "২." etc.
SENSE_NUM_PATTERN = re.compile(r'^([১২৩৪৫৬৭৮৯০]+)\.\s*(.*)')

# Noise patterns — stray characters from bleed-through or OCR errors
NOISE_PATTERNS = [
    re.compile(r'^[0-9]+$'),                    # bare numbers
    re.compile(r'^[१-९॥।]+$'),                  # Devanagari numbers
    re.compile(r'^[\u0900-\u097F\s]+$'),         # pure Devanagari lines
    re.compile(r'^[Ŷìîïüö]+$'),                 # stray diacritical chars
    re.compile(r'^={3,}'),                       # column markers
    re.compile(r'^\s*$'),                        # blank lines
]


def is_noise(line):
    """Check if a line is noise (header, footer, stray chars)."""
    stripped = line.strip()
    if not stripped:
        return True
    # Footer
    for fp in FOOTER_PATTERNS:
        if fp in stripped:
            return True
    # Noise patterns
    for np in NOISE_PATTERNS:
        if np.match(stripped):
            return True
    # Very short fragments that are likely bleed-through from other column
    # (single incomplete Bengali word fragments)
    if len(stripped) <= 3 and not re.match(r'^[\u0980-\u09FF]', stripped):
        return True
    return False


def is_page_number(line):
    """Check if a line is just a page number."""
    stripped = line.strip()
    # Bengali digits or Arabic digits
    return bool(re.match(r'^[০-৯0-9]+$', stripped))


def is_header_word(line, is_first_content_line=False):
    """
    Check if a line is a header word (single Bengali word at top of column).
    Headers are typically 1-2 words without any transliteration or markers.
    """
    stripped = line.strip()
    # Must be short, pure Bengali, no brackets, no markers
    if is_first_content_line and len(stripped) < 20:
        if re.match(r'^[\u0980-\u09FF\s]+$', stripped):
            # No POS markers, no arrows, no brackets
            if not any(m in stripped for m in ['⇒', '≫', '→', '[', ']', '—', '.']):
                return True
    return False


def parse_column(lines):
    """
    Parse lines from a single column into raw entry blocks.
    Returns list of entry dicts.
    """
    entries = []
    current_entry = None
    content_started = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue

        # Skip noise
        if is_noise(stripped):
            continue

        # Skip page numbers
        if is_page_number(stripped):
            continue

        # Skip header words (first content line of column)
        if not content_started:
            if is_header_word(stripped, is_first_content_line=True):
                content_started = True
                continue
            content_started = True

        # Try to match headword pattern
        # Clean HTML tags for matching but preserve original
        clean_line = re.sub(r'</?b>', '', stripped)
        clean_line = re.sub(r'[¸⊃]', '', clean_line).strip()

        match = HEADWORD_PATTERN.match(clean_line)
        if match:
            # Save previous entry
            if current_entry:
                entries.append(current_entry)

            headword = match.group(1).strip()
            transliteration = match.group(2).strip()
            etymology_part = match.group(3) or ''

            current_entry = {
                'headword': headword,
                'transliteration': transliteration,
                'etymology': etymology_part.strip(),
                'raw_lines': [stripped],
            }
        elif current_entry:
            current_entry['raw_lines'].append(stripped)
        else:
            # Lines before first entry (could be continuation from previous page)
            if not entries and not current_entry:
                current_entry = {
                    'headword': '_continuation',
                    'transliteration': '',
                    'etymology': '',
                    'raw_lines': [stripped],
                }

    # Don't forget last entry
    if current_entry:
        entries.append(current_entry)

    return entries


def extract_entry_details(entry):
    """
    From raw_lines, extract part_of_speech, definition, examples, notes, cross_references.
    """
    raw_lines = entry.get('raw_lines', [])
    if not raw_lines:
        return entry

    # Join all lines for easier parsing
    all_text = ' '.join(raw_lines)

    # Extract etymology if not already captured
    if not entry.get('etymology'):
        etym_match = re.search(r'\[([^\]]*)\]', all_text)
        if etym_match:
            entry['etymology'] = '[' + etym_match.group(1) + ']'
    else:
        # Complete etymology if the bracket wasn't closed
        if '[' in entry['etymology'] and ']' not in entry['etymology']:
            for line in raw_lines[1:]:
                entry['etymology'] += ' ' + line
                if ']' in line:
                    entry['etymology'] = entry['etymology'][:entry['etymology'].index(']')+1]
                    break

    # Parse line by line for structure
    part_of_speech = ''
    definitions = []
    examples = []
    notes = []
    cross_refs = []
    current_section = 'definition'

    for line in raw_lines[1:]:  # skip headword line
        stripped = line.strip()
        if not stripped:
            continue

        # Remove HTML tags
        stripped = re.sub(r'</?b>', '', stripped)

        # Check for cross references
        dr_match = re.search(r'দ্র\.\s*([\u0980-\u09FF\s,]+)', stripped)
        if dr_match:
            refs = [r.strip() for r in dr_match.group(1).split(',') if r.strip()]
            cross_refs.extend(refs)

        # Check for examples (⇒)
        if stripped.startswith('⇒'):
            example_text = stripped[1:].strip()
            examples.append(example_text)
            current_section = 'example'
            continue

        # Check for notes/comparisons (→ or ≫)
        if stripped.startswith('→') or stripped.startswith('≫'):
            note_text = stripped[1:].strip()
            notes.append(note_text)
            current_section = 'note'
            continue

        # Check for POS and definition (marked with —)
        pos_def_match = re.match(r'([\u0980-\u09FF\.\s]+)\s*—\s*(.*)', stripped)
        if pos_def_match:
            pos_candidate = pos_def_match.group(1).strip()
            def_text = pos_def_match.group(2).strip()
            if any(pos_candidate.endswith(p.rstrip('.')) or pos_candidate == p for p in POS_MARKERS) or \
               any(p in pos_candidate for p in POS_MARKERS):
                part_of_speech = pos_candidate
                if def_text:
                    definitions.append(def_text)
                current_section = 'definition'
                continue

        # Check for sense numbers
        sense_match = SENSE_NUM_PATTERN.match(stripped)
        if sense_match:
            rest = sense_match.group(2).strip()
            if rest:
                # Could be POS + definition
                definitions.append(stripped)
            continue

        # Continuation of previous section
        if current_section == 'example' and examples:
            examples[-1] += ' ' + stripped
        elif current_section == 'note' and notes:
            notes[-1] += ' ' + stripped
        elif current_section == 'definition':
            definitions.append(stripped)

    # Build final entry (remove raw_lines)
    result = {
        'headword': entry['headword'],
        'transliteration': entry['transliteration'],
        'etymology': entry.get('etymology', ''),
    }

    if part_of_speech:
        result['part_of_speech'] = part_of_speech
    if definitions:
        result['definition'] = ' '.join(definitions)
    if examples:
        result['examples'] = examples
    if notes:
        result['notes'] = ' '.join(notes)
    if cross_refs:
        result['cross_references'] = cross_refs

    return result


def process_file(text_path):
    """Process a single extracted text file into JSON entries."""
    with open(text_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into left and right columns
    left_lines = []
    right_lines = []
    current_column = None

    for line in content.split('\n'):
        if 'LEFT COLUMN' in line or 'বাম কলাম' in line:
            current_column = 'left'
            continue
        elif 'RIGHT COLUMN' in line or 'ডান কলাম' in line:
            current_column = 'right'
            continue

        if current_column == 'left':
            left_lines.append(line)
        elif current_column == 'right':
            right_lines.append(line)

    # Parse each column
    left_entries = parse_column(left_lines)
    right_entries = parse_column(right_lines)

    # Combine: left column first, then right column
    all_entries = left_entries + right_entries

    # Extract details for each entry
    parsed_entries = []
    for entry in all_entries:
        parsed = extract_entry_details(entry)
        # Skip empty continuation entries or entries with no useful content
        if parsed.get('headword') == '_continuation' and not parsed.get('definition'):
            continue
        parsed_entries.append(parsed)

    return parsed_entries


def main():
    if len(sys.argv) > 1:
        # Process specific files
        files = sys.argv[1:]
    else:
        # Process all extracted text files
        files = sorted(glob.glob(os.path.join(TEXT_DIR, 'IMG_*_extracted_text.txt')))

    total = len(files)
    all_entries_combined = []

    for idx, fpath in enumerate(files, 1):
        basename = os.path.basename(fpath).replace('_extracted_text.txt', '')
        print(f'[{idx}/{total}] Parsing {basename}...', end=' ')

        try:
            entries = process_file(fpath)
            print(f'{len(entries)} entries found')

            # Save individual JSON
            json_path = os.path.join(JSON_DIR, f'{basename}_entries.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)

            all_entries_combined.extend(entries)
        except Exception as e:
            print(f'ERROR: {e}')

    # Save combined JSON
    combined_path = os.path.join(JSON_DIR, 'all_entries_combined.json')
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_entries_combined, f, ensure_ascii=False, indent=2)

    print(f'\nDone. {len(all_entries_combined)} total entries across {total} pages.')
    print(f'Individual JSONs: {JSON_DIR}')
    print(f'Combined JSON: {combined_path}')


if __name__ == '__main__':
    main()
