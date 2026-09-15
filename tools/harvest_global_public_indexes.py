#!/usr/bin/env python3
import ipaddress
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
TIMEOUT = 9
MAX_STREAMS = 4
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

SOURCES = [
    ("dearbulut online", "https://dearbulut.github.io/iptv/playlists/online.m3u"),
    ("FreeWorldTV", "https://raw.githubusercontent.com/HermesGR/FreeWorldTV/master/README.m3u"),
    ("iptv-restream", "https://raw.githubusercontent.com/iptv-restream/channels/master/channels.m3u8"),
    ("mayaxcn getM3U8", "https://raw.githubusercontent.com/mayaxcn/getM3U8/master/tv.txt"),
]

BLOCKED_HOST_TOKENS = (
    "xtream", "m-iptv", "sigma-iptv", "vip-max", "janjua", "freechannelsonly",
    "fullspeed.tv", "tntendirect", "bozztv", "data-stream.top", "alteox.app"
)
PREMIUM_RE = re.compile(
    r"(?i)(canal\s*\+|canal\s*plus|be\s*in\s*sports?|\bocs\b|cin[ée]\s*\+|"
    r"rmc\s*sport|eurosport|dazn|disney\s*channel|warner\s*tv|\btcm\b|"
    r"plan[èe]te\s*\+|polar\s*\+|national\s*geographic|13[èe]me\s*rue|syfy)"
)
TRUSTED_HOST_FRAGMENTS = (
    "akamaized.net", "akamaihd.net", "cloudfront.net", "wurl.com", "amagi.tv",
    "infomaniak.com", "easybroadcast.io", "streamlock.net", "itworkscdn.net",
    "mgmlcdn.com", "mangomolo.com", "kwikmotion.com", "acangroup.org",
    "streamakaci.tv", "wowza.com", "fastly.net", "cdn.orange.com", "vidgyor.com",
    "bestream.io", "technocdn.com", "octivid.com", "logichost.in", "live.net.sa",
    "getaj.net", "alarabiya.net", "skynewsarabia.com", "france24.com", "bfmtv",
    "cgtn.com", "savoir.media", "rttv.com", "alabbassia.com", "i-news.tv",
    "tanitweb.net", "creacast.com", "echoroukonline.com", "congoplanet.com",
    "nrjaudio.fm", "streamakaci", "radio-canada.ca", "akamaized.net"
)


def fetch(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 Global-Public-Stream-Scanner/1.0"})
    with urlopen(req, timeout=25, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", "replace")


def norm_name(s):
    s = re.sub(r"\s*\(Secours\s+\d+\)\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[\[(](?:\d{3,4}[pi]|HD|FHD|UHD|4K|SD|Geo-blocked|Not 24/7)[^\])]*[\])]\s*$", "", s, flags=re.I)
    s = s.replace("Ⓨ", "").replace("Ⓓ", "").replace("Ⓢ", "").replace("œ", "oe").casefold()
    return re.sub(r"[^a-z0-9à-ÿ]+", "", s)


def clean_name(s):
    s = re.sub(r"\s*\(Secours\s+\d+\)\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_playlist(text):
    out = []
    ext = None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            ext = line
            continue
        if ext and not line.startswith("#"):
            attrs = dict(ATTR_RE.findall(ext))
            name = ext.split(",", 1)[1].strip() if "," in ext else attrs.get("tvg-name", "")
            out.append({"name":name, "url":line, "id":attrs.get("tvg-id", "")})
            ext = None
            continue
        if not line.startswith("#") and ",http" in line:
            n, u = line.split(",", 1)
            if u.startswith(("http://", "https://")):
                out.append({"name":n.strip(), "url":u.strip(), "id":""})
    return out


def parse_current(text):
    entries = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].startswith("#EXTINF:"):
            i += 1
            continue
        ext = lines[i]
        block = [ext]
        i += 1
        while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
            block.append(lines[i]); i += 1
        attrs = dict(ATTR_RE.findall(ext))
        name = ext.split(",", 1)[1].strip() if "," in ext else "Unknown"
        url = next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")
        entries.append({"ext":ext,"attrs":attrs,"name":name,"url":url,"block":block})
    return entries


def safe_url(name, url):
    if PREMIUM_RE.search(name):
        return False
    if not url.startswith(("http://", "https://")):
        return False
    low = url.casefold()
    if "youtube.com" in low or "youtu.be" in low or "dailymotion.com" in low:
        return False
    try:
        p = urlparse(url); host = (p.hostname or "").casefold()
        if p.username or p.password or not host:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
    except Exception:
        return False
    if any(x in host for x in BLOCKED_HOST_TOKENS):
        return False
    if not any(x in host for x in TRUSTED_HOST_FRAGMENTS):
        return False
    return any(x in low for x in (".m3u8", ".mpd", "/manifest", "/playlist", "/master", "/index", "chunklist"))


def probe(item):
    try:
        req = Request(item["url"], headers={"User-Agent":"Mozilla/5.0", "Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,application/dash+xml,*/*"})
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            code = getattr(r, "status", 200) or 200
            data = r.read(131072).lower()
            ctype = (r.headers.get("Content-Type") or "").casefold()
        ok = 200 <= code < 300 and (b"#extm3u" in data or b"#ext-x-" in data or b"<mpd" in data or "mpegurl" in ctype or "dash+xml" in ctype)
        return ok, f"HTTP {code}"
    except Exception as exc:
        return False, type(exc).__name__


def main():
    current_text = open(PATH, encoding="utf-8").read()
    current = parse_current(current_text)
    by_id = {}
    by_name = {}
    counts = {}
    urls = {e["url"] for e in current if e["url"]}
    for e in current:
        base_id = e["attrs"].get("tvg-id", "").split("@", 1)[0].casefold()
        key = base_id or norm_name(e["name"])
        counts[key] = counts.get(key, 0) + 1
        if base_id and base_id not in by_id:
            by_id[base_id] = e
        nn = norm_name(e["name"])
        if nn and nn not in by_name:
            by_name[nn] = e

    candidates = []
    seen = set()
    source_stats = {}
    for label, source_url in SOURCES:
        try:
            ext_entries = parse_playlist(fetch(source_url))
        except Exception as exc:
            print("SOURCE_FAIL", label, type(exc).__name__)
            source_stats[label] = [0, 0]
            continue
        matched = 0
        for x in ext_entries:
            base_id = x["id"].split("@", 1)[0].casefold() if x["id"] else ""
            target = by_id.get(base_id) if base_id else None
            if not target:
                target = by_name.get(norm_name(x["name"]))
            if not target:
                continue
            if x["url"] in urls or x["url"] in seen or not safe_url(target["name"], x["url"]):
                continue
            key = target["attrs"].get("tvg-id", "").split("@", 1)[0].casefold() or norm_name(target["name"])
            if counts.get(key, 0) >= MAX_STREAMS:
                continue
            seen.add(x["url"])
            candidates.append({"target":target, "url":x["url"], "source":label, "key":key})
            matched += 1
        source_stats[label] = [len(ext_entries), matched]
        print("SOURCE", label, len(ext_entries), "entries", matched, "candidates")

    results = []
    with ThreadPoolExecutor(max_workers=24) as pool:
        futs = {pool.submit(probe, c):c for c in candidates}
        for fut in as_completed(futs):
            c = futs[fut]
            ok, why = fut.result()
            results.append((c, ok, why))
            print(("PASS" if ok else "FAIL"), why, c["source"], c["target"]["name"], c["url"])

    added = []
    per_key = dict(counts)
    for c, ok, why in sorted(results, key=lambda r:(r[0]["target"]["attrs"].get("group-title", ""), r[0]["target"]["name"], r[0]["url"])):
        if not ok:
            continue
        key = c["key"]
        if per_key.get(key, 0) >= MAX_STREAMS:
            continue
        t = c["target"]
        group = t["attrs"].get("group-title", "International")
        tid = t["attrs"].get("tvg-id", "")
        logo = t["attrs"].get("tvg-logo", "")
        base = clean_name(t["name"])
        n = per_key.get(key, 0) + 1
        ext = f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{group}",{base} (Secours {n})'
        added.append((group, ext, c["url"], c["source"]))
        per_key[key] = n
        urls.add(c["url"])

    lines = current_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [x for x in lines if not x.startswith("# Récolte mondiale d'index publics:")]
    report = f"# Récolte mondiale d'index publics: {len(candidates)} candidats testés, {sum(1 for _,ok,_ in results if ok)} actifs, {len(added)} secours ajoutés"
    at = 1 if lines and lines[0].startswith("#EXTM3U") else 0
    lines.insert(at, report)
    if added:
        lines.append("")
        for group, ext, url, source in added:
            lines.append(ext)
            lines.append(url)
    open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines).rstrip() + "\n")
    print(report)
    for label, stats in source_stats.items():
        print("SOURCE_SUMMARY", label, "parsed", stats[0], "matched", stats[1])

if __name__ == "__main__":
    main()
