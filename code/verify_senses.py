# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
import json, glob

total = 0
all_ok = True
multi_sense = 0
no_sense = 0

for f in sorted(glob.glob('ParsedJSON/entries_pages_*.json')):
    d = json.load(open(f, 'r', encoding='utf-8'))
    total += len(d)
    for e in d:
        if 'senses' not in e:
            all_ok = False
            no_sense += 1
        elif len(e['senses']) > 1:
            multi_sense += 1

print(f"Total entries: {total}")
print(f"All have senses: {all_ok}")
print(f"Missing senses: {no_sense}")
print(f"Entries with multiple senses: {multi_sense}")
