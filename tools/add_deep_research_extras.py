#!/usr/bin/env python3
import re
import ssl
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
TIMEOUT = 12
MAX_STREAMS_PER_CHANNEL = 4

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r'(?i)\s*(?:\((?:\d{3,4}[pi]|HD|FHD|UHD|4K|Secours\s+\d+)\)|\[(?:geo-blocked|not 24/7)\])\s*$')
PRIVATE_HOSTS = (
    "ip.xtremetv.eu", "m-iptv.net", "sigma-iptv.net", "vip-max.com",
    "janjua.pw", "freechannelsonly.xyz"
)
PREMIUM = (
    "canal+", "canal plus", "bein", "be in sport", "ocs", "ciné+", "cine+",
    "rmc sport", "eurosport", "dazn", "disney channel", "warner tv", "tcm",
    "planète+", "planete+", "polar+", "national geographic", "13ème rue", "syfy"
)
COUNTRY_ORDER = [
    "France", "Algérie", "Maroc", "Tunisie", "Égypte", "Mauritanie", "Liban",
    "Jordanie", "Palestine", "Irak", "Syrie", "Qatar", "Émirats arabes unis",
    "Arabie saoudite", "Koweït", "Bahreïn", "Oman", "Yémen", "Libye", "Soudan",
    "Djibouti", "Comores", "Sénégal", "Côte d’Ivoire", "Cameroun", "Gabon",
    "Tchad", "Bénin", "Togo", "Burkina Faso", "Mali", "Niger", "Guinée",
    "R.D. Congo", "Congo", "Madagascar", "Rwanda", "Burundi", "Maurice",
    "Seychelles", "Haïti", "Canada", "Belgique", "Suisse", "Luxembourg",
    "Monaco", "Chine", "Allemagne", "Royaume-Uni", "États-Unis", "International"
]

# Candidats issus de recherches approfondies dans les sites officiels des diffuseurs,
# leurs applications officielles, leurs CDN publics et des index publics servant
# uniquement à découvrir l'URL technique. Chaque URL est testée avant ajout.
CANDIDATES = [
    # France / francophonie internationale
    {"id":"AssembleeNationale.fr","name":"Assemblée nationale","group":"France","url":"http://assemblee-nationale.akamaized.net/live/live36/stream36.m3u8"},
    {"id":"France24French.fr","name":"France 24 Français","group":"France","url":"https://static.france24.com/live/F24_FR_HI_HLS/live_tv.m3u8"},
    {"id":"France24Arabic.fr","name":"France 24 العربية","group":"France","url":"https://static.france24.com/live/F24_AR_HI_HLS/live_tv.m3u8"},
    {"id":"BFMTV.fr","name":"BFM TV","group":"France","url":"https://live-cdn-stream-euw1.bfmtv.bct.nextradiotv.com/master.m3u8"},
    {"id":"Arte.fr","name":"Arte","group":"France","url":"https://artesimulcast.akamaized.net/hls/live/2031003/artelive_fr/index.m3u8"},
    {"id":"TV5MondeFBS.fr","name":"TV5 Monde FBS","group":"France","url":"https://ott.tv5monde.com/Content/HLS/Live/channel(fbs)/variant.m3u8"},
    {"id":"TV5MondeEurope.fr","name":"TV5 Monde Europe","group":"France","url":"https://ott.tv5monde.com/Content/HLS/Live/channel(europe)/variant.m3u8"},
    {"id":"TV5MondeInfo.fr","name":"TV5 Monde Info","group":"France","url":"https://ott.tv5monde.com/Content/HLS/Live/channel(info)/variant.m3u8"},
    {"id":"TV5MondeStyle.fr","name":"TV5 Monde Style","group":"France","url":"https://ott.tv5monde.com/Content/HLS/Live/channel(style1)/variant.m3u8"},
    {"id":"TiVi5Monde.fr","name":"TiVi5 Monde","group":"France","url":"https://ott.tv5monde.com/Content/HLS/Live/channel(tivi5)/variant.m3u8"},
    {"id":"CGTNFrench.cn","name":"CGTN Français","group":"Chine","url":"https://news.cgtn.com/resource/live/french/cgtn-f.m3u8"},

    # Maroc - SNRT / MEDI1 / 2M, avec anciennes et nouvelles routes publiques
    {"id":"2MMonde.ma","name":"2M Monde","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/2m_monde/hls_video_ts_tuhawxpiemz257adfc/2m_monde.m3u8"},
    {"id":"AlAoulaInternational.ma","name":"Al Aoula International","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/al_aoula_inter/hls_snrt/al_aoula_inter.m3u8"},
    {"id":"AlAoulaLaayoune.ma","name":"Al Aoula Laayoune","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/al_aoula_laayoune/hls_snrt/al_aoula_laayoune.m3u8"},
    {"id":"AlMaghribia.ma","name":"Al Maghribia","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/al_maghribia_snrt/hls_snrt/index.m3u8"},
    {"id":"Athaqafia.ma","name":"Athaqafia","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/arrabiaa/hls_snrt/index.m3u8"},
    {"id":"Arryadia.ma","name":"Arryadia","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/arriadia/hls_snrt/index.m3u8"},
    {"id":"Assadissa.ma","name":"Assadissa","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/assadissa/hls_snrt/index.m3u8"},
    {"id":"TamazightTV.ma","name":"Tamazight TV","group":"Maroc","url":"https://cdnamd-hls-globecast.akamaized.net/live/ramdisk/tamazight_tv8_snrt/hls_snrt/index.m3u8"},
    {"id":"Medi1TVArabic.ma","name":"Medi 1 TV Arabic","group":"Maroc","url":"https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-arabic_g90v4ec/playlist.m3u8"},
    {"id":"Medi1TVMaghreb.ma","name":"Medi 1 TV Maghreb","group":"Maroc","url":"https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-maghreb_jnbspmg/playlist.m3u8"},
    {"id":"Medi1TVAfrique.ma","name":"Medi 1 TV Afrique","group":"Maroc","url":"https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-afrique_tm7tu45/playlist.m3u8"},
    {"id":"Arryadia.ma","name":"Arryadia","group":"Maroc","url":"https://cdn.live.easybroadcast.io/ts_corp/73_arryadia-tnt_zcmwjdc/playlist_dvr.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"ExoPlayer"}},
    {"id":"AlAoula.ma","name":"Al Aoula","group":"Maroc","url":"https://streaming.snrtlive.ma/live/slaalaoula/slaalaoula.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"Mozilla/5.0"}},
    {"id":"Arryadia.ma","name":"Arryadia","group":"Maroc","url":"https://streaming.snrtlive.ma/live/slaarryadia/slaarryadia.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"Mozilla/5.0"}},
    {"id":"TamazightTV.ma","name":"Tamazight TV","group":"Maroc","url":"https://streaming.snrtlive.ma/live/slataamazight/slataamazight.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"Mozilla/5.0"}},
    {"id":"Assadissa.ma","name":"Assadissa","group":"Maroc","url":"https://streaming.snrtlive.ma/live/slaassadissa/slaassadissa.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"Mozilla/5.0"}},
    {"id":"AlMaghribia.ma","name":"Al Maghribia","group":"Maroc","url":"https://streaming.snrtlive.ma/live/slamaghribia/slamaghribia.m3u8","headers":{"Referer":"https://snrtlive.ma/","User-Agent":"Mozilla/5.0"}},

    # Jordanie
    {"id":"AlMamlakaTV.jo","name":"Al Mamlaka","group":"Jordanie","url":"https://almamlka-live.ercdn.net/almamlka/almamlka.m3u8"},
    {"id":"JordanTV.jo","name":"Jordan TV","group":"Jordanie","url":"https://jrtv-live.ercdn.net/jordanhd/jordanhd.m3u8"},
    {"id":"JordanTV.jo","name":"Jordan TV","group":"Jordanie","url":"https://jrtv-live.ercdn.net/jordanhd/jordanhd_1080p.m3u8"},
    {"id":"JordanSport.jo","name":"Jordan Sport","group":"Jordanie","url":"https://jrtv-live.ercdn.net/jordansporthd/jordansporthd.m3u8"},

    # Bahreïn
    {"id":"BahrainTV.bh","name":"Bahrain TV","group":"Bahreïn","url":"https://5c7b683162943.streamlock.net/live/ngrp:bahraintvmain_all/playlist.m3u8"},
    {"id":"BahrainInternational.bh","name":"Bahrain International","group":"Bahreïn","url":"https://5c7b683162943.streamlock.net/live/ngrp:bahraininternational_all/playlist.m3u8"},
    {"id":"BahrainQuran.bh","name":"Bahrain Quran","group":"Bahreïn","url":"https://5c7b683162943.streamlock.net/live/ngrp:bahrainquran_all/playlist.m3u8"},

    # Koweït - chaînes publiques du ministère de l'Information
    {"id":"KTV1.kw","name":"Kuwait TV 1","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtv1.m3u8"},
    {"id":"KTV2.kw","name":"Kuwait TV 2","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtv2.m3u8"},
    {"id":"KTVAlMajlis.kw","name":"Kuwait Al Majlis","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvmajlis.m3u8"},
    {"id":"KTVAlQurain.kw","name":"Kuwait Al Qurain","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvqurain.m3u8"},
    {"id":"KTVArabi.kw","name":"Kuwait Al Arabi","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvarabi.m3u8"},
    {"id":"KTVEthraa.kw","name":"Kuwait Ethraa","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvethraa.m3u8"},
    {"id":"KTVKids.kw","name":"Kuwait Kids","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvkids.m3u8"},
    {"id":"KTVSports.kw","name":"Kuwait Sport","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvsports.m3u8"},
    {"id":"KTVSportsPlus.kw","name":"Kuwait Sport Plus","group":"Koweït","url":"https://hiplayer.hibridcdn.net/t/kwmedia-kwtvsportsplus.m3u8"},

    # Oman
    {"id":"OmanTV.om","name":"Oman TV","group":"Oman","url":"https://partneta.cdn.mgmlcdn.com/omantv/smil:omantv.stream.smil/chunklist.m3u8"},

    # Palestine
    {"id":"PalestineTV.ps","name":"Palestine TV","group":"Palestine","url":"https://pbc.furrera.ps/palestinehd/tracks-v3a1/mono.m3u8"},

    # Syrie - chaîne gratuite, plusieurs CDN officiels/publics
    {"id":"SyriaTV.sy","name":"Syria TV","group":"Syrie","url":"https://live.kwikmotion.com/syriatvlive/syriatv.smil/playlist_dvr.m3u8"},
    {"id":"SyriaTV.sy","name":"Syria TV","group":"Syrie","url":"https://svs.itworkscdn.net/syriatvlive/syriatv.smil/playlist_dvr.m3u8"},
    {"id":"SyriaTV.sy","name":"Syria TV","group":"Syrie","url":"https://stream.ads.ottera.tv/playlist.m3u8?network_id=6017"},

    # Canada francophone
    {"id":"TeleQuebec.ca","name":"Télé-Québec","group":"Canada","url":"https://bcovlive-a.akamaihd.net/575d86160eb143458d51f7ab187a4e68/us-east-1/6101674910001/playlist.m3u8"},
    {"id":"SavoirMedia.ca","name":"Savoir Média","group":"Canada","url":"https://hls.savoir.media/live/stream.m3u8"},
    {"id":"IciRadioCanadaTele.ca","name":"ICI Télé","group":"Canada","url":"https://rcavlive.akamaized.net/hls/live/696615/xcancbft/master.m3u8"},
    {"id":"IciRadioCanadaTele.ca","name":"ICI Télé","group":"Canada","url":"https://amdici.akamaized.net/hls/live/873426/ICI-Live-Stream/master.m3u8"},

    # Cameroun - service public CRTV
    {"id":"CRTV.cm","name":"CRTV","group":"Cameroun","url":"https://live1.acangroup.org:1929/crtv/crtv_all/playlist.m3u8"},
    {"id":"CRTVNews.cm","name":"CRTV News","group":"Cameroun","url":"https://live1.acangroup.org:1929/publiclive/crtv_news/playlist.m3u8"},

    # Côte d'Ivoire - RTI Play est gratuit; anciennes routes CDN testées à chaque build
    {"id":"RTI1.ci","name":"RTI 1","group":"Côte d’Ivoire","url":"https://www.enovativecdn.com:4433/rticdn/smil:rti1.smil/playlist.m3u8"},
    {"id":"RTI2.ci","name":"RTI 2","group":"Côte d’Ivoire","url":"https://www.enovativecdn.com:4433/rticdn/smil:rti2.smil/playlist.m3u8"},
    {"id":"La3.ci","name":"La 3","group":"Côte d’Ivoire","url":"https://www.enovativecdn.com:4433/rticdn/smil:rti3.smil/playlist.m3u8"},

    # Mali - ORTM public
    {"id":"ORTM1.ml","name":"ORTM 1","group":"Mali","url":"https://cs2.push2stream.com/ORTM-DVR/playlist.m3u8"},

    # Burkina Faso - RTB public
    {"id":"RTB.bf","name":"RTB","group":"Burkina Faso","url":"https://edge12.vedge.infomaniak.com/livecast/ik:rtblive1_8/manifest.m3u8"},
    {"id":"RTB3.bf","name":"RTB 3","group":"Burkina Faso","url":"https://edge13.vedge.infomaniak.com/livecast/ik:rtb3-1/manifest.m3u8"},

    # Bénin - service public SRTB, avec référent officiel
    {"id":"ORTBTV.bj","name":"Bénin TV","group":"Bénin","url":"https://strhls.streamakaci.tv/ortb/ortb1-multi/playlist.m3u8","headers":{"Referer":"https://srtb.bj/","User-Agent":"Mozilla/5.0"}},
    {"id":"ADOTV.bj","name":"ADO TV","group":"Bénin","url":"https://strhls.streamakaci.tv/ortb/ortb2-multi/playlist.m3u8","headers":{"Referer":"https://srtb.bj/","User-Agent":"Mozilla/5.0"}},

    # Gabon - Gabon 1ère public
    {"id":"Gabon1ere.ga","name":"Gabon 1ère","group":"Gabon","url":"https://uvotv-aniview.global.ssl.fastly.net/hls/live/2119695/gabon1ere/playlist.m3u8"},

    # Tchad - ONAMA / Télé Tchad
    {"id":"TeleTchad.td","name":"Télé Tchad","group":"Tchad","url":"https://strhlslb01.streamakaci.tv/str_tchad_tchad/str_tchad_multi/playlist.m3u8"},

    # Sénégal - chaînes gratuites diffusées publiquement via aCAN
    {"id":"SenTV.sn","name":"Sen TV","group":"Sénégal","url":"https://live3.acangroup.org:1929/acanabr/sentv.stream_all/playlist.m3u8"},
    {"id":"DTV.sn","name":"DTV","group":"Sénégal","url":"https://live3.acangroup.org:1929/acanabr/dtv.stream_all/acanabr/dtv.stream_SD/chunks.m3u8"},
    {"id":"7TV.sn","name":"7 TV","group":"Sénégal","url":"https://live3.acangroup.org:1929/publiclive/septtv.stream/chunks.m3u8"},
    {"id":"WalfTV.sn","name":"Walf TV","group":"Sénégal","url":"https://live3.acangroup.org:1929/publiclive/walftv.stream/chunks.m3u8"},
]


def norm_name(name):
    n = name.strip()
    old = None
    while old != n:
        old = n
        n = QUALITY_RE.sub("", n).strip()
    n = re.sub(r'\s*\(Secours\s+\d+\)\s*$', '', n, flags=re.I)
    n = n.casefold().replace("œ", "oe")
    return re.sub(r'[^a-z0-9à-ÿ]+', '', n)


def block_url(block):
    return next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")


def entry_name(extinf):
    return extinf.split(",", 1)[1].strip() if "," in extinf else "Unknown"


def safe_candidate(item):
    low_name = item["name"].casefold()
    if any(x in low_name for x in PREMIUM):
        return False
    try:
        p = urlparse(item["url"])
    except Exception:
        return False
    host = (p.hostname or "").casefold()
    if p.scheme not in ("http", "https") or p.username or p.password:
        return False
    return not any(x in host for x in PRIVATE_HOSTS)


def probe(item):
    if not safe_candidate(item):
        return False, "blocked"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,application/dash+xml,*/*;q=0.8",
    }
    headers.update(item.get("headers") or {})
    try:
        req = Request(item["url"], headers=headers)
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            code = getattr(r, "status", 200) or 200
            data = r.read(131072)
            ctype = (r.headers.get("Content-Type") or "").casefold()
        if code not in (200, 206):
            return False, f"HTTP {code}"
        low = data.lstrip().lower()
        is_hls = b"#extm3u" in low or b"#ext-x-" in low or "mpegurl" in ctype
        is_dash = b"<mpd" in low or "dash+xml" in ctype
        return bool(is_hls or is_dash), f"HTTP {code}"
    except Exception as exc:
        return False, type(exc).__name__


def opts_for(item):
    headers = item.get("headers") or {}
    out = []
    if headers.get("Referer"):
        out.append(f'#EXTVLCOPT:http-referrer={headers["Referer"]}')
    if headers.get("User-Agent"):
        out.append(f'#EXTVLCOPT:http-user-agent={headers["User-Agent"]}')
    return out


def parse_playlist():
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
                block.append(lines[i]); i += 1
            attrs = dict(ATTR_RE.findall(block[0]))
            group = attrs.get("group-title", "International")
            groups.setdefault(group, []).append(block)
            continue
        if line.strip() and not line.startswith("# =====") and not line.startswith("# Recherche approfondie:"):
            header.append(line)
        i += 1
    return header, groups


def add_item(groups, item):
    all_urls = set()
    matches = []
    needle_id = item["id"].split("@", 1)[0].casefold()
    needle_name = norm_name(item["name"])
    for group, blocks in groups.items():
        for block in blocks:
            url = block_url(block)
            if url:
                all_urls.add(url)
            attrs = dict(ATTR_RE.findall(block[0]))
            bid = attrs.get("tvg-id", "").split("@", 1)[0].casefold()
            if (needle_id and bid == needle_id) or norm_name(entry_name(block[0])) == needle_name:
                matches.append((group, block))
    if item["url"] in all_urls:
        return "duplicate"
    if matches:
        target_group = matches[0][0]
        current_urls = {block_url(b) for _, b in matches if block_url(b)}
        if len(current_urls) >= MAX_STREAMS_PER_CHANNEL:
            return "full"
        primary = matches[0][1]
        attrs = dict(ATTR_RE.findall(primary[0]))
        tid = attrs.get("tvg-id", item["id"])
        logo = attrs.get("tvg-logo", "")
        name = re.sub(r'\s*\(Secours\s+\d+\)\s*$', '', entry_name(primary[0]), flags=re.I)
        n = len(current_urls) + 1
        ext = f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{target_group}",{name} (Secours {n})'
        groups.setdefault(target_group, []).append([ext] + opts_for(item) + [item["url"]])
        return "backup"
    group = item["group"]
    ext = f'#EXTINF:-1 tvg-id="{item["id"]}" tvg-logo="" group-title="{group}",{item["name"]}'
    groups.setdefault(group, []).append([ext] + opts_for(item) + [item["url"]])
    return "new"


def group_sort_key(name, original_index):
    try:
        return (0, COUNTRY_ORDER.index(name), name.casefold())
    except ValueError:
        return (1, original_index, name.casefold())


def main():
    candidates = [x for x in CANDIDATES if safe_candidate(x)]
    results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(probe, item): item for item in candidates}
        for fut in as_completed(futures):
            item = futures[fut]
            ok, why = fut.result()
            results[item["url"]] = ok
            print(("PASS" if ok else "FAIL"), why, item["group"], item["name"], item["url"])

    header, groups = parse_playlist()
    active = added = new_channels = backups = 0
    by_country = {}
    for item in candidates:
        if not results.get(item["url"]):
            continue
        active += 1
        result = add_item(groups, item)
        if result in ("new", "backup"):
            added += 1
            new_channels += result == "new"
            backups += result == "backup"
            by_country[item["group"]] = by_country.get(item["group"], 0) + 1

    report = (
        f"# Recherche approfondie: {len(candidates)} liens publics testés, {active} actifs, "
        f"{added} ajoutés ({new_channels} nouvelles chaînes, {backups} secours)"
    )
    insert_at = 1 if header and header[0].startswith("#EXTM3U") else 0
    header.insert(insert_at, report)

    original_order = {name: i for i, name in enumerate(groups.keys())}
    ordered_names = sorted(groups.keys(), key=lambda n: group_sort_key(n, original_order[n]))
    out = header + [""]
    for group in ordered_names:
        blocks = groups[group]
        blocks.sort(key=lambda b: norm_name(entry_name(b[0])))
        out.append(f"# ===== {group.upper()} ({len(blocks)} entrées) =====")
        for block in blocks:
            out.extend(block)
        out.append("")

    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(report)
    if by_country:
        print("Added by country:", ", ".join(f"{k}={v}" for k, v in sorted(by_country.items())))

if __name__ == "__main__":
    main()
