#!/usr/bin/env python3
import re
import ssl
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
SOURCES = ("https://www.m3u.cl/lista/total.m3u", "https://m3u.cl/lista/total.m3u")
TIMEOUT = 10
MAX_CANDIDATES = 80
MAX_STREAMS_PER_CHANNEL = 3

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
PREMIUM = (
    "canal+", "ocs", "cine+", "ciné+", "bein", "rmc sport", "eurosport",
    "warner tv", "tcm", "disney channel", "canal j", "planete+", "planète+",
    "national geographic", "13eme rue", "13ème rue", "syfy", "polar+",
)
BLOCKED_HOSTS = (
    "ip.xtremetv.eu", "m-iptv.net", "sigma-iptv.net", "vip-max.com",
    "janjua.pw", "freechannelsonly.xyz",
)
RELEVANT = (
    "france", "français", "francais", "french", "francophone", "tv5", "bfm",
    "euronews", "africanews", "africa 24", "arte", "cgtn france",
    "alger", "algérie", "algerie", "maroc", "morocco", "tunisie", "tunisia",
    "egypt", "egypte", "égypte", "qatar", "saudi", "arab", "palestine",
    "iraq", "irak", "liban", "lebanon", "jordan", "syria", "syrie",
    "yemen", "oman", "kuwait", "bahrain", "uae", "emirates", "émirats",
    "dubai", "sharjah", "abu dhabi", "mauritania", "mauritanie",
    "al jazeera", "al arabiya", "al hadath", "medi1",
)

def clean_url(url):
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))

def norm_name(name):
    s = name.casefold()
    s = re.sub(r'\b(?:fhd|uhd|4k|hd|sd|1080p|720p)\b', ' ', s)
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'[^a-z0-9à-ÿ]+', ' ', s)
    return ' '.join(s.split())

def stream_url(block):
    return next((clean_url(x) for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")

def entry_name(extinf):
    return extinf.rsplit(",", 1)[-1].strip()

def infer_group(text):
    x = text.casefold()
    mapping = [
        (("alger", "algérie", "algerie"), "Algérie"), (("maroc", "morocco", "medi1"), "Maroc"),
        (("tunisie", "tunisia"), "Tunisie"), (("egypt", "egypte", "égypte"), "Égypte"),
        (("qatar",), "Qatar"), (("saudi",), "Arabie saoudite"),
        (("uae", "emirates", "émirats", "dubai", "sharjah", "abu dhabi"), "Émirats arabes unis"),
        (("iraq", "irak"), "Irak"), (("liban", "lebanon"), "Liban"), (("palestine",), "Palestine"),
        (("jordan",), "Jordanie"), (("syria", "syrie"), "Syrie"), (("kuwait",), "Koweït"),
        (("bahrain",), "Bahreïn"), (("oman",), "Oman"), (("mauritania", "mauritanie"), "Mauritanie"),
    ]
    for keys, group in mapping:
        if any(k in x for k in keys): return group
    if any(k in x for k in ("france", "français", "francais", "french", "tv5", "bfm", "arte")): return "France"
    return "International arabe/francophone"

def probe(url):
    try:
        req = Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,application/dash+xml,*/*;q=0.8"})
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            code = getattr(r, "status", 200); data = r.read(65536)
        if code not in (200, 206): return False, f"HTTP {code}"
        head = data.lstrip(); low = url.casefold()
        if ".m3u8" in low or "playlist" in low or "manifest" in low or "master" in low: ok = b"#EXTM3U" in head or b"#EXT-X-" in head
        elif ".mpd" in low: ok = b"<MPD" in head or b"<mpd" in head
        else: ok = False
        return ok, f"HTTP {code}"
    except Exception as exc: return False, type(exc).__name__

def fetch_source():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36",
        "Referer": "https://www.m3u.cl/",
        "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    last = None
    ctx = ssl.create_default_context()
    for source in SOURCES:
        try:
            req = Request(source, headers=headers)
            with urlopen(req, timeout=15, context=ctx) as r:
                data = r.read(5_000_000).decode("utf-8", "ignore")
            if "#EXTM3U" in data[:4096]: return data
        except Exception as exc:
            last = exc
    if last: raise last
    raise RuntimeError("No valid M3U.CL playlist returned")

def parse_m3u(txt):
    lines = txt.replace("\r\n", "\n").replace("\r", "\n").split("\n"); out = []; i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            ext = lines[i].strip(); attrs = dict(ATTR_RE.findall(ext)); name = entry_name(ext); j = i + 1; url = ""
            while j < len(lines) and not lines[j].startswith("#EXTINF:"):
                if lines[j].strip() and not lines[j].startswith("#"): url = lines[j].strip(); break
                j += 1
            if url: out.append({"id":attrs.get("tvg-id", ""),"name":name,"logo":attrs.get("tvg-logo", ""),"group":attrs.get("group-title", ""),"url":url})
        i += 1
    return out

try:
    source_entries = parse_m3u(fetch_source())
except Exception as exc:
    print("M3U.CL source fetch failed:", type(exc).__name__); source_entries = []

candidates = []; seen = set()
for e in source_entries:
    hay = f'{e["name"]} {e["group"]} {e["id"]}'.casefold()
    if not any(k in hay for k in RELEVANT) or any(k in hay for k in PREMIUM): continue
    try: p = urlsplit(e["url"])
    except Exception: continue
    host = p.netloc.casefold()
    if p.scheme not in ("http", "https") or p.username or p.password or any(b in host for b in BLOCKED_HOSTS): continue
    u = clean_url(e["url"]); low = u.casefold()
    if u in seen or not any(x in low for x in (".m3u8", "playlist", "manifest", "master", ".mpd")): continue
    seen.add(u); e["url"] = u; e["country"] = infer_group(hay); candidates.append(e)
    if len(candidates) >= MAX_CANDIDATES: break

with open(PATH, encoding="utf-8") as f: lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
header = []; groups = OrderedDict(); i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("#EXTINF:"):
        block = [line]; i += 1
        while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="): block.append(lines[i]); i += 1
        attrs = dict(ATTR_RE.findall(block[0])); group = attrs.get("group-title", "International"); groups.setdefault(group, []).append(block); continue
    if not line.startswith("# =====") and line.strip() and not line.startswith("# M3U.CL vérifié:"): header.append(line)
    i += 1
existing_urls = set(); name_index = {}
for group, blocks in groups.items():
    for block in blocks:
        u = stream_url(block)
        if u: existing_urls.add(u)
        nn = norm_name(entry_name(block[0]))
        if nn: name_index.setdefault(nn, []).append((group, block))
results = {}
with ThreadPoolExecutor(max_workers=16) as ex:
    futs = {ex.submit(probe, e["url"]): e for e in candidates}
    for fut in as_completed(futs):
        e = futs[fut]; ok, status = fut.result(); results[e["url"]] = ok; print(("PASS" if ok else "FAIL"), status, e["name"], e["url"])
active = sum(1 for e in candidates if results.get(e["url"])); added = new_channels = backups = 0
for e in candidates:
    u = e["url"]
    if not results.get(u) or u in existing_urls: continue
    nn = norm_name(e["name"]); matches = name_index.get(nn, [])
    if matches:
        group, primary = matches[0]; current_urls = {stream_url(b) for _, b in matches if stream_url(b)}
        if len(current_urls) >= MAX_STREAMS_PER_CHANNEL: continue
        attrs = dict(ATTR_RE.findall(primary[0])); tid = attrs.get("tvg-id", e.get("id", "")); logo = attrs.get("tvg-logo", e.get("logo", "")); num = len(current_urls) + 1
        ext = f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{group}",{entry_name(primary[0])} (Secours {num})'; block = [ext, u]
        groups.setdefault(group, []).append(block); name_index.setdefault(nn, []).append((group, block)); backups += 1
    else:
        group = e["country"]; tid = e.get("id", "") or "M3UCL"; logo = e.get("logo", "")
        ext = f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{group}",{e["name"]}'; block = [ext, u]
        groups.setdefault(group, []).append(block); name_index.setdefault(nn, []).append((group, block)); new_channels += 1
    existing_urls.add(u); added += 1
header.insert(1 if header and header[0].startswith("#EXTM3U") else 0, f"# M3U.CL vérifié: {len(candidates)} candidats arabes/francophones testés, {active} actifs, {added} ajoutés ({new_channels} nouvelles chaînes, {backups} secours)")
out = header + [""]
for group, blocks in groups.items():
    out.append(f"# ===== {group.upper()} ({len(blocks)} entrées) =====")
    for block in blocks: out.extend(block)
    out.append("")
with open(PATH, "w", encoding="utf-8", newline="\n") as f: f.write("\n".join(out).rstrip() + "\n")
print(f"M3U.CL extras: {len(candidates)} tested, {active} active, {added} added")
