#!/usr/bin/env python3
import re
import ssl
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
MAX_URLS_PER_CHANNEL = 3
TIMEOUT = 8

# Candidates collected from official broadcaster domains, public broadcaster CDNs,
# current public indexes and forum/GitHub issue reports. They are NOT added unless
# a live HTTP request returns a valid HLS/DASH manifest at build time.
CANDIDATES = [
    # ALGERIA — HTA public distribution + AL24 public CDN
    {"id":"AL24News.dz","name":"AL24 News","country":"Algérie","urls":["https://cdn.live.easybroadcast.io/abr_corp/66_al24_u4yga6h/playlist.m3u8"]},
    {"id":"TV1.dz","name":"TV1 Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/PROGRAMME_NATIONAL/htatv/PROGRAMME_NATIONAL_720p/chunks.m3u8"]},
    {"id":"TV2.dz","name":"Canal Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/CANAL_ALGERIE/htatv/CANAL_ALGERIE_720p/chunks.m3u8"]},
    {"id":"TV3.dz","name":"TV3 Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/A3_HD/htatv/A3_HD_720p/chunks.m3u8"]},
    {"id":"TV4.dz","name":"TV4 Tamazight Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/TV_4/htatv/TV_4_720p/chunks.m3u8"]},
    {"id":"TV5.dz","name":"TV5 Coran Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/TV_5/htatv/TV_5_720p/chunks.m3u8"]},
    {"id":"TV6.dz","name":"TV6 Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/TV_6_HD/htatv/TV_6_HD_720p/chunks.m3u8"]},
    {"id":"TV7.dz","name":"TV7 El Maarifa","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/TV7_ELMAARIFA/htatv/TV7_ELMAARIFA_720p/chunks.m3u8"]},
    {"id":"TV8.dz","name":"TV8 Edhakira","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/TV8_EDHAKIRA/htatv/TV8_EDHAKIRA_720p/chunks.m3u8"]},
    {"id":"ElBiladTV.dz","name":"El Bilad TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/EL_BILAD/htatv/EL_BILAD_720p/chunks.m3u8"]},
    {"id":"BeurTV.dz","name":"Beur TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/Beur_TV/htatv/Beur_TV_720p/chunks.m3u8"]},
    {"id":"EchoroukTV.dz","name":"Echorouk TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/Echorouk_TV_HD/htatv/Echorouk_TV_HD_720p/chunks.m3u8"]},
    {"id":"ElDjazairiaOne.dz","name":"El Djazairia","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/EL_DJAZAIRIA_TV/htatv/EL_DJAZAIRIA_TV_720p/chunks.m3u8"]},
    {"id":"EnnaharTV.dz","name":"Ennahar TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/ENNAHAR_TV/htatv/ENNAHAR_TV_720p/chunks.m3u8"]},
    {"id":"EchoroukNews.dz","name":"Echorouk News","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/ECHOROUK_NEWS/htatv/ECHOROUK_NEWS_720p/chunks.m3u8"]},
    {"id":"BahiaTV.dz","name":"Bahia TV Oran","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/Bahia_TV/htatv/Bahia_TV_720p/chunks.m3u8"]},
    {"id":"ElHayatTVAlgerie.dz","name":"El Hayat TV Algérie","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/EL_HAYAT_TV_ALGERIE/htatv/EL_HAYAT_TV_ALGERIE_720p/chunks.m3u8"]},
    {"id":"ElHeddafTV.dz","name":"El Heddaf TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/EL_HEDDAF_TV/htatv/EL_HEDDAF_TV_720p/chunks.m3u8"]},
    {"id":"LinaTV.dz","name":"Lina TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/Lina_TV/htatv/Lina_TV_720p/chunks.m3u8"]},
    {"id":"SamiraTV.dz","name":"Samira TV","country":"Algérie","urls":["https://cdn02.hta.dz/abr_htatv/SamiraTV/htatv/SamiraTV_720p/chunks.m3u8"]},

    # MOROCCO — SNRT official domain + public 2M distribution
    {"id":"AlAoula.ma","name":"Al Aoula","country":"Maroc","urls":["https://streaming.snrtlive.ma/live/slaalaoula/slaalaoula.m3u8"]},
    {"id":"Arryadia.ma","name":"Arryadia","country":"Maroc","urls":["https://streaming.snrtlive.ma/live/slaarryadia/slaarryadia.m3u8"]},
    {"id":"TamazightTV.ma","name":"Tamazight TV","country":"Maroc","urls":["https://streaming.snrtlive.ma/live/slataamazight/slataamazight.m3u8"]},
    {"id":"Assadissa.ma","name":"Assadissa","country":"Maroc","urls":["https://streaming.snrtlive.ma/live/slaassadissa/slaassadissa.m3u8"]},
    {"id":"AlMaghribia.ma","name":"Al Maghribia","country":"Maroc","urls":["https://streaming.snrtlive.ma/live/slamaghribia/slamaghribia.m3u8","https://viamotionhsi.netplus.ch/live/eds/almaghribia/browser-HLS8/almaghribia.m3u8"]},
    {"id":"2M.ma","name":"2M","country":"Maroc","urls":["https://d3g87jnubafe6a.cloudfront.net/out/v1/1fa0fb3c8dec402994a6f7a7f6492b82/index.m3u8"]},

    # TUNISIA — only an additional public candidate not already in the main index
    {"id":"NessmaElJadida.tn","name":"Nessma El Jadida","country":"Tunisie","urls":["https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119176/nessmaejdida/playlist.m3u8"]},

    # EGYPT — public carriage of state channel
    {"id":"AlMasriyah.eg","name":"Al Masriyah","country":"Égypte","urls":["https://viamotionhsi.netplus.ch/live/eds/almasriyah/browser-HLS8/almasriyah.m3u8","https://netplus.zappr.stream/almasriyah.m3u8"]},

    # QATAR
    {"id":"QatarTV.qa","name":"Qatar TV","country":"Qatar","urls":["https://qatartv.akamaized.net/hls/live/2026573/qtv1/master.m3u8"]},
    {"id":"QatarTVTheHolyQuran.qa","name":"Qatar TV The Holy Quran","country":"Qatar","urls":["https://qatartv.akamaized.net/hls/live/20000612/qtvquran/master.m3u8"]},
    {"id":"AlJazeeraMubasher.qa","name":"Al Jazeera Mubasher","country":"Qatar","urls":["https://live-hls-web-ajm.getaj.net/AJM/index.m3u8"]},
    {"id":"AlRayyanTV.qa","name":"Al Rayyan","country":"Qatar","urls":["https://svs.itworkscdn.net/alrayyanlive/alrayyan.smil/playlist.m3u8"]},
    {"id":"AlRayyanOldTV.qa","name":"Al Rayyan Old TV","country":"Qatar","urls":["https://svs.itworkscdn.net/alrayyanqadeemlive/alrayyanqadeem.smil/playlist.m3u8"]},

    # SAUDI ARABIA — public religious streams + Globecast public feed
    {"id":"AlSaudiya.sa","name":"Al Saudiya","country":"Arabie saoudite","urls":["https://cdn-globecast.akamaized.net/live/eds/saudi_tv/hls_roku/index.m3u8"]},
    {"id":"AlQuranAlKareemTV.sa","name":"Al Quran Al Kareem TV","country":"Arabie saoudite","urls":["http://m.live.net.sa:1935/live/quran/gmswf.m3u8","http://m.live.net.sa:1935/live/quran/playlist.m3u8"]},
    {"id":"AlSunnahAlNabawiyahTV.sa","name":"Al Sunnah Al Nabawiyah TV","country":"Arabie saoudite","urls":["http://m.live.net.sa:1935/live/sunnah/gmswf.m3u8"]},

    # UAE
    {"id":"SharjahTV.ae","name":"Sharjah TV","country":"Émirats arabes unis","urls":["https://live.kwikmotion.com/smc1live/smc1tv.smil/playlist.m3u8","https://cdn-globecast.akamaized.net/live/eds/sharjah_tv/hls_roku/index.m3u8"]},
    {"id":"DubaiTV.ae","name":"Dubai TV","country":"Émirats arabes unis","urls":["https://dmieigthvll.cdn.mgmlcdn.com/dubaitvht/smil:dubaitv.stream.smil/playlist.m3u8"]},
    {"id":"DubaiOne.ae","name":"Dubai One","country":"Émirats arabes unis","urls":["http://dminnvll.cdn.mangomolo.com/dubaione/smil:dubaione.stream.smil/chunklist.m3u8"]},
    {"id":"AbuDhabiTV.ae","name":"Abu Dhabi TV","country":"Émirats arabes unis","urls":["https://admdn2.cdn.mangomolo.com/adtv/smil:adtv.stream.smil/playlist.m3u8"]},
    {"id":"SpacetoonArabic.ae","name":"Spacetoon Arabic","country":"Émirats arabes unis","urls":["https://live-uae-next.spacetoongo.com/ST_MENA_NEXT/hls/r9p2hjipmw2kl.m3u8"]},
]

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def base_id(extinf):
    attrs = dict(ATTR_RE.findall(extinf))
    return attrs.get("tvg-id", "").split("@", 1)[0].casefold()


def stream_url(block):
    return next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")


def probe(url):
    try:
        req = Request(url, headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36",
            "Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,application/dash+xml,*/*;q=0.8",
        })
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            code = getattr(r, "status", 200)
            data = r.read(32768)
            if code not in (200, 206):
                return False, f"HTTP {code}"
            head = data.lstrip()[:32768]
            low = url.casefold()
            if ".m3u8" in low or "playlist" in low or "master" in low or "chunk" in low:
                ok = b"#EXTM3U" in head or b"#EXT-X-" in head
            elif ".mpd" in low:
                ok = b"<MPD" in head or b"<mpd" in head
            else:
                ok = bool(data)
            return ok, f"HTTP {code}"
    except Exception as exc:
        return False, type(exc).__name__


with open(PATH, encoding="utf-8") as f:
    lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

header = []
groups = OrderedDict()
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("#EXTINF:"):
        block = [line]
        i += 1
        while i < len(lines) and lines[i] and not lines[i].startswith("#EXTINF:") and not lines[i].startswith("# ====="):
            block.append(lines[i])
            i += 1
        attrs = dict(ATTR_RE.findall(block[0]))
        country = attrs.get("group-title", "International")
        groups.setdefault(country, []).append(block)
        continue
    if not line.startswith("# =====") and line.strip():
        header.append(line)
    i += 1

existing = {}
for country, blocks in groups.items():
    for block in blocks:
        bid = base_id(block[0])
        if bid:
            existing.setdefault(bid, set()).add(stream_url(block))

all_urls = sorted({u for c in CANDIDATES for u in c["urls"]})
results = {}
with ThreadPoolExecutor(max_workers=16) as ex:
    future_map = {ex.submit(probe, u): u for u in all_urls}
    for fut in as_completed(future_map):
        url = future_map[fut]
        ok, status = fut.result()
        results[url] = ok
        print(("PASS" if ok else "FAIL"), status, url)

added = 0
channels_touched = 0
for c in CANDIDATES:
    bid = c["id"].casefold()
    live = [u for u in c["urls"] if results.get(u)]
    if not live:
        continue
    current_urls = existing.setdefault(bid, set())
    new_urls = [u for u in live if u not in current_urls]
    if not new_urls:
        continue
    room = max(0, MAX_URLS_PER_CHANNEL - len(current_urls))
    if room <= 0:
        continue
    new_urls = new_urls[:room]
    country = c["country"]
    groups.setdefault(country, [])
    had_channel = bool(current_urls)
    for idx, url in enumerate(new_urls, start=1):
        n = len(current_urls) + 1
        suffix = f" (Secours vérifié {n})" if had_channel or n > 1 else ""
        ext = f'#EXTINF:-1 tvg-id="{c["id"]}" group-title="{country}",{c["name"]}{suffix}'
        groups[country].append([ext, url])
        current_urls.add(url)
        added += 1
    channels_touched += 1

clean_header = [x for x in header if not x.startswith("# Ajouts vérifiés Internet:")]
insert_at = 1 if clean_header and clean_header[0].startswith("#EXTM3U") else 0
clean_header.insert(insert_at, f"# Ajouts vérifiés Internet: {added} flux actifs sur {channels_touched} chaînes")

out = clean_header + [""]
for country, blocks in groups.items():
    out.append(f"# ===== {country.upper()} ({len(blocks)} entrées) =====")
    for block in blocks:
        out.extend(block)
    out.append("")

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out).rstrip() + "\n")

print(f"Verified extras: added {added} live URLs across {channels_touched} channels; tested {len(all_urls)} candidate URLs")
