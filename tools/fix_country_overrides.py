#!/usr/bin/env python3
import re

PATH = "france-maghreb.m3u"

# Known upstream metadata mistakes.  The final legal filter rebuilds the
# country sections from group-title, so changing the attribute here is enough
# to move every affected entry into the correct country block.
OVERRIDES = [
    {
        "ids": ("LibyaAlAhrarTV.qa", "LibyaAlAhrar.ly"),
        "names": ("libya al ahrar", "libya al-ahrar", "ليبيا الأحرار"),
        "group": "Libye",
    },
]

ATTR_ID_RE = re.compile(r'tvg-id="([^"]*)"', re.I)
GROUP_RE = re.compile(r'group-title="[^"]*"', re.I)


def normalize(s):
    s = re.sub(r"\s*\((?:secours\s+\d+|youtube officiel)\)\s*$", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9à-ÿ]+", "", s.casefold().replace("œ", "oe"))


def target_group(extinf):
    tid_match = ATTR_ID_RE.search(extinf)
    tid = (tid_match.group(1).split("@", 1)[0] if tid_match else "").casefold()
    name = extinf.split(",", 1)[1] if "," in extinf else ""
    nn = normalize(name)
    for rule in OVERRIDES:
        ids = {x.casefold() for x in rule["ids"]}
        names = {normalize(x) for x in rule["names"]}
        if tid in ids or any(n and n in nn for n in names):
            return rule["group"]
    return None


with open(PATH, encoding="utf-8") as f:
    lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

changed = 0
out = []
for line in lines:
    if line.startswith("#EXTINF:"):
        group = target_group(line)
        if group:
            if GROUP_RE.search(line):
                new_line = GROUP_RE.sub(f'group-title="{group}"', line, count=1)
            else:
                comma = line.find(",")
                if comma >= 0:
                    new_line = line[:comma] + f' group-title="{group}"' + line[comma:]
                else:
                    new_line = line
            if new_line != line:
                changed += 1
                line = new_line
    out.append(line)

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out).rstrip() + "\n")

print(f"Country overrides: corrected {changed} entries")
