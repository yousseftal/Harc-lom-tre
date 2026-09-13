#!/usr/bin/env python3
import re
import sys
import ipaddress
from collections import defaultdict
from urllib.parse import urlparse
from urllib.request import Request, urlopen

OUTPUT = "france-maghreb.m3u"

# Every source below was previously shared. The Arabic/French language lists
# define the language scope; the other lists can only provide a better stream
# for a channel already identified as Arabic/French (or explicitly named as such).
SOURCES = [
    ("IPTV-org Arabic", "lang", "https://iptv-org.github.io/iptv/languages/ara.m3u"),
    ("IPTV-org French", "lang", "https://iptv-org.github.io/iptv/languages/fra.m3u"),
    ("IPTV-org France", "extra", "https://iptv-org.github.io/iptv/countries/fr.m3u"),
    ("IPTV-org Algeria", "extra", "https://iptv-org.github.io/iptv/countries/dz.m3u"),
    ("IPTV-org Morocco", "extra", "https://iptv-org.github.io/iptv/countries/ma.m3u"),
    ("IPTV-org Tunisia", "extra", "https://iptv-org.github.io/iptv/countries/tn.m3u"),
    ("IPTV-org Egypt", "extra", "https://iptv-org.github.io/iptv/countries/eg.m3u"),
    ("IPTV-org Saudi Arabia", "extra", "https://iptv-org.github.io/iptv/countries/sa.m3u"),
    ("IPTV-org UAE", "extra", "https://iptv-org.github.io/iptv/countries/ae.m3u"),
    ("IPTV-org Qatar", "extra", "https://iptv-org.github.io/iptv/countries/qa.m3u"),
    ("IPTV-org Arab region", "extra", "https://iptv-org.github.io/iptv/regions/arab.m3u"),
    ("IPTV-org Gulf", "extra", "https://iptv-org.github.io/iptv/regions/gcc.m3u"),
    ("Free-TV Arabic News", "arabic", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_zz_news_ar.m3u8"),
    ("Free-TV", "extra", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
    ("FreeCastHub", "extra", "https://raw.githubusercontent.com/freecasthub/public-iptv/main/playlist.m3u"),
    ("Chaipa demo", "extra", "https://www.chaipa.net/demo.m3u"),
]

COUNTRY_NAMES = {
    "FR":"France","DZ":"Algérie","MA":"Maroc","TN":"Tunisie","EG":"Égypte","SA":"Arabie saoudite","AE":"Émirats arabes unis","QA":"Qatar",
    "BH":"Bahreïn","KW":"Koweït","OM":"Oman","IQ":"Irak","JO":"Jordanie","LB":"Liban","SY":"Syrie","YE":"Yémen","LY":"Libye","SD":"Soudan",
    "PS":"Palestine","MR":"Mauritanie","SO":"Somalie","DJ":"Djibouti","KM":"Comores","BE":"Belgique","CH":"Suisse","CA":"Canada","LU":"Luxembourg",
    "MC":"Monaco","SN":"Sénégal","CI":"Côte d’Ivoire","CM":"Cameroun","CD":"R.D. Congo","CG":"Congo","GA":"Gabon","BJ":"Bénin","TG":"Togo",
    "BF":"Burkina Faso","ML":"Mali","NE":"Niger","GN":"Guinée","MG":"Madagascar","RW":"Rwanda","BI":"Burundi","HT":"Haïti","MU":"Maurice",
    "SC":"Seychelles","VU":"Vanuatu","NC":"Nouvelle-Calédonie","PF":"Polynésie française","DE":"Allemagne","CN":"Chine","RU":"Russie","GB":"Royaume-Uni",
    "US":"États-Unis","TR":"Turquie","INT":"International"
}
COUNTRY_ORDER = [
    "FR","DZ","MA","TN","EG","LB","JO","PS","IQ","SY","QA","AE","SA","KW","BH","OM","YE","LY","SD","MR",
    "BE","CH","CA","LU","MC","SN","CI","CM","CD","CG","GA","BJ","TG","BF","ML","NE","GN","MG","RW","BI","HT","MU","SC","VU","NC","PF"
]

# Exclude obvious subscription/adult services. The goal is free/public streams.
PAY_RE = re.compile(
    r"(?i)(canal\s*\+|canal\s*plus|be\s*in\s*sports?|\bocs\b|cin[ée]\s*\+|disney|netflix|dazn|hbo|paramount\s*\+|"
    r"rmc\s*sport|eurosport|foot\s*\+|golf\s*\+|multisports|s[ée]rie\s*club|\bab1\b|adult|xxx|porn)"
)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r"(?i)\s*(?:\((?:\d{3,4}[pi]|HD|FHD|UHD|4K)\)|\[(?:geo-blocked|not 24/7)\]|[ⓈⓎⓉⒹⒼ])\s*$")
DIRECT_RE = re.compile(r"(?i)(\.m3u8(?:[?&#]|$)|\.mpd(?:[?&#]|$)|\.ts(?:[?&#]|$)|/manifest(?:[?&#/]|$)|/playlist(?:[?&#/]|$)|/master(?:[?&#/]|$)|/index(?:[?&#/]|$))")


def fetch(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 M3U-Merger/2.0"})
    with urlopen(req, timeout=35) as r:
        return r.read().decode("utf-8", "replace")


def parse_m3u(text, source, kind):
    out, extinf, opts = [], None, []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            extinf, opts = line, []
        elif extinf and line.startswith("#"):
            opts.append(line)
        elif extinf:
            attrs = dict(ATTR_RE.findall(extinf))
            name = extinf.split(",", 1)[1].strip() if "," in extinf else attrs.get("tvg-name", "Unknown")
            out.append({"extinf":extinf,"opts":opts[:],"url":line,"attrs":attrs,"name":name,"source":source,"kind":kind})
            extinf, opts = None, []
    return out


def clean_name(name):
    n = name.strip()
    old = None
    while old != n:
        old = n
        n = QUALITY_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n)


def country_code(e):
    c = (e["attrs"].get("tvg-country") or "").strip().upper()
    if c:
        c = re.split(r"[,;/ ]+", c)[0]
        if len(c) == 2:
            return c
    tid = e["attrs"].get("tvg-id", "")
    m = re.search(r"\.([A-Za-z]{2})(?:@[^.]*)?$", tid)
    if m:
        return m.group(1).upper()
    gt = (e["attrs"].get("group-title") or "").casefold()
    aliases = {
        "france":"FR","algeria":"DZ","algérie":"DZ","morocco":"MA","maroc":"MA","tunisia":"TN","tunisie":"TN","egypt":"EG","égypte":"EG",
        "saudi arabia":"SA","qatar":"QA","united arab emirates":"AE","uae":"AE","lebanon":"LB","liban":"LB","jordan":"JO","jordanie":"JO",
        "palestine":"PS","iraq":"IQ","syria":"SY","kuwait":"KW","bahrain":"BH","oman":"OM","yemen":"YE","libya":"LY","sudan":"SD","mauritania":"MR",
        "belgium":"BE","belgique":"BE","switzerland":"CH","suisse":"CH","canada":"CA","luxembourg":"LU","monaco":"MC","senegal":"SN","sénégal":"SN"
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


def score(e):
    p = urlparse(e["url"])
    host = (p.hostname or "").lower()
    s = 8 if p.scheme == "https" else 0
    try:
        ipaddress.ip_address(host); s -= 12
    except ValueError:
        s += 6
    if any(x in host for x in ("france24.com","arte.tv","francetv","akamaized.net","infomaniak.com","easybroadcast.io","alarabiya.net","getaj.net","skynewsarabia.com","tanitweb.net","tv5monde.com")):
        s += 5
    if any(x in host for x in ("workers.dev","duckdns.org","work.gd","servehttp.com")):
        s -= 4
    if e["kind"] in ("lang", "arabic"):
        s += 5
    return s


def rewrite_group(extinf, code):
    label = COUNTRY_NAMES.get(code, code)
    if re.search(r'group-title="[^"]*"', extinf):
        return re.sub(r'group-title="[^"]*"', f'group-title="{label}"', extinf)
    pos = extinf.find(",")
    return extinf[:pos] + f' group-title="{label}"' + extinf[pos:] if pos >= 0 else extinf


def main():
    all_entries, failures = [], []
    allowed_ids, allowed_names = set(), set()

    # Language lists first: they are the authoritative language filter.
    for source, kind, url in SOURCES:
        try:
            entries = parse_m3u(fetch(url), source, kind)
            if kind in ("lang", "arabic"):
                for e in entries:
                    tid = e["attrs"].get("tvg-id", "").split("@", 1)[0].casefold()
                    if tid:
                        allowed_ids.add(tid)
                    allowed_names.add(clean_name(e["name"]).casefold())
            all_entries.extend(entries)
            print(f"{source}: {len(entries)}")
        except Exception as exc:
            failures.append(f"{source}: {exc}")
            print(f"WARNING {source}: {exc}", file=sys.stderr)

    candidates = []
    for e in all_entries:
        name = clean_name(e["name"])
        tid = e["attrs"].get("tvg-id", "").split("@", 1)[0].casefold()
        explicit = any(x in name.casefold() for x in (" arabic", " العربية", " français", " french", " francophone"))
        language_ok = e["kind"] in ("lang", "arabic") or (tid and tid in allowed_ids) or name.casefold() in allowed_names or explicit
        if not language_ok:
            continue
        if PAY_RE.search(name) or not direct_stream(e["url"]):
            continue
        e["clean_name"] = name
        e["country"] = country_code(e)
        candidates.append(e)

    # Exact URL dedupe.
    by_url = {}
    for e in candidates:
        u = e["url"].strip()
        if u not in by_url or score(e) > score(by_url[u]):
            by_url[u] = e

    # Channel dedupe. Quality/status suffixes are ignored, but regional names remain.
    by_channel = {}
    for e in by_url.values():
        normalized = re.sub(r"[^a-z0-9]+", "", e["clean_name"].casefold())
        key = (e["country"], normalized)
        if key not in by_channel or score(e) > score(by_channel[key]):
            by_channel[key] = e

    groups = defaultdict(list)
    for e in by_channel.values():
        groups[e["country"]].append(e)
    for code in groups:
        groups[code].sort(key=lambda x: x["clean_name"].casefold())

    order = {c:i for i,c in enumerate(COUNTRY_ORDER)}
    countries = sorted(groups, key=lambda c: (order.get(c, 999), COUNTRY_NAMES.get(c,c).casefold()))
    total = sum(len(groups[c]) for c in countries)
    if total < 100:
        raise RuntimeError(f"Only {total} channels; refusing overwrite. Failures: {failures}")

    lines = [
        "#EXTM3U",
        "# Chaînes arabes et francophones — flux gratuits/publics",
        f"# Total après déduplication: {total}",
        "# Classées par pays. Doublons, pages Web et chaînes payantes évidentes exclus.",
        "# Sources: IPTV-org, Free-TV, FreeCastHub, Chaipa",
        ""
    ]
    for code in countries:
        label = COUNTRY_NAMES.get(code, code)
        lines.append(f"# ===== {label.upper()} ({len(groups[code])}) =====")
        for e in groups[code]:
            lines.append(rewrite_group(e["extinf"], code))
            lines.extend(e["opts"])
            lines.append(e["url"])
        lines.append("")

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    print(f"Wrote {OUTPUT}: {total} unique Arabic/French channels, {len(countries)} countries")
    for failure in failures:
        print("Unavailable:", failure)

if __name__ == "__main__":
    main()
