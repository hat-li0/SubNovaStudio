import re
import sys
from app.subtitle import parse_subtitle

sys.stdout.reconfigure(encoding='utf-8')

file_path = r"c:\Users\hatim alharbi\Downloads\My Girlfriends Friend S01E04.ara.ass"
doc = parse_subtitle(file_path)

print(f"Total lines: {len(doc.events)}")

for i, ev in enumerate(doc.events, 1):
    text = ev.translated_text or ev.original_text
    
    # Check 1: Empty tags like {\i1}{\i0}
    if r"{\i1}{\i0}" in text or r"{\i0}{\i1}" in text or r"{\b1}{\b0}" in text:
        print(f"[EMPTY TAG] Line {i}: {text}")
        
    # Check 2: Latin characters
    no_tags = re.sub(r"\{[^}]*\}", "", text).replace(r"\N", " ")
    latin = re.findall(r"[A-Za-z\u00C0-\u024F]+", no_tags)
    if latin:
        print(f"[LATIN] Line {i} {latin}: {text}")

    # Check 3: Broken punctuation or formatting
    if re.search(r"[,?;]", no_tags):
        print(f"[ASCII PUNCT] Line {i}: {text}")
        
    if re.search(r"\s+[،؟!\.]", no_tags):
        print(f"[SPACE BEFORE PUNCT] Line {i}: {text}")

    if re.search(r"\\N\s*$", text) or re.search(r"^\s*\\N", text):
        print(f"[DANGLING \\N] Line {i}: {text}")
