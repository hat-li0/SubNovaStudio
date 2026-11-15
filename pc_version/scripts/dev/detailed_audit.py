import re
import sys
from app.subtitle import parse_subtitle

sys.stdout.reconfigure(encoding='utf-8')

orig = parse_subtitle(r"C:\Users\hatim alharbi\AppData\Local\Temp\orig_track.ass")
trans = parse_subtitle(r"c:\Users\hatim alharbi\Downloads\My Girlfriends Friend S01E04.ara.ass")

for i in range(min(len(orig.events), len(trans.events))):
    oe = orig.events[i]
    te = trans.events[i]
    t_text = te.translated_text or te.original_text
    
    # Check if original had tags that were mutated weirdly
    if "{\\i1}" in oe.original_text and "{\\i1}{\\i0}" in t_text:
        # We already know this
        pass
    
    # Check if original had dash and translation lost it or vice versa
    if oe.original_text.startswith("-") != t_text.startswith("-"):
        if "-" in oe.original_text[:3] or "-" in t_text[:3]:
            # print(f"Dash mismatch Line {i+1}: orig='{oe.original_text}' | trans='{t_text}'")
            pass

    # Check for any remaining untranslated French or English words
    clean = re.sub(r"\{[^}]*\}", "", t_text).replace(r"\N", " ")
    for word in re.findall(r"[A-Za-z]+", clean):
        if len(word) > 1 and word.lower() not in ("kôdan", "production", "esuka", "anesaki", "deregula", "wwwave"):
            print(f"Stray Latin Word in Line {i+1}: '{word}' in: {t_text}")
