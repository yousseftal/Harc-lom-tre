#!/usr/bin/env python3
"""Ajoute uniquement des directs officiels vérifiés, sans URL temporaire."""
from pathlib import Path

PATH = Path("france-maghreb.m3u")
SOURCES = [
    ("Syrie", "AlikhbariaSyria.sy", "Alikhbaria Syria",
     "https://www.youtube.com/c/syriaalikhbaria/live"),
    ("Arabie saoudite", "AlThaqafeyah.sa", "Al Thaqafeyah (الثقافية)",
     "https://www.youtube.com/@thaqafeyah/live"),
]

text = PATH.read_text(encoding="utf-8")
added = 0
for country, tvg_id, name, url in SOURCES:
    if url in text:
        print(f"Already present: {name}")
        continue
    entry = (f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="" '
             f'group-title="{country}",{name} (YouTube officiel)\n{url}\n')
    marker = f"# ===== {country.upper()} "
    pos = text.find(marker)
    if pos >= 0:
        end = text.find("\n# ===== ", pos + 1)
        if end < 0:
            end = len(text)
        text = text[:end].rstrip() + "\n" + entry + "\n" + text[end:].lstrip("\n")
    else:
        text = text.rstrip() + f"\n\n# ===== {country.upper()} =====\n" + entry
    added += 1
    print(f"Added official YouTube live: {name}")

if added:
    PATH.write_text(text, encoding="utf-8", newline="\n")
print(f"Verified official live additions: {added}")
