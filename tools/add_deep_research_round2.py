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
    # Tunisie - Télévision Tunisienne, routes TanitWeb observées actives en 2026
    {"id":"ElWatania1.tn","name":"El Watania 1","group":"Tunisie","url":"https://sw1.tanitweb.net/TunisiaTV/_definst_/watania1/chunklist.m3u8"},
    {"id":"ElWatania1.tn","name":"El Watania 1","group":"Tunisie","url":"https://sw1.tanitweb.net/TunisiaTV/_definst_/watania1/playlist.m3u8?DVR"},
    {"id":"ElWatania2.tn","name":"El Watania 2","group":"Tunisie","url":"https://sw1.tanitweb.net/TunisiaTV/_definst_/watania2/chunklist.m3u8"},
    {"id":"ElWatania2.tn","name":"El Watania 2","group":"Tunisie","url":"https://sw1.tanitweb.net/TunisiaTV/_definst_/watania2/playlist.m3u8?DVR"},

    # Koweït - CDN public du bouquet du ministère de l'Information
    {"id":"KTV1.kw","name":"Kuwait TV 1","group":"Koweït","url":"https://kwtktv1ta.cdn.mangomolo.com/ktv1/smil:ktv1.stream.smil/chunklist.m3u8"},
    {"id":"KTV2.kw","name":"Kuwait TV 2","group":"Koweït","url":"https://kwtktv2ta.cdn.mangomolo.com/ktv2/smil:ktv2.stream.smil/chunklist.m3u8"},
    {"id":"KTVAlQurain.kw","name":"Kuwait Al Qurain","group":"Koweït","url":"https://kwtktvaqta.cdn.mangomolo.com/ktvaq/smil:tktvaq.stream.smil/chunklist.m3u8"},
    {"id":"KTVArabe.kw","name":"Kuwait Al Arabi","group":"Koweït","url":"https://kwtktvata.cdn.mangomolo.com/ktva/smil:tktva.stream.smil/chunklist.m3u8"},
    {"id":"KTVEthraa.kw","name":"Kuwait Ethraa","group":"Koweït","url":"https://kwtethta.cdn.mangomolo.com/eth/smil:eth.stream.smil/chunklist.m3u8"},
    {"id":"KTVNews.kw","name":"Kuwait News","group":"Koweït","url":"https://kwtkbta.cdn.mangomolo.com/kb/smil:kb.stream.smil/chunklist.m3u8"},
    {"id":"KTVSport.kw","name":"Kuwait Sport","group":"Koweït","url":"https://kwtspta.cdn.mangomolo.com/sp/smil:sp.stream.smil/chunklist.m3u8"},
    {"id":"KTVSportPlus.kw","name":"Kuwait Sport Plus","group":"Koweït","url":"https://kwtsplta.cdn.mangomolo.com/spl/smil:spl.stream.smil/chunklist.m3u8"},
    {"id":"KTV1.kw","name":"Kuwait TV 1","group":"Koweït","url":"https://svs.itworkscdn.net/ktv1live/ktv1.smil/playlist.m3u8"},
    {"id":"KTV2.kw","name":"Kuwait TV 2","group":"Koweït","url":"https://svs.itworkscdn.net/ktv2live/ktv2.smil/playlist.m3u8"},
    {"id":"KTVArabe.kw","name":"Kuwait Al Arabi","group":"Koweït","url":"https://svs.itworkscdn.net/ktvarabelive/karabe.smil/playlist.m3u8"},
    {"id":"KTVAlMajlis.kw","name":"Kuwait Al Majlis","group":"Koweït","url":"https://svs.itworkscdn.net/ktvalmajlislive/kalmajlis.smil/playlist.m3u8"},

    # Oman - chaînes annoncées par le ministère de l'Information
    {"id":"OmanTVCultural.om","name":"Oman Cultural","group":"Oman","url":"https://partwota.cdn.mgmlcdn.com/omcultural/smil:omcultural.stream.smil/chunklist.m3u8"},
    {"id":"OmanTVMubashir.om","name":"Oman Mubasher","group":"Oman","url":"https://partwota.cdn.mgmlcdn.com/omlive/smil:omlive.stream.smil/chunklist.m3u8"},
    {"id":"OmanSportsTV.om","name":"Oman Sports TV","group":"Oman","url":"https://partneta.cdn.mgmlcdn.com/omsport/smil:omsport.stream.smil/chunklist.m3u8"},
]

BLOCKED = ("ip.xtremetv.eu","m-iptv.net","sigma-iptv.net","vip-max.com","janjua.pw","freechannelsonly.xyz")
ORDER = ["France","Algérie","Maroc","Tunisie","Égypte","Mauritanie","Liban","Jordanie","Palestine","Irak","Syrie","Qatar","Émirats arabes unis","Arabie saoudite","Koweït","Bahreïn","Oman","Yémen","Libye","Soudan","Sénégal","Côte d’Ivoire","Cameroun","Gabon","Tchad","Bénin","Togo","Burkina Faso","Mali","Niger","Guinée","Canada","Belgique","Suisse","Luxembourg","Monaco","Chine","Allemagne","International"]


def norm(s):
    s = re.sub(r'\s*\(Secours\s+\d+\)\s*$', '', s, flags=re.I).casefold().replace('œ','oe')
    return re.sub(r'[^a-z0-9à-ÿ]+','',s)

def name(ext): return ext.split(',',1)[1].strip() if ',' in ext else 'Unknown'
def url_of(block): return next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith('#')), '')

def safe(item):
    p = urlparse(item['url']); host = (p.hostname or '').casefold()
    return p.scheme in ('http','https') and not p.username and not p.password and not any(x in host for x in BLOCKED)

def probe(item):
    if not safe(item): return False, 'blocked'
    try:
        req = Request(item['url'], headers={'User-Agent':'Mozilla/5.0','Accept':'application/vnd.apple.mpegurl,application/x-mpegURL,*/*'})
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            code = getattr(r,'status',200) or 200; data = r.read(131072).lower(); ctype=(r.headers.get('Content-Type') or '').casefold()
        ok = code in (200,206) and (b'#extm3u' in data or b'#ext-x-' in data or 'mpegurl' in ctype)
        return ok, f'HTTP {code}'
    except Exception as exc: return False, type(exc).__name__

def parse():
    lines=open(PATH,encoding='utf-8').read().replace('\r\n','\n').replace('\r','\n').split('\n')
    header=[]; groups=OrderedDict(); i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith('#EXTINF:'):
            block=[line]; i+=1
            while i<len(lines) and lines[i] and not lines[i].startswith('#EXTINF:') and not lines[i].startswith('# ====='):
                block.append(lines[i]); i+=1
            group=dict(ATTR_RE.findall(block[0])).get('group-title','International'); groups.setdefault(group,[]).append(block); continue
        if line.strip() and not line.startswith('# =====') and not line.startswith('# Recherche approfondie 2:'): header.append(line)
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
    with ThreadPoolExecutor(max_workers=16) as pool:
        futs={pool.submit(probe,x):x for x in candidates}
        for fut in as_completed(futs):
            x=futs[fut]; ok,why=fut.result(); results[x['url']]=ok; print(('PASS' if ok else 'FAIL'),why,x['group'],x['name'],x['url'])
    header,groups=parse(); active=added=new=backups=0; by_country={}
    for x in candidates:
        if not results.get(x['url']): continue
        active+=1; r=add(groups,x)
        if r in ('new','backup'):
            added+=1; new+=r=='new'; backups+=r=='backup'; by_country[x['group']]=by_country.get(x['group'],0)+1
    report=f'# Recherche approfondie 2: {len(candidates)} liens testés, {active} actifs, {added} ajoutés ({new} nouvelles chaînes, {backups} secours)'
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
