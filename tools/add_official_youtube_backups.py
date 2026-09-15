#!/usr/bin/env python3
import re
from collections import OrderedDict

PATH = "france-maghreb.m3u"
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

# URLs /live officielles et stables. Elles ne sont PAS des URLs googlevideo temporaires.
# Elles sont conservées comme secours uniquement; le lecteur IPTV doit savoir résoudre YouTube.
YOUTUBE = [
    {
        "ids": ["FranceInfo.fr", "Franceinfo.fr"],
        "names": ["France Info", "Franceinfo", "franceinfo"],
        "fallback_id": "FranceInfo.fr",
        "name": "franceinfo",
        "group": "France",
        "url": "https://www.youtube.com/c/franceinfo/live",
    },
    {
        "ids": ["France24French.fr", "France24.fr@French"],
        "names": ["France 24 Français", "France 24 French"],
        "fallback_id": "France24French.fr",
        "name": "France 24 Français",
        "group": "France",
        "url": "https://www.youtube.com/c/FRANCE24/live",
    },
    {
        "ids": ["EuronewsFrench.fr", "Euronews.fr@French"],
        "names": ["Euronews Français", "Euronews French", "Euronews"],
        "fallback_id": "EuronewsFrench.fr",
        "name": "Euronews Français",
        "group": "France",
        "url": "https://www.youtube.com/euronewsfr/live",
    },
    {
        "ids": ["France24Arabic.fr", "France24.fr@Arabic"],
        "names": ["France 24 العربية", "France 24 Arabic"],
        "fallback_id": "France24.fr@Arabic",
        "name": "France 24 العربية",
        "group": "France",
        "url": "https://www.youtube.com/c/FRANCE24Arabic/live",
    },
]


def norm(s):
    s = re.sub(r"\s*\((?:Secours\s+\d+|YouTube officiel)\)\s*$", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9à-ÿ]+", "", s.casefold().replace("œ", "oe"))


def entry_name(ext):
    return ext.split(",", 1)[1].strip() if "," in ext else "Unknown"


def url_of(block):
    return next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")


def parse():
    lines = open(PATH, encoding="utf-8").read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header = []
    groups = OrderedDict()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF:"):
            block = [line]
            i += 1
            while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
                block.append(lines[i]); i += 1
            group = dict(ATTR_RE.findall(block[0])).get("group-title", "International")
            groups.setdefault(group, []).append(block)
            continue
        if line.strip() and not line.startswith("# =====") and not line.startswith("# Secours YouTube officiels:"):
            header.append(line)
        i += 1
    return header, groups


def main():
    header, groups = parse()
    existing_urls = {url_of(b) for blocks in groups.values() for b in blocks if url_of(b)}
    added = 0
    for y in YOUTUBE:
        if y["url"] in existing_urls:
            continue
        id_aliases = {x.casefold() for x in y["ids"]}
        name_aliases = {norm(x) for x in y["names"]}
        match = None
        for g, blocks in groups.items():
            for b in blocks:
                attrs = dict(ATTR_RE.findall(b[0]))
                tid = attrs.get("tvg-id", "").casefold()
                if tid in id_aliases or norm(entry_name(b[0])) in name_aliases:
                    match = (g, b)
                    break
            if match:
                break
        if match:
            g, b = match
            attrs = dict(ATTR_RE.findall(b[0]))
            tid = attrs.get("tvg-id", y["fallback_id"])
            logo = attrs.get("tvg-logo", "")
            base = re.sub(r"\s*\(Secours\s+\d+\)\s*$", "", entry_name(b[0]), flags=re.I)
            block = [f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{g}",{base} (YouTube officiel)', y["url"]]
            groups[g].append(block)
        else:
            g = y["group"]
            groups.setdefault(g, []).append([
                f'#EXTINF:-1 tvg-id="{y["fallback_id"]}" tvg-logo="" group-title="{g}",{y["name"]} (YouTube officiel)',
                y["url"],
            ])
        existing_urls.add(y["url"])
        added += 1

    report = f"# Secours YouTube officiels: {added} liens /live ajoutés (aucune URL googlevideo temporaire)"
    header.insert(1 if header and header[0].startswith("#EXTM3U") else 0, report)
    out = header + [""]
    for g, blocks in groups.items():
        blocks.sort(key=lambda b: norm(entry_name(b[0])))
        out.append(f"# ===== {g.upper()} ({len(blocks)} entrées) =====")
        for b in blocks:
            out.extend(b)
        out.append("")
    open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(out).rstrip() + "\n")
    print(report)

if __name__ == "__main__":
    main()
