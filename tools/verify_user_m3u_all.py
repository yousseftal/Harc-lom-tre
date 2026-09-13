#!/usr/bin/env python3
import ast
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.parse import urlparse

PLAYLIST = "france-maghreb.m3u"
IMPORTER = "tools/import_user_m3u_candidates.py"
TIMEOUT = 10
BLOCKED = ("edgenextcdn.net", "m-iptv.net", "sigma-iptv.net", "vip-max.com", "janjua.pw", "freechannelsonly.xyz")


def load_candidates():
    src = open(IMPORTER, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CANDIDATES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("CANDIDATES not found")


def probe(item):
    url = item["url"]
    try:
        host = (urlparse(url).hostname or "").casefold()
        if any(x in host for x in BLOCKED):
            return item, False, "blocked"
        req = Request(url, headers={"User-Agent":"Mozilla/5.0", "Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,*/*"})
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            code = getattr(r, "status", 200) or 200
            data = r.read(65536).decode("utf-8", "ignore")
            ctype = (r.headers.get("Content-Type") or "").casefold()
            ok = 200 <= code < 300 and ("#EXTM3U" in data or "#EXT-X-" in data or "mpegurl" in ctype)
            return item, ok, f"HTTP {code}"
    except Exception as exc:
        return item, False, type(exc).__name__


def fix_qatar_quran_alias(lines):
    alias = 'tvg-id="QatarTelevisionTheHolyQuran.qa"'
    canonical_prefix = 'tvg-id="QatarTVTheHolyQuran.qa'
    canonical_count = sum(1 for x in lines if x.startswith("#EXTINF:") and canonical_prefix in x)
    if canonical_count == 0:
        return lines, 0
    changed = 0
    out = []
    for line in lines:
        if line.startswith("#EXTINF:") and alias in line:
            line = line.replace(alias, 'tvg-id="QatarTVTheHolyQuran.qa@HD"')
            if "," in line:
                head, _ = line.split(",", 1)
                canonical_count += 1
                line = head + f",Qatar TV The Holy Quran (Secours {canonical_count})"
            changed += 1
        out.append(line)
    return out, changed


def main():
    candidates = load_candidates()
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(probe, c) for c in candidates]
        for fut in as_completed(futures):
            results.append(fut.result())
    active = 0
    for item, ok, why in sorted(results, key=lambda x: (x[0]["group"].casefold(), x[0]["name"].casefold())):
        if ok:
            active += 1
        print(("PASS" if ok else "FAIL"), why, item["group"], item["name"], item["url"])

    with open(PLAYLIST, encoding="utf-8") as f:
        lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [x for x in lines if not x.startswith("# Vérification fichier utilisateur:")]
    lines, alias_fixed = fix_qatar_quran_alias(lines)
    report = f"# Vérification fichier utilisateur: {len(results)} liens testés, {active} actifs; doublons renommés en secours: {alias_fixed}"
    at = 1 if lines and lines[0].startswith("#EXTM3U") else 0
    lines.insert(at, report)
    with open(PLAYLIST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    print(report)

if __name__ == "__main__":
    main()
