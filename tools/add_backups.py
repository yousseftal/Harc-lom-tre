#!/usr/bin/env python3
import re
from collections import defaultdict
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
MAX_URLS_PER_CHANNEL = 3

SOURCES = [
    "https://iptv-org.github.io/iptv/languages/ara.m3u",
    "https://iptv-org.github.io/iptv/languages/fra.m3u",
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://iptv-org.github.io/iptv/countries/dz.m3u",
    "https://iptv-org.github.io/iptv/countries/ma.m3u",
    "https://iptv-org.github.io/iptv/countries/tn.m3u",
    "https://iptv-org.github.io/iptv/countries/eg.m3u",
    "https://iptv-org.github.io/iptv/countries/sa.m3u",
    "https://iptv-org.github.io/iptv/countries/ae.m3u",
    "https://iptv-org.github.io/iptv/countries/qa.m3u",
    "https://iptv-org.github.io/iptv/regions/arab.m3u",
    "https://iptv-org.github.io/iptv/regions/gcc.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_zz_news_ar.m3u8",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://raw.githubusercontent.com/freecasthub/public-iptv/main/playlist.m3u",
]

# Extra public URLs recently cross-checked on broadcaster/public IPTV indexes.
STATIC = {
    "skynewsarabia.ae": [
        "https://live-stream.skynewsarabia.com/c-horizontal-channel/horizontal-stream/index.m3u8",
        "https://stream.skynewsarabia.com/ott/ott.m3u8",
        "https://stream.skynewsarabia.com/hls/sna.m3u8",
    ],
    "alhadath.sa": [
        "https://av.alarabiya.net/alarabiapublish/alhadath.smil/playlist.m3u8",
        "https://shd-gcp-live.edgenextcdn.net/live/bitmovin-hadath/2ff87ec4c2f3ede35295a20637d9f8fd/index.m3u8",
        "https://live.alarabiya.net/alarabiapublish/alhadath.smil/playlist.m3u8",
    ],
    "medi1tvarabic.ma": [
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-arabic_g90v4ec/playlist.m3u8",
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-arabic_g90v4ec/playlist_dvr.m3u8",
    ],
    "medi1tvmaghreb.ma": [
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-maghreb_jnbspmg/playlist.m3u8",
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-maghreb_jnbspmg/playlist_dvr.m3u8",
    ],
    "medi1tvafrique.ma": [
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-afrique_tm7tu45/playlist.m3u8",
        "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-afrique_tm7tu45/playlist_dvr.m3u8",
    ],
    "france24arabic.fr": [
        "https://static.france24.com/live/F24_AR_HI_HLS/live_tv.m3u8",
        "https://live.france24.com/hls/live/2037222-b/F24_AR_HI_HLS/master_5000.m3u8",
    ],
    "france24french.fr": [
        "https://static.france24.com/live/F24_FR_HI_HLS/live_tv.m3u8",
        "https://live.france24.com/hls/live/2037179-b/F24_FR_HI_HLS/master_5000.m3u8",
    ],
    "dwArabic.de".casefold(): [
        "https://dwamdstream103.akamaized.net/hls/live/2015526/dwstream103/index.m3u8",
        "https://dwamdstream103.akamaized.net/hls/live/2015526/dwstream103/master.m3u8",
    ],
    "cgtnarabic.cn": [
        "https://arabic-livews.cgtn.com/hls/LSveq57bErWLinBnxosqjisZ220802LSTefTAS9zc9mpU08y3np9TH220802cd/playlist.m3u8",
        "https://news.cgtn.com/resource/live/arabic/cgtn-a.m3u8",
    ],
    "france3.fr": [
        "http://89.187.185.76:8080/France3/index.m3u8",
        "http://5.180.164.197:8080/FRANCE3/index.m3u8",
    ],
}

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r"(?i)\s*(?:\((?:\d{3,4}[pi]|HD|FHD|UHD|4K)\)|\[(?:geo-blocked|not 24/7)\]|[ⓈⓎⓉⒹⒼ])\s*$")


def fetch(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 M3U-Backup-Merger/1.0"})
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def clean_name(name):
    n = name.strip()
    old = None
    while old != n:
        old = n
        n = QUALITY_RE.sub("", n).strip()
    n = re.sub(r"\s*\(Secours \d+\)\s*$", "", n, flags=re.I)
    return re.sub(r"\s+", " ", n)


def norm_name(name):
    return re.sub(r"[^a-z0-9]+", "", clean_name(name).casefold())


def base_id(extinf):
    attrs = dict(ATTR_RE.findall(extinf))
    return attrs.get("tvg-id", "").split("@", 1)[0].casefold()


def is_direct(url):
    if not url.lower().startswith(("http://", "https://")):
        return False
    host = (urlparse(url).hostname or "").lower()
    if host in {"youtube.com","www.youtube.com","youtu.be","twitch.tv","www.twitch.tv","dailymotion.com","www.dailymotion.com"}:
        return False
    return ".m3u8" in url.lower() or ".mpd" in url.lower() or "/manifest" in url.lower() or "/playlist" in url.lower() or "/master" in url.lower() or "/index" in url.lower()


def parse_entries(text):
    out = []
    ext = None
    opts = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            ext, opts = line, []
        elif ext and line.startswith("#"):
            opts.append(line)
        elif ext:
            name = ext.split(",", 1)[1].strip() if "," in ext else "Unknown"
            out.append((ext, opts[:], line, name))
            ext, opts = None, []
    return out


def backup_extinf(ext, n):
    if "," not in ext:
        return ext
    left, name = ext.split(",", 1)
    name = clean_name(name)
    return f"{left},{name} (Secours {n})"


def main():
    with open(PATH, encoding="utf-8") as f:
        current = f.read().replace("\r\n", "\n").replace("\r", "\n")

    source_by_id = defaultdict(list)
    source_by_name = defaultdict(list)
    for url in SOURCES:
        try:
            for ext, opts, stream, name in parse_entries(fetch(url)):
                if not is_direct(stream):
                    continue
                tid = base_id(ext)
                if tid:
                    source_by_id[tid].append(stream)
                source_by_name[norm_name(name)].append(stream)
        except Exception as exc:
            print("Source unavailable:", url, exc)

    for tid, urls in STATIC.items():
        source_by_id[tid.casefold()].extend(urls)

    lines = current.split("\n")
    out = []
    backups_added = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("#EXTINF:"):
            if not line.startswith("# Flux de secours ajoutés:"):
                out.append(line)
            i += 1
            continue

        block = [line]
        i += 1
        while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
            block.append(lines[i])
            i += 1

        out.extend(block)
        primary_url = next((x for x in reversed(block[1:]) if x and not x.startswith("#")), None)
        if not primary_url:
            continue

        name = line.split(",", 1)[1].strip() if "," in line else "Unknown"
        tid = base_id(line)
        candidates = []
        if tid:
            candidates.extend(source_by_id.get(tid, []))
        candidates.extend(source_by_name.get(norm_name(name), []))

        seen = {primary_url.strip()}
        chosen = []
        for u in candidates:
            u = u.strip()
            if not is_direct(u) or u in seen:
                continue
            seen.add(u)
            chosen.append(u)
            if len(chosen) >= MAX_URLS_PER_CHANNEL - 1:
                break

        for n, u in enumerate(chosen, start=2):
            out.append(backup_extinf(line, n))
            # Keep HTTP options from the primary when useful.
            out.extend(x for x in block[1:] if x.startswith("#EXTVLCOPT:") or x.startswith("#KODIPROP:"))
            out.append(u)
            backups_added += 1

    # Insert a summary line near the top.
    insert_at = 1 if out and out[0].startswith("#EXTM3U") else 0
    out.insert(insert_at, f"# Flux de secours ajoutés: {backups_added} (jusqu'à {MAX_URLS_PER_CHANNEL} liens par chaîne)")

    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(f"Added {backups_added} backup stream entries")

if __name__ == "__main__":
    main()
