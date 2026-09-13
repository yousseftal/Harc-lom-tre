#!/usr/bin/env python3
import re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

PATH = "france-maghreb.m3u"
TIMEOUT = 8
MAX_URLS_PER_CHANNEL = 3

# Public/free Tunisian stream candidates gathered from broadcaster/public indexes
# and public GitHub stream reports. A URL is only added if it returns a valid
# HLS/DASH manifest at build time. Private credential-based IPTV servers are excluded.
CANDIDATES = [
    {"id":"HannibalTV.tn","name":"Hannibal TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120686/hannibaltv/playlist.m3u8",
    ]},
    {"id":"ElhiwarEttounsiTV.tn","name":"El Hiwar Ettounsi TV","headers":{"User-Agent":"TNAgexpl212C"},"urls":[
        "http://217.182.137.206/elhiwar.m3u8",
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120686/elhiwarettounsi/playlist.m3u8",
    ]},
    {"id":"AttessiaTV.tn","name":"Attessia TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119051/attesiatv/playlist.m3u8",
    ]},
    {"id":"NessmaElJadida.tn","name":"Nessma El Jadida","urls":[
        "https://fl1002.bozztv.com/ga-nessmatv/tracks-v1a1/mono.m3u8",
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119176/nessmaejdida/playlist.m3u8",
        "https://shls-live-ak.akamaized.net/out/v1/119ae95bbc91462093918a7c6ba11415/index.m3u8",
    ]},
    {"id":"CarthagePlus.tn","name":"Carthage+","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120681/carthageplus/playlist.m3u8",
    ]},
    {"id":"TelvzaTV.tn","name":"Telvza TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120681/telvzatv/playlist.m3u8",
    ]},
    {"id":"TunisnaTV.tn","name":"Tunisna TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120681/tunisna/playlist.m3u8",
    ]},
    {"id":"AlJanoubiyaTV.tn","name":"Al Janoubiya TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120686/aljanoubiatv/playlist.m3u8",
    ]},
    {"id":"AlInsenTV.tn","name":"Al Insen TV","urls":[
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120686/alinsentv/playlist.m3u8",
    ]},
    {"id":"EssaidaTV.tn","name":"Essaida TV","urls":[
        "https://app.rtvli.com/hls/stream/index.m3u8",
    ]},
    {"id":"SahelTV.tn","name":"Sahel TV","urls":[
        "http://142.44.214.231:1935/saheltv/myStream/playlist.m3u8",
    ]},
    {"id":"TunisieImmobilierTV.tn","name":"Tunisie Immobilier TV","urls":[
        "https://5ac31d8a4c9af.streamlock.net/tunimmob/myStream/playlist.m3u8",
    ]},
    {"id":"IFMTV.tn","name":"IFM TV","urls":[
        "https://ythls.onrender.com/channel/UCvPW0VhnTcxYjWIxCvMlw2Q.m3u8",
    ]},
    {"id":"JawharaTV.tn","name":"Jawhara TV","urls":[
        "https://streaming.toutech.net/live/jtv/index.m3u8",
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2120681/jawharafmtv/playlist.m3u8",
    ]},
    {"id":"MosaiqueFM.tn","name":"Mosaïque FM","urls":[
        "https://cdn.live.easybroadcast.io/abr_corp/63_mosaique-fm_rn56tgl/playlist_dvr.m3u8",
        "https://webcam.mosaiquefm.net:1936/mosatv/studio/playlist.m3u8",
    ]},
    {"id":"ElWatania1.tn","name":"El Watania 1","urls":[
        "http://live.watania1.tn:1935/live/watanya1.stream/playlist.m3u8",
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119176/tunisianat/playlist.m3u8",
    ]},
    {"id":"ElWatania2.tn","name":"El Watania 2","headers":{"User-Agent":"TNAgexpl212C"},"urls":[
        "http://217.182.137.206/tunisie2.m3u8",
        "http://live.watania2.tn:1935/live/watanya2.stream/playlist.m3u8",
        "https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119176/tunisianat2/playlist.m3u8",
    ]},
]

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def valid_manifest(url, headers=None):
    h = {"User-Agent":"Mozilla/5.0"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=TIMEOUT) as r:
            status = getattr(r, "status", 200)
            data = r.read(262144).decode("utf-8", "ignore")
        ok = status == 200 and ("#EXTM3U" in data[:4096] or "<MPD" in data[:8192])
        print(("PASS" if ok else "FAIL"), f"HTTP {status}", url)
        return ok
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        print("FAIL", type(exc).__name__, url)
        return False


def base_id(extinf):
    attrs = dict(ATTR_RE.findall(extinf))
    return attrs.get("tvg-id", "").split("@", 1)[0].casefold()


def parse_blocks(lines):
    blocks = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            b = [lines[i]]
            i += 1
            while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
                b.append(lines[i])
                i += 1
            blocks.append(b)
        else:
            i += 1
    return blocks


def stream_url(block):
    for line in reversed(block[1:]):
        if line and not line.startswith("#"):
            return line.strip()
    return None


def extinf(channel, suffix=""):
    name = channel["name"] + suffix
    return f'#EXTINF:-1 tvg-id="{channel["id"]}" group-title="Tunisie",{name}'


def main():
    with open(PATH, encoding="utf-8") as f:
        lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Remove prior summary so repeated builds stay clean.
    lines = [x for x in lines if not x.startswith("# Ajouts Tunisie vérifiés:")]
    blocks = parse_blocks(lines)
    existing_urls = {u for b in blocks if (u := stream_url(b))}
    by_id = {}
    for b in blocks:
        tid = base_id(b[0])
        if tid:
            by_id.setdefault(tid, []).append(b)

    new_blocks = []
    tested = 0
    added_urls = 0
    added_channels = 0

    for ch in CANDIDATES:
        good = []
        for url in ch["urls"]:
            tested += 1
            if url in existing_urls:
                good.append(url)
            elif valid_manifest(url, ch.get("headers")):
                good.append(url)
        # de-dupe while keeping order
        good = list(dict.fromkeys(good))
        if not good:
            continue

        tid = ch["id"].casefold()
        current = by_id.get(tid, [])
        current_urls = [stream_url(b) for b in current if stream_url(b)]
        available_slots = max(0, MAX_URLS_PER_CHANNEL - len(current_urls))
        candidates = [u for u in good if u not in existing_urls and u not in current_urls][:available_slots]
        if not candidates:
            continue

        if current:
            # Add only backups; existing primary remains unchanged.
            start = len(current_urls) + 1
            for idx, url in enumerate(candidates, start=start):
                new_blocks.append([extinf(ch, f" (Secours {idx})"), url])
                existing_urls.add(url)
                added_urls += 1
        else:
            # First working URL becomes the channel; remaining URLs become backups.
            for idx, url in enumerate(candidates, start=1):
                suffix = "" if idx == 1 else f" (Secours {idx})"
                new_blocks.append([extinf(ch, suffix), url])
                existing_urls.add(url)
                added_urls += 1
            added_channels += 1

    # Insert new Tunisian blocks at end of Tunisia section.
    if new_blocks:
        start = next((i for i,x in enumerate(lines) if x.startswith("# ===== TUNISIE")), None)
        if start is None:
            raise RuntimeError("Tunisia section not found")
        end = next((i for i in range(start+1, len(lines)) if lines[i].startswith("# =====")), len(lines))
        insert = []
        for b in new_blocks:
            insert.extend(b)
        if end > 0 and lines[end-1] == "":
            end -= 1
        lines[end:end] = insert

    # Recount Tunisian entries and update the section header.
    count = sum(1 for x in lines if x.startswith("#EXTINF:") and 'group-title="Tunisie"' in x)
    for i,x in enumerate(lines):
        if x.startswith("# ===== TUNISIE"):
            lines[i] = f"# ===== TUNISIE ({count} entrées) ====="
            break

    insert_at = 1 if lines and lines[0].startswith("#EXTM3U") else 0
    lines.insert(insert_at, f"# Ajouts Tunisie vérifiés: {added_urls} flux ajoutés, {added_channels} nouvelles chaînes, {tested} candidats testés")

    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    print(f"Tunisia extras: {added_urls} URLs added, {added_channels} new channels; tested {tested}")

if __name__ == "__main__":
    main()
