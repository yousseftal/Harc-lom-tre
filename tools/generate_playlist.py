#!/usr/bin/env python3
import re
import sys
import ipaddress
from collections import defaultdict
from urllib.parse import urlparse
from urllib.request import Request, urlopen

OUTPUT = "france-maghreb.m3u"

# Sources already shared in the conversation. The two language playlists are
# authoritative for deciding whether a channel is Arabic- or French-language.
SOURCES = [
    ("IPTV-org Arabic", "ar", "https://iptv-org.github.io/iptv/languages/ara.m3u"),
    ("IPTV-org French", "fr", "https://iptv-org.github.io/iptv/languages/fra.m3u"),
    ("IPTV-org France", "country", "https://iptv-org.github.io/iptv/countries/fr.m3u"),
    ("IPTV-org Algeria", "country", "https://iptv-org.github.io/iptv/countries/dz.m3u"),
    ("IPTV-org Morocco", "country", "https://iptv-org.github.io/iptv/countries/ma.m3u"),
    ("IPTV-org Tunisia", "country", "https://iptv-org.github.io/iptv/countries/tn.m3u"),
    ("IPTV-org Egypt", "country", "https://iptv-org.github.io/iptv/countries/eg.m3u"),
    ("IPTV-org Saudi Arabia", "country", "https://iptv-org.github.io/iptv/countries/sa.m3u"),
    ("IPTV-org UAE", "country", "https://iptv-org.github.io/iptv/countries/ae.m3u"),
    ("IPTV-org Qatar", "country", "https://iptv-org.github.io/iptv/countries/qa.m3u"),
    ("IPTV-org Arab region", "country", "https://iptv-org.github.io/iptv/regions/arab.m3u"),
    ("IPTV-org Gulf", "country", "https://iptv-org.github.io/iptv/regions/gcc.m3u"),
    ("Free-TV Arabic News", "ar", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_zz_news_ar.m3u8"),
    ("Free-TV", "mixed", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("FreeCastHub", "mixed", "https://raw.githubusercontent.com/freecasthub/public-iptv/main/playlist.m3u"),
    ("Chaipa demo", "mixed", "https://www.chaipa.net/demo.m3u"),
]

TARGET_COUNTRIES = {
    # Arabic-majority / Arabic broadcasting countries
    "DZ","MA","TN","EG","SA","AE","QA","BH","KW","OM","IQ","JO","LB","SY","YE","LY","SD","PS","MR","SO","DJ","KM",
    # Principal French-speaking origins and territories
    "FR","BE","CH","CA","LU","MC","SN","CI","CM","CD","CG","GA","BJ","TG","BF","ML","NE","GN","MG","RW","BI","HT","MU","SC","VU","NC","PF",
}

COUNTRY_NAMES = {
    "FR":"France","DZ":"Algérie","MA":"Maroc","TN":"Tunisie","EG":"Égypte","SA":"Arabie saoudite","AE":"Émirats arabes unis","QA":"Qatar",
    "BH":"Bahreïn","KW":"Koweït","OM":"Oman","IQ":"Irak","JO":"Jordanie","LB":"Liban","SY":"Syrie","YE":"Yémen","LY":"Libye","SD":"Soudan",
    "PS":"Palestine","MR":"Mauritanie","SO":"Somalie","DJ":"Djibouti","KM":"Comores","BE":"Belgique","CH":"Suisse","CA":"Canada","LU":"Luxembourg",
    "MC":"Monaco","SN":"Sénégal","CI":"Côte d’Ivoire","CM":"Cameroun","CD":"R.D. Congo","CG":"Congo","GA":"Gabon","BJ":"Bénin","TG":"Togo",
    "BF":"Burkina Faso","ML":"Mali","NE":"Niger","GN":"Guinée","MG":"Madagascar","RW":"Rwanda","BI":"Burundi","HT":"Haïti","MU":"Maurice",
    "SC":"Seychelles","VU":"Vanuatu","NC":"Nouvelle-Calédonie","PF":"Polynésie française","DE":"Allemagne","CN":"Chine","RU":"Russie","US":"États-Unis",
    "GB":"Royaume-Uni","TR":"Turquie","INT":"International"
}

COUNTRY_ORDER = [
    "FR","DZ","MA","TN","EG","LB","JO","PS","IQ","SY","QA","AE","SA","KW","BH","OM","YE","LY","SD","MR",
    "BE","CH","CA","LU","MC","SN","CI","CM","CD","CG","GA","BJ","TG","BF","ML","NE","GN","MG","RW","BI","HT","MU","SC","VU","NC","PF",
]

# Obvious subscription/pay-TV brands are deliberately excluded. This playlist
# is intended for free/public streams only.
PAY_RE = re.compile(
    r"(?i)(canal\s*\+|canal\s*plus|be\s*in\s*sports?|\bocs\b|cin[ée]\s*\+|disney|netflix|dazn|hbo|max\s*cinema|paramount\s*\+|"
    r"rmc\s*sport|eurosport|foot\s*\+|golf\s*\+|multisports|s[ée]rie\s*club|\bab1\b|adult|xxx|porn)"
)

DIRECT_RE = re.compile(r"(?i)(\.m3u8(?:[?&#]|$)|\.mpd(?:[?&#]|$)|\.ts(?:[?&#]|$)|/manifest(?:[?&#/]|$)|/playlist(?:[?&#/]|$)|/master(?:[?&#/]|$)|/index(?:[?&#/]|$))")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r"(?i)\s*(?:\((?:\d{3,4}[pi]|\d{3,4}p|HD|FHD|UHD|4K)\)|\[(?:geo-blocked|not 24/7)\]|[ⓈⓎⓉⒹⒼ])\s*$")


def fetch(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 M3U-Merger/1.0"})
    with urlopen(req, timeout=35) as r:
        return r.read().decode("utf-8", "replace")


def parse_m3u(text, source_name, source_kind):
    entries = []
    extinf = None
    opts = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            extinf = line
            opts = []
            continue
        if extinf and line.startswith("#"):
            opts.append(line)
            continue
        if extinf and not line.startswith("#"):
            attrs = dict(ATTR_RE.findall(extinf))
            name = extinf.split(",", 1)[1].strip() if "," in extinf else attrs.get("tvg-name", "Unknown")
            entries.append({"extinf":extinf,"opts":opts[:],"url":line,"attrs":attrs,"name":name,"source":source_name,"kind":source_kind})
            extinf = None
            opts = []
    return entries


def clean_name(name):
    n = name.strip()
    old = None
    while old != n:
        old = n
        n = QUALITY_RE.sub("", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def country_code(entry):
    attrs = entry["attrs"]
    c = (attrs.get("tvg-country") or "").strip().upper()
    if c:
        # Some lists use comma-separated country codes. Use the first origin.
        c = re.split(r"[,;/ ]+", c)[0]
        if len(c) == 2:
            return c
    tid = attrs.get("tvg-id", "")
    m = re.search(r"\.([A-Za-z]{2})(?:@[^.]*)?$", tid)
    if m:
        return m.group(1).upper()
    gt = (attrs.get("group-title") or "").casefold()
    aliases = {
        "france":"FR","algeria":"DZ","algérie":"DZ","morocco":"MA","maroc":"MA","tunisia":"TN","tunisie":"TN","egypt":"EG","égypte":"EG",
        "saudi arabia":"SA","qatar":"QA","united arab emirates":"AE","uae":"AE","emirats":"AE","lebanon":"LB","liban":"LB","jordan":"JO","jordanie":"JO",
        "palestine":"PS","iraq":"IQ","irak":"IQ","syria":"SY","syrie":"SY","kuwait":"KW","koweït":"KW","bahrain":"BH","bahreïn":"BH","oman":"OM",
        "yemen":"YE","yémen":"YE","libya":"LY","libye":"LY","sudan":"SD","soudan":"SD","mauritania":"MR","mauritanie":"MR","belgium":"BE","belgique":"BE",
        "switzerland":"CH","suisse":"CH","canada":"CA","luxembourg":"LU","monaco":"MC","senegal":"SN","sénégal":"SN","cameroon":"CM","cameroun":"CM"
    }
    for label, code in aliases.items():
        if label in gt:
            return code
    return "INT"


def direct_stream(url):
    if not url.lower().startswith(("http://", "https://")):
        return False
    host = (urlparse(url).hostname or "").lower()
    if host in {"youtube.com","www.youtube.com","youtu.be","twitch.tv","www.twitch.tv","dailymotion.com","www.dailymotion.com"}:
        return False
    return bool(DIRECT_RE.search(url)) or any(x in host for x in ("akamaized.net","cloudfront.net","amagi.tv","infomaniak.com","easybroadcast.io","getaj.net"))


def stream_score(entry):
    url = entry["url"]
    p = urlparse(url)
    host = (p.hostname or "").lower()
    score = 0
    if p.scheme == "https": score += 8
    try:
        ipaddress.ip_address(host)
        score -= 12
    except ValueError:
        score += 6
    officialish = ("france24.com","francetv","arte.tv","akamaized.net","infomaniak.com","easybroadcast.io","alarabiya.net","getaj.net","skynewsarabia.com","dw.com","medi1","tanitweb.net","tv5monde.com")
    if any(x in host for x in officialish): score += 5
    if any(x in host for x in ("workers.dev","duckdns.org","work.gd","servehttp.com")): score -= 4
    if entry["kind"] in ("ar","fr"): score += 5
    return score


def rewrite_extinf(entry, country):
    line = entry["extinf"]
    label = COUNTRY_NAMES.get(country, country)
    if re.search(r'group-title="[^"]*"', line):
        line = re.sub(r'group-title="[^"]*"', f'group-title="{label}"', line)
    else:
        comma = line.find(",")
        if comma >= 0:
            line = line[:comma] + f' group-title="{label}"' + line[comma:]
    return line


def main():
    all_entries = []
    authoritative_ids = set()
    authoritative_names = set()
    failures = []

    # Fetch language lists first; they define the language scope.
    for source_name, kind, url in SOURCES:
        try:
            text = fetch(url)
            parsed = parse_m3u(text, source_name, kind)
            if kind in ("ar", "fr"):
                for e in parsed:
                    tid = e["attrs"].get("tvg-id", "").split("@", 1)[0].casefold()
                    if tid: authoritative_ids.add(tid)
                    authoritative_names.add(clean_name(e["name"]).casefold())
            all_entries.extend(parsed)
            print(f"{source_name}: {len(parsed)} entries")
        except Exception as exc:
            failures.append(f"{source_name}: {exc}")
            print(f"WARNING {source_name}: {exc}", file=sys.stderr)

    candidates = []
    for e in all_entries:
        name = clean_name(e["name"])
        country = country_code(e)
        tid = e["attrs"].get("tvg-id", "").split("@", 1)[0].casefold()
        known_language = e["kind"] in ("ar", "fr") or (tid and tid in authoritative_ids) or name.casefold() in authoritative_names

        # Mixed/country lists are allowed only when they match a channel already
        # identified by the Arabic/French language indexes, or are from one of
        # the explicitly targeted Arabic/French countries.
        if not known_language and not (e["kind"] == "country" and country in TARGET_COUNTRIES):
            # A few language-explicit names from public mixed lists are useful.
            low = name.casefold()
            if not any(token in low for token in (" arabic"," العربية"," français"," french"," francophone")):
                continue
        if e["kind"] == "mixed" and not known_language:
            low = name.casefold()
            if not any(token in low for token in (" arabic"," العربية"," français"," french"," francophone")):
                continue
        if PAY_RE.search(name):
            continue
        if not direct_stream(e["url"]):
            continue
        e["clean_name"] = name
        e["country"] = country
        candidates.append(e)

    # De-duplicate exact stream URLs first, keeping the better quality candidate.
    by_url = {}
    for e in candidates:
        key = e["url"].strip()
        if key not in by_url or stream_score(e) > stream_score(by_url[key]):
            by_url[key] = e

    # Then de-duplicate channel names within each country. Resolution/availability
    # suffixes were removed by clean_name(), while real regional names remain.
    by_channel = {}
    for e in by_url.values():
        key = (e["country"], re.sub(r"[^a-z0-9]+", "", e["clean_name"].casefold()))
        if key not in by_channel or stream_score(e) > stream_score(by_channel[key]):
            by_channel[key] = e

    groups = defaultdict(list)
    for e in by_channel.values():
        groups[e["country"]].append(e)
    for code in groups:
        groups[code].sort(key=lambda e: e["clean_name"].casefold())

    order_index = {c:i for i,c in enumerate(COUNTRY_ORDER)}
    countries = sorted(groups, key=lambda c: (order_index.get(c, 999), COUNTRY_NAMES.get(c,c).casefold()))
    total = sum(len(groups[c]) for c in countries)
    if total < 50:
        raise RuntimeError(f"Only {total} channels after merge; refusing to overwrite existing playlist. Failures: {failures}")

    out = [
        "#EXTM3U",
        "# France + chaînes arabes/francophones — flux gratuits/publics",
        f"# Total après déduplication: {total}",
        "# Sources: IPTV-org, Free-TV, FreeCastHub, Chaipa",
        "# Les chaînes payantes évidentes et les liens de pages Web ont été exclus.",
        "",
    ]
    for code in countries:
        label = COUNTRY_NAMES.get(code, code)
        out.append(f"# ===== {label.upper()} ({len(groups[code])}) =====")
        for e in groups[code]:
            out.append(rewrite_extinf(e, code))
            out.extend(e["opts"])
            out.append(e["url"])
        out.append("")

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip() + "\n")
    print(f"Wrote {OUTPUT}: {total} unique channels in {len(countries)} country groups")
    if failures:
        print("Unavailable sources:")
        for x in failures: print(" -", x)

if __name__ == "__main__":
    main()
