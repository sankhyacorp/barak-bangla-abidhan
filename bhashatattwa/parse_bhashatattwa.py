# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Parse OCR-extracted text for ভাষাতত্ত্ব pages into structured JSON with
formatting annotations (headings, paragraphs, examples, tables, citations).

This is the intelligence layer: it reads raw OCR lines and detects structure.

Usage: python parse_bhashatattwa.py
"""
import os, re, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_DIR = os.path.join(BASE_DIR, 'ExtractedText')
JSON_DIR = os.path.join(BASE_DIR, 'ParsedJSON')
os.makedirs(JSON_DIR, exist_ok=True)

# ─── Section definitions (must match ocr_bhashatattwa.py) ─────
SECTIONS = [
    {
        'key': 'dhwanilipi_o_swaradhwani',
        'title_bn': 'ধ্বনিলিপি ও স্বরধ্বনি',
        'title_en': 'Phonetic Alphabet & Vowels',
        'pages': list(range(380, 384)),
    },
    {
        'key': 'byanjanadhwani',
        'title_bn': 'ব্যঞ্জনধ্বনি',
        'title_en': 'Consonants',
        'pages': list(range(384, 387)),
    },
    {
        'key': 'shwasaghat',
        'title_bn': 'শ্বাসাঘাত',
        'title_en': 'Stress',
        'pages': [387],
    },
    {
        'key': 'barnamala_o_dwiswara',
        'title_bn': 'বর্ণমালা ও দ্বিস্বরধ্বনি',
        'title_en': 'Alphabet & Diphthongs',
        'pages': list(range(388, 390)),
    },
    {
        'key': 'dhwanigata_paribartan',
        'title_bn': 'ধ্বনিগত পরিবর্তন',
        'title_en': 'Phonological Changes',
        'pages': list(range(390, 395)),
    },
    {
        'key': 'apinihiti_o_dhwani_biparyay',
        'title_bn': 'অপিনিহিতি ও ধ্বনি বিপর্যয়',
        'title_en': 'Epenthesis & Sound Reversal',
        'pages': list(range(395, 403)),  # extended through 402
    },
    {
        'key': 'shabdatattwa',
        'title_bn': 'শব্দতত্ত্ব',
        'title_en': 'Word Theory',
        'pages': list(range(403, 407)),
    },
    {
        'key': 'rupatattwa_shabdarup',
        'title_bn': 'রূপতত্ত্ব — শব্দরূপ',
        'title_en': 'Morphology — Declension',
        'pages': list(range(407, 414)),
    },
    {
        'key': 'rupatattwa_dhatu_o_kriyarup',
        'title_bn': 'রূপতত্ত্ব — ধাতু ও ক্রিয়ারূপ',
        'title_en': 'Morphology — Roots & Verb Conjugation',
        'pages': list(range(414, 423)),
    },
    {
        'key': 'rupatattwa_pratyay',
        'title_bn': 'রূপতত্ত্ব — প্রত্যয়',
        'title_en': 'Morphology — Suffixes & Prefixes',
        'pages': list(range(423, 430)),
    },
    {
        'key': 'rupatattwa_sandhi_o_samas',
        'title_bn': 'রূপতত্ত্ব — সন্ধি ও সমাস',
        'title_en': 'Morphology — Sandhi & Compound Words',
        'pages': list(range(430, 435)),
    },
    {
        'key': 'rupatattwa_bisheshya_linga_bachan',
        'title_bn': 'রূপতত্ত্ব — বিশেষ্য, লিঙ্গ, বচন',
        'title_en': 'Morphology — Nouns, Gender & Number',
        'pages': list(range(435, 441)),
    },
    {
        'key': 'rupatattwa_karma_o_bisheshan',
        'title_bn': 'রূপতত্ত্ব — কর্ম ও বিশেষণ',
        'title_en': 'Morphology — Verbs & Adjectives',
        'pages': list(range(441, 451)),
    },
    {
        'key': 'rupatattwa_bisheshan_sarbanam',
        'title_bn': 'রূপতত্ত্ব — বিশেষণ ও সর্বনাম',
        'title_en': 'Morphology — Adjectives & Pronouns',
        'pages': list(range(451, 460)),
    },
    {
        'key': 'rupatattwa_kriya',
        'title_bn': 'রূপতত্ত্ব — ক্রিয়া',
        'title_en': 'Morphology — Verbs',
        'pages': list(range(460, 472)),
    },
    {
        'key': 'rupatattwa_anusarga_karak_bachya',
        'title_bn': 'রূপতত্ত্ব — অনুসর্গ, কারক ও বাচ্য',
        'title_en': 'Morphology — Postpositions, Case & Voice',
        'pages': list(range(472, 482)),
    },
    {
        'key': 'shabdarthatattwa',
        'title_bn': 'শব্দার্থতত্ত্ব',
        'title_en': 'Semantics',
        'pages': list(range(482, 496)),
    },
    {
        'key': 'shabdabhandar',
        'title_bn': 'শব্দভাণ্ডার',
        'title_en': 'Vocabulary & Lexicon',
        'pages': list(range(496, 516)),
    },
    {
        'key': 'bakyatattwa',
        'title_bn': 'বাক্যতত্ত্ব',
        'title_en': 'Syntax',
        'pages': list(range(516, 565)),
    },
    {
        'key': 'narir_bhasha',
        'title_bn': 'নারীর ভাষা',
        'title_en': "Women's Language",
        'pages': list(range(565, 574)),
    },
    {
        'key': 'charya_o_srikrishnakirtaner_bhasha',
        'title_bn': 'চর্যা ও শ্রীকৃষ্ণকীর্তনের ভাষা',
        'title_en': 'Language of Charya & Srikrishnakirtana',
        'pages': list(range(574, 605)),
    },
]

# ─── Known noise patterns ─────────────────────────────────────
# Running headers / footers / page numbers to strip
NOISE_PATTERNS = [
    r'^\d{1,4}$',                                              # bare page number
    r'^<b>\d{1,4}</b>$',                                       # bold page number
    r'^<b>[\u09E6-\u09EF]{1,4}</b>$',                                    # bold Bengali page number
    r'^[\u09E6-\u09EF]{1,4}$',                                            # Bengali page number
    r'^[0-9\u09E6-\u09EF\$\u0966-\u096F\u0963]{2,4}$',                   # mixed-script garbled page numbers (800, 80³, 8$8, 8२१)
    r'^\u099A\u09B0\u09CD\u09AF\u09BE \u0993 \u09B6\u09CD\u09B0\u09C0\u0995\u09C3\u09B7\u09CD\u09A3\u0995\u09C0\u09B0\u09CD\u09A4\u09A8$',                              # running header (587-588)
    r'^\u09AD\u09BE\u09B7\u09BE$',                                                   # running sub-header (587-588)
    r'^\u09AC\u09B0\u09BE\u0995 \u0989\u09AA\u09A4\u09CD\u09AF\u0995\u09BE\u09B0 \u0986\u099E\u09CD\u099A\u09B2\u09BF\u0995 \u09AC\u09BE\u0982\u09B2\u09BE \u09AD\u09BE\u09B7\u09BE\u09B0 \u0985\u09AD\u09BF\u09A7\u09BE\u09A8 \u0993 \u09AD\u09BE\u09B7\u09BE\u09A4\u09A4\u09CD',   # book title footer
    r'^\u09AC\u09B0\u09BE\u0995 \u0989\u09AA\u09A4\u09CD\u09AF\u0995\u09BE\u09B0 \u0986\u099E\u09CD\u099A\u09B2\u09BF\u0995 \u09AC\u09BE\u0982\u09B2\u09BE \u09AD\u09BE\u09B7\u09BE\u09B0 \u0985\u09AD\u09BF\u09A7\u09BE\u09A8 \u0993 \u09AD\u09BE\u09B7\u09BE\u09A4\u09A4\u09CD\u09A4\u09CD\u09AC$',
    r'^\u09AC\u09B0\u09BE\u0995 \u0989\u09AA\u09A4\u09CD\u09AF\u0995\u09BE\u09B0 \u0986\u099E\u09CD\u099A\u09B2\u09BF\u0995 \u09AC\u09BE\u0982\u09B2\u09BE \u09AD\u09BE\u09B7\u09BE\u09B0 \u09AD\u09BE\u09B7\u09BE\u09A4',               # alt footer
    r'^\- \d+[\.\u2026]+$',                                          # page number artifacts like '- 45...'
]
NOISE_RES = [re.compile(p) for p in NOISE_PATTERNS]

# Running headers that appear at top of page (first 3 lines).
# These are stripped only when found in position 0-2 of a page.
RUNNING_HEADERS = {
    # Main chapter header
    'ধ্বনিতত্ত্ব',
    # Sub-section headers
    'স্বরধ্বনি',
    'ব্যঞ্জনধ্বনি',
    'ধ্বনিগত পরিবর্তন',
    'অপিনিহিতি ও ধ্বনি বিপর্যয়',
    'অপিনিহিতি ও বিপর্যাস',
    'অপিনিহিতি',
    'শ্বাসাঘাত',
    'স্বরবর্ণ ও ব্যঞ্জনবর্ণ',
    'দ্বিস্বরধ্বনি স্বরসংযোগ',
    # Garbled OCR versions of running headers
    'ধ্বনিপবিবর্ত',
    'স্পপ্তধ্বা-',
    'वाञ्जनभानि स्श्रेष्ठभानि',
    # Topic-list running sub-headers
    'তাড়িত, রনিত, পার্শ্বিক',
    'উত্ম, নাসিক্য, অর্ধস্বরধ্বনি',
    'মৌলিক স্বরধ্বনি',
    # Book title running header
    'বরাক উপত্যকার আঞ্চলিক বাংলা ভাষার ভাষাতত্ত্ব',
    # Pages 587-588 headers
    'চর্যা ও শ্রীকৃষ্ণকীর্তনের ভাষা',
    'ভাষা',
    # Pages 401-450 headers (running headers from OCR)
    'অপিনিহিতি ধ্বনিবিকার',
    'শব্দতত্ত্ব',
    'রূপতত্ত্ব',
    'রাপতত্ত্ব',  # OCR misspelling of রূপতত্ত্ব
    'শব্দরাপ',
    'শব্দরূপ',
    'নাম শব্দরাপ',
    'নাম শব্দরূপ',
    'সর্বনাম শব্দরূপ',
    'সর্বনাম শব্দরাপ',
    'ধাতু',
    'ধাতুরাপ',
    'ধাতুরূপ',
    'ক্রিয়ারূপাদর্শ',
    'কুৎপ্রত্যয়',
    'তদ্ধিত প্রত্যয়',
    'তদ্ধিত্ প্রত্যয়',
    'তদ্ধিত্ প্রত্যয়',
    'অনুসর্গীয় প্রত্যয়',
    'উপসর্গীয় প্রত্যয়',
    'সন্ধি',
    'সমাস',
    'বিশেষ্য',
    'লিঙ্গ',
    'বচন',
    'কর্তাকর্ম',
    'কর্ম',
    'বিশেষণ',
    'বিশেষণীয় বিশেষণ',
    'দ্বিগুণিতশব্দ',
    'অনুকার ও অনুগামী শব্দ',
    'সংখ্যশব্দ',
    # OCR garbled versions
    'শব্দরাপ DECLENSION',
    'শব্দরূপ DECLENSION',
    'শ্রেষ',
    'मका',
    '•',
    # Pages 451-550 running headers
    'বিশেষণ',
    'প্রতিপাদক বিশেষক',
    'সর্বনাম',
    'ক্রিয়া নির্মাণ',
    'ক্রিয়ার ভাব',
    'ক্রিয়া',
    'যৌগিক ক্রিয়া',
    'অসমাপিকা ক্রিয়া ও অস্তার্থ ক্রিয়া',
    'নাস্ত্যর্থ ক্রিয়া',
    'অনুসর্গ',
    'অনম্বয়ী',
    'কারক',
    'বাচ্য',
    'শব্দার্থতত্ত্ব',
    'শব্দার্থতত্ত',
    'শব্দের আন্তরশক্তি',
    'অর্থ পরিবর্তনের ধারা',
    'সুভাষণ ও দুর্ভাষণ',
    'শব্দের চিত্রময়তা',
    'শব্দের বিশিষ্টার্থক প্রয়োগ',
    'শব্দভাণ্ডার',
    'শবভাণ্ডার',
    'শব্দভাতার',
    'শব্দভাগুর',
    'শক্তাপ্তার',
    'শব্দ ভাভার',  # garbled শব্দভাণ্ডার
    'শব্দার্থ তত্ত্ব',  # garbled শব্দার্থতত্ত্ব
    'মৌলিক শব্দ',
    'আগন্তুক শব্দ',
    'বিদেশি শব্দ',
    'তদ্ভব শব্দ',
    'ভগ্নতৎসম শব্দ',
    'দেশি শব্দ',
    'শব্দ সংরক্ষণ',
    'বাক্যতত্ত্ব',
    'বাক্যভত্ত',
    'উদ্যম: এক',
    'উদ্যম : এক',
    'উদাম : এক',
    'উদ্যম : দুই',
    'উদ্যম: দুই',
    'নিৰ্মাণ',
    'নির্মাণ',
    'উদ্দেশ্য নির্মাণ',
    'সম্বন্ধ নিৰ্মাণ',
    'সম্বন্ধ নির্মাণ',
    'নিষ্ঠান্ত নিৰ্মাণ',
    'সর্বনাম নির্মাণ',
    'বিশেষণ অতিক্রমণ নির্মাণ',
    'বিধেয় নির্মাণ',
    'ক্রিয়া নির্মাণ',
    'প্রশ্নাত্মক বাক্য নির্মাণ',
    # Pages 551-604 running headers
    'প্রশাত্মক বাক্য নির্মাণ',  # garbled প্রশ্নাত্মক
    'অনুজ্ঞাসূচক নির্মাণ',
    'সরল জটিল যৌগিক বাক্যের নির্মাণ',
    'সরল বাক্যের নির্মাণ',
    'জটিল বাক্যের নির্মাণ',
    'সংলাপ নিৰ্মাণ',
    'সংলাপ নির্মাণ',
    'বাক্তি',  # garbled বাক্যতত্ত্ব
    'নারীর ভাষা',
    'বরাক উপত্যকার নারীর ভাষা',
    'সর্বনাম, সম্বোধন',
    'ধ্বন্যাত্মক শব্দ',
    'সংস্কার',
    'বাগধারা',
    'প্রবচন',
    'বিশেষ্য বিশেষণ',
    'চর্যাপদ ও শ্রীকৃষ্ণকীর্তনের উত্তরাধিকার',
    'চর্যা ও শ্রীকৃষ্ণকীর্তন',
    'চর্যা ও গ্রীকৃষ্ণকীর্তন',  # OCR garbled
    'চযা ও গ্রীকৃষ্ণকীর্তন',  # OCR garbled
}

def is_noise(line):
    t = line.strip()
    if not t:
        return True
    for pat in NOISE_RES:
        if pat.match(t):
            return True
    return False

# ─── Line-type classification ─────────────────────────────────

# Section heading:  (ক) ধ্বনিতত্ত্ব:  or  (খ) রূপতত্ত্ব:
RE_SECTION_HEADING = re.compile(r'^\([\u0995-\u09B9]\)\s+.+')

# Section title that spans part of a page heading
RE_SECTION_TITLE_LINE = re.compile(
    r'^বরাক উপত্যকার আঞ্চলিক বাংলা ভাষায় সংরক্ষিত')

# Numbered point:  ১. or ২. or 8. etc  (start of a numbered paragraph)
RE_NUMBERED = re.compile(r'^[\d১-৯][০-৯\d]*[\.\,]\s*')

# Sub-example labels:  অ. আ. ই. ঈ. উ.
RE_SUB_EXAMPLE = re.compile(r'^[অআইঈউঊঋএঐওঔ][\.\,]\s*')

# Arrow example:  word > word  or  word ⇒ sentence
RE_ARROW = re.compile(r'^.+\s*[>⇒=]\s*.+')

# Slash pair:  word / word  (comparison pair)
RE_SLASH_PAIR = re.compile(r'^.+\s*/\s*.+$')

# Citation: starts with — or " or ends with —author.
RE_CITATION = re.compile(r'^[\—\–\-]\s*[\'"\u201c]|^[""\u201c]|—[^—]+$')

# Table header markers: look for known table headers in bhashatattwa pages
TABLE_HEADERS = [
    ['বাংলা', 'বরাকবাংলা'],
    ['শ্রীকৃষ্ণকীর্তন', 'বরাকবাংলা'],
    ['শ্রীকৃষ্ণকীর্তন', 'স্বর', 'বরাকবাংলা'],
    ['শ্রীকৃষ্ণকীর্তন', 'বরাক বাংলা'],
]


def classify_line(line, prev_type=None, context_lines=None, line_idx=0):
    """Classify a single OCR line into a formatting type."""
    t = line.strip()
    if not t:
        return 'blank'

    # Section title line (e.g. "বরাক উপত্যকার আঞ্চলিক বাংলা ভাষায় সংরক্ষিত...")
    if RE_SECTION_TITLE_LINE.match(t):
        return 'section_title'

    # Section heading: (ক) ধ্বনিতত্ত্ব:
    if RE_SECTION_HEADING.match(t):
        return 'heading'

    # Numbered point start
    if RE_NUMBERED.match(t):
        return 'numbered'

    # Sub-example
    if RE_SUB_EXAMPLE.match(t):
        return 'sub_example'

    # Check for table header
    if t in [h for hlist in TABLE_HEADERS for h in hlist]:
        return 'table_header'

    # Arrow/comparison example
    if RE_ARROW.match(t) and len(t) < 120:
        return 'example'

    # Slash pair (short comparison)
    if RE_SLASH_PAIR.match(t) and len(t) < 80:
        return 'example'

    # Short isolated word (likely a table cell or label) - typically < 25 chars
    # and standalone between other short lines
    if len(t) < 30 and prev_type in ('table_cell', 'table_header', None):
        # Could be a table cell
        if context_lines:
            neighbors_short = True
            for offset in [-1, 1]:
                ni = line_idx + offset
                if 0 <= ni < len(context_lines):
                    nt = context_lines[ni].strip()
                    if nt and len(nt) > 60:
                        neighbors_short = False
            if neighbors_short:
                return 'table_cell'

    # Default: paragraph text
    return 'paragraph'


def detect_table_regions(lines):
    """Detect contiguous regions that form tables (sequences of short alternating lines)."""
    N = len(lines)
    table_regions = []  # list of (start, end, columns) tuples
    i = 0
    while i < N:
        t = lines[i].strip()
        # Check if this line is a known table header
        is_header = False
        header_cols = None
        for hlist in TABLE_HEADERS:
            if t == hlist[0]:
                # Check if subsequent lines match remaining headers
                matched = True
                for j, h in enumerate(hlist[1:], 1):
                    if i + j < N and lines[i + j].strip() == h:
                        continue
                    else:
                        matched = False
                        break
                if matched:
                    is_header = True
                    header_cols = hlist
                    break

        if is_header:
            header_start = i
            num_cols = len(header_cols)
            i += num_cols  # skip header lines

            # Collect table rows: sequences of num_cols short lines
            row_start = i
            rows = []
            while i < N:
                # Try to read num_cols lines as one row
                row_lines = []
                all_short = True
                for c in range(num_cols):
                    if i + c >= N:
                        all_short = False
                        break
                    cl = lines[i + c].strip()
                    if not cl or is_noise(lines[i + c]):
                        all_short = False
                        break
                    if len(cl) > 80:  # too long for a table cell
                        all_short = False
                        break
                    row_lines.append(cl)

                if all_short and len(row_lines) == num_cols:
                    rows.append(row_lines)
                    i += num_cols
                else:
                    break

            if rows:
                table_regions.append({
                    'start': header_start,
                    'end': i,
                    'headers': header_cols,
                    'rows': rows,
                })
            continue
        i += 1
    return table_regions


def is_terminal(line):
    """Line ends with sentence-terminal punctuation."""
    t = line.strip()
    if not t:
        return False
    last = t[-1]
    if last in '।:;)':
        return True
    if t.endswith('।।'):
        return True
    if last in "'\u2019\"" and len(t) > 1 and t[-2] == '।':
        return True
    return False


def parse_page(lines):
    """Parse a single page's OCR lines into structured blocks.

    Returns a list of block dicts, each with:
      type: 'section_title' | 'heading' | 'paragraph' | 'example_group' |
            'table' | 'citation' | 'sub_examples'
      content: varies by type
    """
    # STEP 1: Strip running headers from top of page (first 3 non-blank lines)
    top_content_count = 0
    header_indices = set()
    for idx, line in enumerate(lines[:8]):  # look in first 8 raw lines
        t = line.strip()
        if not t:
            continue
        top_content_count += 1
        if top_content_count <= 3:
            clean_t = re.sub(r'<[^>]+>', '', t).strip()
            if clean_t in RUNNING_HEADERS:
                header_indices.add(idx)

    # STEP 2: Filter noise + running headers
    clean = []
    for idx, line in enumerate(lines):
        if idx in header_indices:
            continue
        if not is_noise(line):
            clean.append(line)

    # Detect table regions
    table_regions = detect_table_regions(clean)
    table_line_set = set()
    for tr in table_regions:
        for j in range(tr['start'], tr['end']):
            table_line_set.add(j)

    blocks = []
    i = 0
    N = len(clean)

    while i < N:
        # Skip if in a table region
        if i in table_line_set:
            # Find and emit the table block
            for tr in table_regions:
                if tr['start'] == i:
                    blocks.append({
                        'type': 'table',
                        'headers': tr['headers'],
                        'rows': tr['rows'],
                    })
                    i = tr['end']
                    break
            else:
                i += 1
            continue

        t = clean[i].strip()
        if not t:
            i += 1
            continue

        line_type = classify_line(t, 
                                  prev_type=blocks[-1]['type'] if blocks else None,
                                  context_lines=clean, 
                                  line_idx=i)

        if line_type == 'section_title':
            blocks.append({'type': 'section_title', 'text': t})
            i += 1

        elif line_type == 'heading':
            blocks.append({'type': 'heading', 'text': t})
            i += 1

        elif line_type == 'numbered':
            # Numbered paragraph: collect continuation lines
            para_lines = [t]
            i += 1
            while i < N and i not in table_line_set:
                nt = clean[i].strip()
                if not nt:
                    i += 1
                    continue
                ntype = classify_line(nt, prev_type='numbered', context_lines=clean, line_idx=i)
                if ntype in ('heading', 'section_title', 'numbered', 'table_header'):
                    break
                # If it's a continuation of the paragraph (long line, no terminal on prev)
                if ntype in ('paragraph',) and len(para_lines[-1]) > 45 and not is_terminal(para_lines[-1]):
                    para_lines.append(nt)
                    i += 1
                else:
                    break
            blocks.append({'type': 'numbered', 'text': ' '.join(para_lines)})

        elif line_type == 'example':
            # Collect consecutive examples
            examples = [t]
            i += 1
            while i < N and i not in table_line_set:
                nt = clean[i].strip()
                if not nt:
                    i += 1
                    continue
                etype = classify_line(nt, prev_type='example', context_lines=clean, line_idx=i)
                if etype == 'example':
                    examples.append(nt)
                    i += 1
                else:
                    break
            blocks.append({'type': 'example_group', 'items': examples})

        elif line_type == 'sub_example':
            subs = [t]
            i += 1
            while i < N and i not in table_line_set:
                nt = clean[i].strip()
                if not nt:
                    i += 1
                    continue
                # Sub-example continuation or new sub-example
                if RE_SUB_EXAMPLE.match(nt):
                    subs.append(nt)
                    i += 1
                elif len(subs[-1]) > 45 and not is_terminal(subs[-1]):
                    # continuation of previous sub-example
                    subs[-1] += ' ' + nt
                    i += 1
                else:
                    break
            blocks.append({'type': 'sub_examples', 'items': subs})

        elif line_type == 'table_cell':
            # Orphan table cells not caught by region detection — pair them
            cells = [t]
            i += 1
            while i < N and i not in table_line_set:
                nt = clean[i].strip()
                if not nt:
                    i += 1
                    continue
                if len(nt) < 60:
                    cells.append(nt)
                    i += 1
                else:
                    break
            # Group into 2-column rows
            if len(cells) >= 2:
                rows = []
                for ri in range(0, len(cells) - 1, 2):
                    rows.append([cells[ri], cells[ri + 1]])
                if len(cells) % 2 == 1:
                    rows.append([cells[-1], ''])
                blocks.append({
                    'type': 'table',
                    'headers': [],
                    'rows': rows,
                })
            else:
                blocks.append({'type': 'paragraph', 'text': t})

        else:  # paragraph
            para_lines = [t]
            i += 1
            while i < N and i not in table_line_set:
                nt = clean[i].strip()
                if not nt:
                    i += 1
                    continue
                ntype = classify_line(nt, prev_type='paragraph', context_lines=clean, line_idx=i)
                if ntype in ('heading', 'section_title', 'numbered', 'table_header',
                             'example', 'sub_example'):
                    break
                if ntype == 'paragraph' and len(para_lines[-1]) > 45 and not is_terminal(para_lines[-1]):
                    para_lines.append(nt)
                    i += 1
                else:
                    break
            blocks.append({'type': 'paragraph', 'text': ' '.join(para_lines)})

    return blocks


def build_section_json(section):
    """Build JSON for one section."""
    all_blocks = []
    for page_num in section['pages']:
        txt_path = os.path.join(TEXT_DIR, f'IMG_{page_num:04d}_extracted_text.txt')
        if not os.path.exists(txt_path):
            print(f'  [WARN] Missing: {txt_path}')
            continue

        with open(txt_path, 'r', encoding='utf-8') as f:
            raw_lines = f.read().split('\n')

        page_blocks = parse_page(raw_lines)

        # Tag each block with source page
        for b in page_blocks:
            b['source_page'] = page_num
            b['source_image'] = f'IMG_{page_num:04d}.jpg'

        all_blocks.extend(page_blocks)

    result = {
        'section': section['title_bn'],
        'section_en': section['title_en'],
        'key': section['key'],
        'page_range': f"IMG_{section['pages'][0]:04d} – IMG_{section['pages'][-1]:04d}",
        'blocks': all_blocks,
    }
    return result


def main():
    print('Parsing ভাষাতত্ত্ব OCR text into structured JSON...\n')

    for section in SECTIONS:
        data = build_section_json(section)
        out_path = os.path.join(JSON_DIR, f"{section['key']}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        n_blocks = len(data['blocks'])
        types = {}
        for b in data['blocks']:
            types[b['type']] = types.get(b['type'], 0) + 1

        print(f"  {section['title_bn']} ({section['title_en']})")
        print(f"    → {len(section['pages'])} pages, {n_blocks} blocks")
        print(f"    → Types: {types}")
        print(f"    → {out_path}")
        print()

    print('Done.')


if __name__ == '__main__':
    main()
