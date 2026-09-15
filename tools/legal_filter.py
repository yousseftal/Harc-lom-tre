#!/usr/bin/env python3
import ipaddress
import re
from urllib.parse import urlparse

PATH = "france-maghreb.m3u"

# URLs/hosts that should not be redistributed in this public playlist.
# Includes private credentialled IPTV hosts, known unauthorised relays and
# CDN families explicitly identified as unsuitable for redistribution here.
BLOCKED = (
    "ip.xtremetv.eu",
    "m-iptv.net",
    "sigma-iptv.net",
    "vip-max.com",
    "janjua.pw",
    "freechannelsonly.xyz",
    "mbc1-enc.edgenextcdn.net",
    "shls-live-enc.edgenextcdn.net",
    "wanasah-prod-dub-enc.edgenextcdn.net",
    "shd-gcp-live.edgenextcdn.net/live/bitmovin-",
    "d2hng5r56zpsbw.cloudfront.net",
    "d2lfa0y84k5bwn.cloudfront.net",
    "d2ow8h651gs7dx.cloudfront.net",
)

# Obvious subscription/premium services must never be added just because an
# unauthorised public-looking relay happens to answer HTTP 200.
PREMIUM_RE = re.compile(
    r"(?i)(canal\s*\+|canal\s*plus|be\s*in\s*sports?|\bocs\b|cin[ée]\s*\+|"
    r"rmc\s*sport|eurosport|dazn|disney\s*channel|warner\s*tv|\btcm\b|"
    r"plan[èe]te\s*\+|polar\s*\+|national\s*geographic|13[èe]me\s*rue|syfy)"
)

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

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
removed = []
for block in entries:
    url = next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")
    name = block[0].split(",", 1)[1] if "," in block[0] else block[0]
    low = url.casefold()
    blocked = any(b.casefold() in low for b in BLOCKED)
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        blocked = blocked or bool(parsed.username or parsed.password) or not host
        if host:
            try:
                ipaddress.ip_address(host)
                blocked = True
            except ValueError:
                pass
    except Exception:
        blocked = True
    blocked = blocked or bool(PREMIUM_RE.search(name))
    if blocked:
        removed.append((name, url))
        continue
    kept.append(block)

# Rebuild by country so the playlist remains tidy.
groups = {}
order = []
for block in kept:
    attrs = dict(ATTR_RE.findall(block[0]))
    country = attrs.get("group-title", "International")
    if country not in groups:
        groups[country] = []
        order.append(country)
    groups[country].append(block)

clean_header = []
for line in header:
    if line.startswith("# Filtre légal:"):
        continue
    if line.strip():
        clean_header.append(line)
clean_header.insert(1 if clean_header and clean_header[0].startswith("#EXTM3U") else 0,
                    f"# Filtre légal: {len(removed)} flux privés/premium/à risque exclus")

out = clean_header + [""]
for country in order:
    blocks = groups[country]
    out.append(f"# ===== {country.upper()} ({len(blocks)} entrées) =====")
    for block in blocks:
        out.extend(block)
    out.append("")

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out).rstrip() + "\n")

print(f"Legal filter: removed {len(removed)} entries")
for name, url in removed[:80]:
    print("REMOVED", name, url)
