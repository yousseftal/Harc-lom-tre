#!/usr/bin/env python3
import re

PATH = "france-maghreb.m3u"

# Explicit non-French/non-Arabic language labels sometimes share the base TV ID
# of a French/Arabic channel (for example France24.fr@English). Remove those
# variants without rejecting brands whose names simply happen to be in English.
OTHER_LANG = re.compile(
    r"(?i)(@(?:english|englishhd|spanish|espanol|español|german|deutsch|italian|italiano|portuguese|português|russian|russki|turkish|persian|farsi|hindi|urdu|chinese|mandarin|japanese|korean)\b|"
    r"\b(?:english|español|spanish|deutsch|german|italiano|italian|portuguese|português|russian|turkish|persian|farsi|hindi|urdu|mandarin|japanese|korean)\b)"
)
KEEP_LANG = re.compile(r"(?i)\b(french|français|francaise|française|arabic|arabe)\b|العربية")

with open(PATH, encoding="utf-8") as f:
    lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

header = []
entries = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("#EXTINF:"):
        block = [line]
        i += 1
        while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
            block.append(lines[i])
            i += 1
        entries.append(block)
        continue
    if not line.startswith("# ====="):
        header.append(line)
    i += 1

kept = []
removed = 0
for block in entries:
    ext = block[0]
    name = ext.split(",", 1)[1] if "," in ext else ext
    hay = ext + " " + name
    if OTHER_LANG.search(hay) and not KEEP_LANG.search(name):
        removed += 1
        continue
    kept.append(block)

# Rebuild country groups from group-title.
groups = {}
order = []
for block in kept:
    m = re.search(r'group-title="([^"]+)"', block[0])
    country = m.group(1) if m else "International"
    if country not in groups:
        groups[country] = []
        order.append(country)
    groups[country].append(block)

# Keep the country order already produced by the generator. Replace the total
# in the header and rebuild section counts.
clean_header = []
for line in header:
    if line.startswith("# Total après déduplication:"):
        clean_header.append(f"# Total après déduplication: {len(kept)}")
    elif line.strip():
        clean_header.append(line)

out = clean_header + [""]
for country in order:
    blocks = groups[country]
    out.append(f"# ===== {country.upper()} ({len(blocks)}) =====")
    for block in blocks:
        out.extend(block)
    out.append("")

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out).rstrip() + "\n")

print(f"Language post-filter: kept {len(kept)}, removed {removed} explicit non-French/non-Arabic variants")
