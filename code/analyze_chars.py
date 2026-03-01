# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""Analyze non-Bengali characters in all JSON entries."""
import json, glob, os, re
from collections import Counter

# Bengali Unicode range: U+0980 - U+09FF
# Assamese ৰ = U+09F0, ৱ = U+09F1
# Devanagari: U+0900 - U+097F
# Other scripts to check

def is_bengali(ch):
    cp = ord(ch)
    return 0x0980 <= cp <= 0x09FF

def is_devanagari(ch):
    cp = ord(ch)
    return 0x0900 <= cp <= 0x097F

def scan_files(json_dir):
    files = sorted(glob.glob(os.path.join(json_dir, 'IMG_*_entries.json')))
    
    # Track ৰ occurrences with context
    ra_contexts = []
    # Track non-Bengali/non-ASCII chars
    non_bn = Counter()
    devanagari_contexts = []
    
    for fp in files:
        page = os.path.basename(fp).replace('_entries.json', '')
        with open(fp, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        for idx, entry in enumerate(entries):
            text = json.dumps(entry, ensure_ascii=False)
            
            # Find ৰ
            hw = entry.get('headword', '')
            if '\u09F0' in text:
                ra_contexts.append((page, idx, hw, text[:300]))
            
            # Find Devanagari
            for ch in text:
                if is_devanagari(ch):
                    devanagari_contexts.append((page, idx, hw, ch, f'U+{ord(ch):04X}', text[:200]))
                    non_bn[ch] += 1
                # Assamese-specific
                if ch in '\u09F0\u09F1':
                    non_bn[ch] += 1
    
    return ra_contexts, devanagari_contexts, non_bn

for label, json_dir in [
    ('ParsedJSON', r'c:\Users\sankhyac\Downloads\Dict\ParsedJSON'),
    ('ParsedJSON_Merged', r'c:\Users\sankhyac\Downloads\Dict\ParsedJSON_Merged'),
]:
    print(f"\n{'='*60}")
    print(f"Scanning: {label}")
    print(f"{'='*60}")
    
    ra_ctx, dev_ctx, non_bn = scan_files(json_dir)
    
    print(f"\n--- ৰ (U+09F0) occurrences: {len(ra_ctx)} entries ---")
    for page, idx, hw, ctx in ra_ctx[:20]:
        print(f"  {page} [{idx}] hw={hw}")
    if len(ra_ctx) > 20:
        print(f"  ... and {len(ra_ctx)-20} more")
    
    print(f"\n--- Devanagari characters found ---")
    for ch, cnt in non_bn.most_common(30):
        print(f"  U+{ord(ch):04X} {ch!r:6s} ({ch}) count={cnt}")
    
    print(f"\n--- Devanagari in context (first 15) ---")
    for page, idx, hw, ch, code, ctx in dev_ctx[:15]:
        print(f"  {page} [{idx}] hw={hw} char={ch}({code})")
