# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""Deeper analysis of ৰ in headwords and Devanagari character mapping."""
import json, glob, os
from collections import Counter

JSON_DIR = r'c:\Users\sankhyac\Downloads\Dict\ParsedJSON_Merged'

files = sorted(glob.glob(os.path.join(JSON_DIR, 'IMG_*_entries.json')))

# ৰ in headwords - show with neighbors for context
print("=== ৰ in HEADWORDS (with adjacent entries for context) ===")
ra_hw_count = 0
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    for i, e in enumerate(entries):
        hw = e.get('headword', '')
        if '\u09F0' in hw:
            ra_hw_count += 1
            prev_hw = entries[i-1].get('headword','') if i > 0 else '(none)'
            next_hw = entries[i+1].get('headword','') if i+1 < len(entries) else '(none)'
            print(f"  {os.path.basename(fp):30s} [{i}] prev={prev_hw:15s} >>> {hw:20s} <<< next={next_hw}")

print(f"\nTotal headwords with ৰ: {ra_hw_count}")

# Check ৱ (Assamese Wa, U+09F1) in headwords
print("\n=== ৱ (U+09F1) in HEADWORDS ===")
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    for i, e in enumerate(entries):
        hw = e.get('headword', '')
        if '\u09F1' in hw:
            prev_hw = entries[i-1].get('headword','') if i > 0 else '(none)'
            next_hw = entries[i+1].get('headword','') if i+1 < len(entries) else '(none)'
            print(f"  {os.path.basename(fp):30s} [{i}] prev={prev_hw:15s} >>> {hw:20s} <<< next={next_hw}")

# Get full Devanagari inventory
print("\n=== Full Devanagari character inventory ===")
dev_chars = Counter()
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        text = f.read()
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F and cp != 0x0964 and cp != 0x0965:  # exclude danda
            dev_chars[ch] += 1

for ch, cnt in dev_chars.most_common(50):
    print(f"  U+{ord(ch):04X} ({ch}) → count={cnt}")

# Show Devanagari numbers
print("\n=== Devanagari numbers ===")
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        text = f.read()
    for line in text.split('\n'):
        for ch in '०१२३४५६७८९':
            if ch in line:
                print(f"  {os.path.basename(fp)}: ...{line[max(0,line.index(ch)-20):line.index(ch)+20]}...")
                break
