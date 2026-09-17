#!/usr/bin/env python3
import re
import ssl
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PATH = "france-maghreb.m3u"
TIMEOUT = 12
MAX_STREAMS = 4
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')

CANDIDATES = [
    # Algérie / Afrique du Nord - sites de chaîne ou CDN associés aux diffuseurs
    {"id":"EchoroukTV.dz","name":"Echorouk TV","group":"Algérie","url":"http://live.echoroukonline.com/live/EchoroukTV/playlist.m3u8"},
    {"id":"ChaineNordAfricaine.dz","name":"Chaîne Nord-Africaine","group":"Algérie","url":"https://live.creacast.com/cna/smil:cna.smil/playlist.m3u8"},

    # Chaînes arabophones internationales officiellement proposées en direct
    {"id":"SAT7Arabic.cy","name":"SAT-7 Arabic","group":"International arabe","url":"https://svs.itworkscdn.net/sat7arabiclive/sat7arabic.smil/playlist_dvr.m3u8"},
    {"id":"SAT7Kids.cy","name":"SAT-7 Kids","group":"International arabe","url":"https://svs.itworkscdn.net/sat7kidslive/sat7kids.smil/playlist_dvr.m3u8"},

    # Jordanie / Nilesat 7W - Roya confirme son direct et la fréquence Nilesat 11957 H sur son site officiel
    {"id":"RoyaTV.jo","name":"Roya TV","group":"Jordanie","url":"https://royatv-live.daioncdn.net/royatv/royatv.m3u8"},

    # Francophonie / Afrique
    {"id":"CongoPlanetTV.cd","name":"Congo Planet TV","group":"R.D. Congo","url":"https://radio.congoplanet.com/Congo_Planet_TV.sdp/Congo_Planet_TV/playlist.m3u8"},
    {"id":"CongoPlanetTV2.cd","name":"Congo Planet TV 2","group":"R.D. Congo","url":"https://radio.congoplanet.com/Congo_Planet_TV_Pop.sdp/Congo_Planet_TV_Pop/playlist.m3u8"},

    # France / francophonie - plateforme FAST gratuite reconnue
    {"id":"EuronewsFrench.fr","name":"Euronews Français","group":"France","url":"https://rakuten-euronews-2-fr.samsung.wurl.com/manifest/playlist.m3u8"},
]

BLOCKED = ("ip.xtremetv.eu","m-iptv.net","sigma-iptv.net","vip-max.com","janjua.pw","freechannelsonly.xyz")
ORDER = ["France","Algérie","Maroc","Tunisie","Égypte","Mauritanie","Liban","Jordanie","Palestine","Irak","Syrie","Qatar","Émirats arabes unis","Arabie saoudite","Koweït","Bahreïn","Oman","Yémen","Libye","Soudan","Djibouti","Comores","Sénégal","Côte d’Ivoire","Cameroun","Gabon","Tchad","Bénin","Togo","Burkina Faso","Mali","Niger","Guinée","R.D. Congo","Congo","Madagascar","Rwanda","Burundi","Maurice","Seychelles","Haïti","Canada","Belgique","Suisse","Luxembourg","Monaco","Chine","Allemagne","International arabe","International"]

def norm(s):
    s = re.sub(r'\s*\(Secours\s+\d+\)\s*$', '', s, flags=re.I).casefold().replace('œ','oe')
    return re.sub(r'[^a-z0-9à-ÿ]+','',s)
def name(ext): return ext.split(',',1)[1].strip() if ',' in ext else 'Unknown'
def url_of(block): return next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith('#')), '')
def safe(item):
    try:
        p=urlparse(item['url']); host=(p.hostname or '').casefold()
        return p.scheme in ('http','https') and host and not p.username and not p.password and not any(x in host for x in BLOCKED)
    except Exception: return False
def probe(item):
    if not safe(item): return False, 'blocked'
    try:
        req=Request(item['url'],headers={'User-Agent':'Mozilla/5.0','Accept':'application/vnd.apple.mpegurl,application/x-mpegURL,*/*'})
        with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:
            code=getattr(r,'status',200) or 200; data=r.read(131072).lower(); ctype=(r.headers.get('Content-Type') or '').casefold()
        ok=code in (200,206) and (b'#extm3u' in data or b'#ext-x-' in data or 'mpegurl' in ctype)
        return ok,f'HTTP {code}'
    except Exception as exc: return False,type(exc).__name__
def parse():
    lines=open(PATH,encoding='utf-8').read().replace('\r\n','\n').replace('\r','\n').split('\n'); header=[]; groups=OrderedDict(); i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith('#EXTINF:'):
            block=[line]; i+=1
            while i<len(lines) and lines[i] and not lines[i].startswith('#EXTINF:') and not lines[i].startswith('# ====='):
                block.append(lines[i]); i+=1
            group=dict(ATTR_RE.findall(block[0])).get('group-title','International'); groups.setdefault(group,[]).append(block); continue
        if line.strip() and not line.startswith('# =====') and not line.startswith('# Recherche approfondie 3:'): header.append(line)
        i+=1
    return header,groups
def add(groups,item):
    all_urls=set(); matches=[]; iid=item['id'].split('@',1)[0].casefold(); nn=norm(item['name'])
    for g,blocks in groups.items():
        for b in blocks:
            u=url_of(b)
            if u: all_urls.add(u)
            attrs=dict(ATTR_RE.findall(b[0])); bid=attrs.get('tvg-id','').split('@',1)[0].casefold()
            if (iid and iid==bid) or norm(name(b[0]))==nn: matches.append((g,b))
    if item['url'] in all_urls: return 'duplicate'
    if matches:
        urls={url_of(b) for _,b in matches if url_of(b)}
        if len(urls)>=MAX_STREAMS: return 'full'
        g,b=matches[0]; attrs=dict(ATTR_RE.findall(b[0])); tid=attrs.get('tvg-id',item['id']); logo=attrs.get('tvg-logo',''); base=re.sub(r'\s*\(Secours\s+\d+\)\s*$','',name(b[0]),flags=re.I)
        groups[g].append([f'#EXTINF:-1 tvg-id="{tid}" tvg-logo="{logo}" group-title="{g}",{base} (Secours {len(urls)+1})', item['url']]); return 'backup'
    g=item['group']; groups.setdefault(g,[]).append([f'#EXTINF:-1 tvg-id="{item["id"]}" tvg-logo="" group-title="{g}",{item["name"]}',item['url']]); return 'new'
def main():
    candidates=[x for x in CANDIDATES if safe(x)]; results={}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs={pool.submit(probe,x):x for x in candidates}
        for fut in as_completed(futs):
            x=futs[fut]; ok,why=fut.result(); results[x['url']]=ok; print(('PASS' if ok else 'FAIL'),why,x['group'],x['name'],x['url'])
    header,groups=parse(); active=added=new=backups=0; by_country={}
    for x in candidates:
        if not results.get(x['url']): continue
        active+=1; r=add(groups,x)
        if r in ('new','backup'):
            added+=1; new+=r=='new'; backups+=r=='backup'; by_country[x['group']]=by_country.get(x['group'],0)+1
    report=f'# Recherche approfondie 3: {len(candidates)} liens testés, {active} actifs, {added} ajoutés ({new} nouvelles chaînes, {backups} secours)'
    header.insert(1 if header and header[0].startswith('#EXTM3U') else 0,report)
    original={g:i for i,g in enumerate(groups)}
    def key(g): return (0,ORDER.index(g)) if g in ORDER else (1,original[g])
    out=header+['']
    for g in sorted(groups,key=key):
        blocks=groups[g]; blocks.sort(key=lambda b:norm(name(b[0]))); out.append(f'# ===== {g.upper()} ({len(blocks)} entrées) =====')
        for b in blocks: out.extend(b)
        out.append('')
    open(PATH,'w',encoding='utf-8',newline='\n').write('\n'.join(out).rstrip()+'\n')
    print(report)
    if by_country: print('Added by country:',', '.join(f'{k}={v}' for k,v in sorted(by_country.items())))
if __name__=='__main__': main()
