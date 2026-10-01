#!/usr/bin/env python3
from pathlib import Path

PATH = Path("france-maghreb.m3u")
URL = "https://www.youtube.com/c/syriaalikhbaria/live"
ENTRY = '#EXTINF:-1 tvg-id="AlikhbariaSyria.sy" tvg-logo="" group-title="Syrie",Alikhbaria Syria (YouTube officiel)\n' + URL + '\n'

text = PATH.read_text(encoding="utf-8")
if URL in text:
    print("Alikhbaria Syria already present")
    raise SystemExit(0)

marker = "# ===== SYRIE "
pos = text.find(marker)
if pos >= 0:
    end = text.find("\n# ===== ", pos + 1)
    if end < 0:
        end = len(text)
    text = text[:end].rstrip() + "\n" + ENTRY + "\n" + text[end:].lstrip("\n")
else:
    text = text.rstrip() + "\n\n# ===== SYRIE (1 entrées) =====\n" + ENTRY

PATH.write_text(text, encoding="utf-8", newline="\n")
print("Added verified Alikhbaria Syria official YouTube /live")
