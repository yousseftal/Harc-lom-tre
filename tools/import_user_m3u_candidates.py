#!/usr/bin/env python3
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.parse import urlparse

PATH = "france-maghreb.m3u"
TIMEOUT = 10
MAX_STREAMS_PER_CHANNEL = 4

# Direct HLS links extracted from the M3U file supplied by the user.
# Before this script was generated, entries that were not French/Arabic,
# obvious web pages, known rights-restricted CDN families, suspicious private
# IPTV endpoints, and duplicates were excluded.
CANDIDATES = [
  {
    "id": "AghapyTV.eg",
    "name": "Aghapy TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/Q2j4qYS.png",
    "url": "https://5b622f07944df.streamlock.net/aghapy.tv/aghapy.smil/playlist.m3u8"
  },
  {
    "id": "AlGhadPlus.eg",
    "name": "Al Ghad Plus",
    "group": "Égypte",
    "logo": "",
    "url": "https://playlist.fasttvcdn.com/pl/ykvm3f2fhokwxqsurp9xcg/alghad-plus/playlist.m3u8"
  },
  {
    "id": "AlGhadTV.eg",
    "name": "Al Ghad TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/8KxE2Rs.png",
    "url": "https://eazyvwqssi.erbvr.com/alghadtv/alghadtv.m3u8"
  },
  {
    "id": "AlQaheraNews.eg",
    "name": "Al Qahera News",
    "group": "Égypte",
    "logo": "https://i.imgur.com/GgZ4s9m.png",
    "url": "https://bcovlive-a.akamaihd.net/d30cbb3350af4cb7a6e05b9eb1bfd850/eu-west-1/6057955906001/playlist.m3u8"
  },
  {
    "id": "AlhayatTV.eg",
    "name": "Alhayat TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/BgCNHUw.png",
    "url": "https://cdn3.wowza.com/5/OE5HREpIcEkySlNT/alhayat-live/ngrp:livestream_all/playlist.m3u8"
  },
  {
    "id": "CopticTV.eg",
    "name": "Coptic TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/p45z4XK.png",
    "url": "https://ctv.icopts.app/CTV/index.fmp4.m3u8"
  },
  {
    "id": "HudaTV.eg",
    "name": "Huda TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/4kIG5aF.png",
    "url": "https://cdn.bestream.io:19360/elfaro1/elfaro1.m3u8"
  },
  {
    "id": "KoogiTV.eg",
    "name": "Koogi TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/5nmE9jk.png",
    "url": "https://5d658d7e9f562.streamlock.net/koogi.tv/koogi.smil/playlist.m3u8"
  },
  {
    "id": "RotanaCinema.eg",
    "name": "Rotana Cinema",
    "group": "Égypte",
    "logo": "https://i.imgur.com/SIGbV9C.png",
    "url": "https://rotana.hibridcdn.net/rotananet/cinemamasr_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "WatanTV.eg",
    "name": "Watan TV",
    "group": "Égypte",
    "logo": "https://i.imgur.com/fGKjY7j.png",
    "url": "https://rp.tactivemedia.com/watantv_source/live/playlist.m3u8"
  },
  {
    "id": "Arte.fr",
    "name": "Arte",
    "group": "France",
    "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Arte-Logo.svg/500px-Arte-Logo.svg.png",
    "url": "https://artesimulcast.akamaized.net/hls/live/2031003/artelive_fr/index.m3u8"
  },
  {
    "id": "CGTNFrench.cn",
    "name": "CGTN Français",
    "group": "France",
    "logo": "https://i.imgur.com/fMsJYzl.png",
    "url": "https://news.cgtn.com/resource/live/french/cgtn-f.m3u8"
  },
  {
    "id": "HandicapTV.fr",
    "name": "Handicap TV",
    "group": "France",
    "logo": "",
    "url": "https://srv.webtvmanager.fr:3697/stream/play.m3u8"
  },
  {
    "id": "TV5MondeInfo.fr",
    "name": "TV5 Monde Info",
    "group": "France",
    "logo": "https://i.imgur.com/uPmwTo9.png",
    "url": "https://ott.tv5monde.com/Content/HLS/Live/channel(info)/index.m3u8"
  },
  {
    "id": "TV5MondeFBS.fr",
    "name": "TV5 Monde FBS",
    "group": "France",
    "logo": "https://i.imgur.com/uPmwTo9.png",
    "url": "https://ott.tv5monde.com/Content/HLS/Live/channel(fbs)/index.m3u8"
  },
  {
    "id": "TV5MondeEurope.fr",
    "name": "TV5 Monde Europe",
    "group": "France",
    "logo": "https://i.imgur.com/uPmwTo9.png",
    "url": "https://ott.tv5monde.com/Content/HLS/Live/channel(europe)/index.m3u8"
  },
  {
    "id": "BFMTV.fr",
    "name": "BFM TV",
    "group": "France",
    "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Logo_BFM_TV_%282019%29.png/60px-Logo_BFM_TV_%282019%29.png",
    "url": "https://ncdn-live-bfm.pfd.sfr.net/shls/LIVE$BFM_TV/index.m3u8?end=END&start=LIVE"
  },
  {
    "id": "AlHurraIraq.us",
    "name": "Al-Hurra Iraq",
    "group": "Irak",
    "logo": "https://i.imgur.com/8F3eY8j.png",
    "url": "https://mbnvvideoingest-i.akamaihd.net/hls/live/1004674/MBNV_ALHURRA_IRAQ/playlist.m3u8"
  },
  {
    "id": "AlHurra.us",
    "name": "Al-Hurra",
    "group": "Irak",
    "logo": "https://i.imgur.com/8F3eY8j.png",
    "url": "https://mbnvvideoingest-i.akamaihd.net/hls/live/1004673/MBNV_ALHURRA_MAIN/playlist.m3u8"
  },
  {
    "id": "AlIraqiya.iq",
    "name": "Al-Iraqiya",
    "group": "Irak",
    "logo": "https://i.imgur.com/py7zRxt.png",
    "url": "https://cdn.catiacast.video/abr/8d2ffb0aba244e8d9101a9488a7daa05/playlist.m3u8"
  },
  {
    "id": "AlRafidain.iq",
    "name": "Al-Rafidain",
    "group": "Irak",
    "logo": "https://i.imgur.com/1y7Rw6u.png",
    "url": "https://cdg8.edge.technocdn.com/arrafidaintv/abr_live/playlist.m3u8"
  },
  {
    "id": "AlRasheed.iq",
    "name": "Al-Rasheed",
    "group": "Irak",
    "logo": "https://i.imgur.com/KjFmIKp.png",
    "url": "https://media1.livaat.com/AL-RASHEED-HD/tracks-v1a1/playlist.m3u8"
  },
  {
    "id": "AlSharqiyaNews.iq",
    "name": "Al-Sharqiya News",
    "group": "Irak",
    "logo": "https://i.imgur.com/9qI4scW.png",
    "url": "https://5d94523502c2d.streamlock.net/alsharqiyalive/mystream/playlist.m3u8"
  },
  {
    "id": "AlSharqiya.iq",
    "name": "Al-Sharqiya",
    "group": "Irak",
    "logo": "https://i.imgur.com/o56jVm8.png",
    "url": "https://5d94523502c2d.streamlock.net/home/mystream/playlist.m3u8"
  },
  {
    "id": "DijlahTarab.iq",
    "name": "Dijlah Tarab",
    "group": "Irak",
    "logo": "https://i.imgur.com/lchqCV4.png",
    "url": "https://ghaasiflu.online/tarab/tracks-v1a1/playlist.m3u8"
  },
  {
    "id": "DijlahTV.iq",
    "name": "Dijlah TV",
    "group": "Irak",
    "logo": "https://i.imgur.com/lchqCV4.png",
    "url": "https://ghaasiflu.online/Dijlah/index.m3u8"
  },
  {
    "id": "iNEWS.iq",
    "name": "iNEWS",
    "group": "Irak",
    "logo": "https://i.imgur.com/mrQ1tOI.png",
    "url": "https://live.i-news.tv/hls/stream.m3u8"
  },
  {
    "id": "AlabbassiaTV.iq",
    "name": "Alabbassia TV",
    "group": "Irak",
    "logo": "",
    "url": "https://stream.alabbassia.com/live/alabbassia/index.m3u8"
  },
  {
    "id": "TeleLiban.lb",
    "name": "Tele Liban",
    "group": "Liban",
    "logo": "",
    "url": "https://cdn.catiacast.video/abr/ed8f807e2548db4507d2a6f4ba0c4a06/playlist.m3u8"
  },
  {
    "id": "AlMayadeenTV.lb",
    "name": "Al Mayadeen",
    "group": "Liban",
    "logo": "",
    "url": "https://mdnlv.cdn.octivid.com/almdn/smil:mpegts.stream.smil/playlist.m3u8"
  },
  {
    "id": "VoiceofLebanon.lb",
    "name": "Voice of Lebanon",
    "group": "Liban",
    "logo": "",
    "url": "https://svs.itworkscdn.net/vdltvlive/vdltv.smil/playlist.m3u8"
  },
  {
    "id": "NourSAT.lb",
    "name": "NourSAT",
    "group": "Liban",
    "logo": "",
    "url": "https://svs.itworkscdn.net/nour4satlive/livestream/playlist.m3u8"
  },
  {
    "id": "NourAlKoddas.lb",
    "name": "Nour Al Koddas",
    "group": "Liban",
    "logo": "",
    "url": "https://svs.itworkscdn.net/nour1satlive/livestream/playlist.m3u8"
  },
  {
    "id": "NourAlSharq.lb",
    "name": "Nour Al Sharq",
    "group": "Liban",
    "logo": "",
    "url": "https://svs.itworkscdn.net/nour8satlive/livestream/playlist.m3u8"
  },
  {
    "id": "AlimanTV.lb",
    "name": "Aliman TV",
    "group": "Liban",
    "logo": "",
    "url": "https://svs.itworkscdn.net/alimanlive/imantv.smil/playlist.m3u8"
  },
  {
    "id": "FalestinonaChannel.lb",
    "name": "Falestinona Channel",
    "group": "Liban",
    "logo": "",
    "url": "https://ffs3.gulfsat.com/Falestinona-TV/index.fmp4.m3u8"
  },
  {
    "id": "QatarTelevision.qa",
    "name": "Qatar Television",
    "group": "Qatar",
    "logo": "https://i.imgur.com/N5RB4sp.png",
    "url": "https://qatartv.akamaized.net/hls/live/20000609/qtv1/master.m3u8"
  },
  {
    "id": "QatarTelevision2.qa",
    "name": "Qatar Television 2",
    "group": "Qatar",
    "logo": "https://i.imgur.com/iWJxDUm.png",
    "url": "https://qatartv.akamaized.net/hls/live/20000611/qtv2/master.m3u8"
  },
  {
    "id": "QatarTelevisionTheHolyQuran.qa",
    "name": "Qatar Television The Holy Quran",
    "group": "Qatar",
    "logo": "https://i.imgur.com/N5RB4sp.png",
    "url": "https://qatartv.akamaized.net/hls/live/20000612/qtvquran/master1080p.m3u8"
  },
  {
    "id": "AlRayyanTV.qa",
    "name": "Al Rayyan",
    "group": "Qatar",
    "logo": "https://i.imgur.com/Ts3RjTV.png",
    "url": "https://alrayyancdn.vidgyor.com/pub-noalrayy3pwz0l/liveabr/playlist_dvr.m3u8"
  },
  {
    "id": "AlRayyanOldTV.qa",
    "name": "Al Rayyan Old TV",
    "group": "Qatar",
    "logo": "https://i.imgur.com/4qB5iN0.png",
    "url": "https://alrayyancdn.vidgyor.com/pub-nooldraybinbdh/liveabr/playlist_dvr.m3u8"
  },
  {
    "id": "AlJazeeraMubasher.qa",
    "name": "Al Jazeera Mubasher",
    "group": "Qatar",
    "logo": "https://upload.wikimedia.org/wikipedia/en/9/90/Al_Jazeera_Mubasher_logo.png",
    "url": "https://live-hls-web-ajm.getaj.net/AJM/index.m3u8"
  },
  {
    "id": "AlJazeeraChannel2.qa",
    "name": "Al Jazeera 2",
    "group": "Qatar",
    "logo": "https://i.imgur.com/BB93NQP.png",
    "url": "https://live-hls-web-aja2-gcp.thehlive.com/AJA2/index.m3u8"
  },
  {
    "id": "AlkassOne.qa",
    "name": "Alkass One",
    "group": "Qatar",
    "logo": "https://i.imgur.com/10mmlha.png",
    "url": "https://liveeu-gcp.alkassdigital.net/alkass1-p/main.m3u8"
  },
  {
    "id": "AlkassTwo.qa",
    "name": "Alkass Two",
    "group": "Qatar",
    "logo": "https://i.imgur.com/8w61kFX.png",
    "url": "https://liveeu-gcp.alkassdigital.net/alkass2-p/main.m3u8"
  },
  {
    "id": "AlkassThree.qa",
    "name": "Alkass Three",
    "group": "Qatar",
    "logo": "https://i.imgur.com/d57BdFh.png",
    "url": "https://liveeu-gcp.alkassdigital.net/alkass3-p/main.m3u8"
  },
  {
    "id": "AlkassFour.qa",
    "name": "Alkass Four",
    "group": "Qatar",
    "logo": "https://i.imgur.com/iDL65Wu.png",
    "url": "https://liveeu-gcp.alkassdigital.net/alkass4-p/main.m3u8"
  },
  {
    "id": "AlArabyTV.qa",
    "name": "Al Araby TV",
    "group": "Qatar",
    "logo": "https://i.imgur.com/YMqWEe4.png",
    "url": "https://live.kwikmotion.com/alaraby1live/alaraby_abr/playlist.m3u8"
  },
  {
    "id": "AlQuranAlKareemTV.sa",
    "name": "Al Quran Al Kareem TV",
    "group": "Arabie saoudite",
    "logo": "https://i.imgur.com/bF1fF7D.png",
    "url": "https://al-ekhbaria-prod-dub.shahid.net/out/v1/9885cab0a3ec4008b53bae57a27ca76b/index.m3u8"
  },
  {
    "id": "AlSunnahAlNabawiyahTV.sa",
    "name": "Al Sunnah Al Nabawiyah TV",
    "group": "Arabie saoudite",
    "logo": "https://i.imgur.com/1B2sN1Y.png",
    "url": "http://m.live.net.sa:1935/live/sunnah/gmswf.m3u8"
  },
  {
    "id": "RotanaCinemaKSA.sa",
    "name": "Rotana Cinema KSA",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/cinema_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "RotanaComedy.sa",
    "name": "Rotana Comedy",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/comedy_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "RotanaKhalijia.sa",
    "name": "Rotana Khalijia",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/khaleejiya_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "RotanaDrama.sa",
    "name": "Rotana Drama",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/drama_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "RotanaClassic.sa",
    "name": "Rotana Classic",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://bcovlive-a.akamaihd.net/0debf5648e584e5fb795c3611c5c0252/eu-central-1/6057955906001/playlist.m3u8"
  },
  {
    "id": "RotanaClip.sa",
    "name": "Rotana Ciip",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/clip_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "RotanaMusic.sa",
    "name": "Rotana Music",
    "group": "Arabie saoudite",
    "logo": "",
    "url": "https://rotana.hibridcdn.net/rotananet/music_net-7Y83PP5adWixDF93/playlist.m3u8"
  },
  {
    "id": "AlArabiyaBusiness.ae",
    "name": "Al Arabiya Business",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://live.alarabiya.net/alarabiapublish/aswaaq.smil/playlist.m3u8"
  },
  {
    "id": "SkyNewsArabia.ae",
    "name": "Sky News Arabia",
    "group": "Émirats arabes unis",
    "logo": "https://upload.wikimedia.org/wikipedia/en/thumb/5/57/Sky_News_logo.svg/500px-Sky_News_logo.svg.png",
    "url": "https://stream.skynewsarabia.com/hls/sna.m3u8"
  },
  {
    "id": "BaynounahTV.ae",
    "name": "Baynounah TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://vo-live.cdb.cdn.orange.com/Content/Channel/Baynounah/HLS/index.m3u8"
  },
  {
    "id": "AjmanTV.ae",
    "name": "Ajman TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://cdn1.logichost.in/ajmantv/live/playlist.m3u8"
  },
  {
    "id": "AlAanTV.ae",
    "name": "Al Aan TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://shls-live-ak.akamaized.net/out/v1/dfbdea4c1bf149629764e58c6ff314c8/index.m3u8"
  },
  {
    "id": "AbuDhabiTV.ae",
    "name": "Abu Dhabi TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "http://admdn2.cdn.mangomolo.com/adtv/smil:adtv.stream.smil/chunklist.m3u8"
  },
  {
    "id": "AbuDhabiSports1.ae",
    "name": "Abu Dhabi Sports 1",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://vo-live.cdb.cdn.orange.com/Content/Channel/AbuDhabiSportsChannel1/HLS/index.m3u8"
  },
  {
    "id": "AbuDhabiSports2.ae",
    "name": "Abu Dhabi Sports 2",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://vo-live.cdb.cdn.orange.com/Content/Channel/AbuDhabiSportsChannel2/HLS/index.m3u8"
  },
  {
    "id": "NationalGeographicAbuDhabi.ae",
    "name": "National Geographic Abu Dhabi",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://admdn2.cdn.mangomolo.com/nagtv/smil:nagtv.stream.smil/playlist.m3u8"
  },
  {
    "id": "DubaiTV.ae",
    "name": "Dubai TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmisxthvll.cdn.mgmlcdn.com/dubaitvht/smil:dubaitv.stream.smil/playlist.m3u8"
  },
  {
    "id": "DubaiOne.ae",
    "name": "Dubai One",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dminnvll.cdn.mangomolo.com/dubaione/smil:dubaione.stream.smil/playlist.m3u8"
  },
  {
    "id": "DubaiSports1.ae",
    "name": "Dubai Sports 1",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmitnthfr.cdn.mgmlcdn.com/dubaisports/smil:dubaisports.stream.smil/chunklist.m3u8"
  },
  {
    "id": "DubaiSports2.ae",
    "name": "Dubai Sports 2",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmitwlvvll.cdn.mangomolo.com/dubaisportshd/smil:dubaisportshd.smil/index.m3u8"
  },
  {
    "id": "DubaiSports3.ae",
    "name": "Dubai Sports 3",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmitwlvvll.cdn.mangomolo.com/dubaisportshd5/smil:dubaisportshd5.smil/index.m3u8"
  },
  {
    "id": "DubaiRacing1.ae",
    "name": "Dubai Racing 1",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmisvthvll.cdn.mgmlcdn.com/events/smil:events.stream.smil/playlist.m3u8"
  },
  {
    "id": "DubaiRacing2.ae",
    "name": "Dubai Racing 2",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmithrvll.cdn.mangomolo.com/dubairacing/smil:dubairacing.smil/playlist.m3u8"
  },
  {
    "id": "DubaiRacing3.ae",
    "name": "Dubai Racing 3",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmithrvll.cdn.mangomolo.com/dubaimubasher/smil:dubaimubasher.smil/playlist.m3u8"
  },
  {
    "id": "DubaiZaman.ae",
    "name": "Dubai Zaman",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmiffthvll.cdn.mangomolo.com/dubaizaman/smil:dubaizaman.stream.smil/playlist.m3u8"
  },
  {
    "id": "SamaDubai.ae",
    "name": "Sama Dubai",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmieigthvll.cdn.mgmlcdn.com/samadubaiht/smil:samadubai.stream.smil/playlist.m3u8"
  },
  {
    "id": "NoorDubai.ae",
    "name": "Noor Dubai",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://dmiffthvll.cdn.mangomolo.com/noordubaitv/smil:noordubaitv.smil/playlist.m3u8"
  },
  {
    "id": "SharjahTV.ae",
    "name": "Sharjah TV",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://live.kwikmotion.com/smc1live/smc1tv.smil/playlist.m3u8"
  },
  {
    "id": "SharjahSports.ae",
    "name": "Sharjah Sports",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://svs.itworkscdn.net/smc4sportslive/smc4.smil/playlist.m3u8"
  },
  {
    "id": "AlWousta.ae",
    "name": "Al Wousta",
    "group": "Émirats arabes unis",
    "logo": "",
    "url": "https://svs.itworkscdn.net/alwoustalive/alwoustatv.smil/playlist.m3u8"
  },
  {
    "id": "AlJazeeraDocumentary.qa",
    "name": "Al Jazeera Documentary",
    "group": "International arabe",
    "logo": "",
    "url": "https://live-hls-web-ajd.getaj.net/AJD/index.m3u8"
  },
  {
    "id": "AlJazeeraChannel.qa",
    "name": "Al Jazeera العربية",
    "group": "International arabe",
    "logo": "https://i.imgur.com/BB93NQP.png",
    "url": "https://live-hls-web-aja.getaj.net/AJA/index.m3u8"
  },
  {
    "id": "AlArabiya.ae",
    "name": "Al Arabiya العربية",
    "group": "International arabe",
    "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Al-Arabiya_new_logo.svg/500px-Al-Arabiya_new_logo.svg.png",
    "url": "https://live.alarabiya.net/alarabiapublish/alarabiya.smil/playlist.m3u8"
  },
  {
    "id": "AlHadath.sa",
    "name": "Al Hadath العربية",
    "group": "International arabe",
    "logo": "https://upload.wikimedia.org/wikipedia/commons/a/ae/Al_Hadath_TV_logo_2023.svg",
    "url": "https://live.alarabiya.net/alarabiapublish/alhadath.smil/alarabiapublish/alhadath_1080p/chunks.m3u8"
  },
  {
    "id": "DWArabic.de",
    "name": "DW العربية",
    "group": "International arabe",
    "logo": "https://i.imgur.com/A1xzjOI.png",
    "url": "https://dwamdstream103.akamaized.net/hls/live/2015526/dwstream103/index.m3u8"
  },
  {
    "id": "CGTNArabic.cn",
    "name": "CGTN العربية",
    "group": "International arabe",
    "logo": "https://i.imgur.com/fMsJYzl.png",
    "url": "https://arabic-livews.cgtn.com/hls/LSveq57bErWLinBnxosqjisZ220802LSTefTAS9zc9mpU08y3np9TH220802cd/playlist.m3u8"
  },
  {
    "id": "SkyNewsArabia.ae",
    "name": "Sky News العربية",
    "group": "International arabe",
    "logo": "https://upload.wikimedia.org/wikipedia/en/thumb/5/57/Sky_News_logo.svg/500px-Sky_News_logo.svg.png",
    "url": "https://stream.skynewsarabia.com/hls/sna.m3u8"
  },
  {
    "id": "RTArabic.ru",
    "name": "RT العربية",
    "group": "International arabe",
    "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Russia-today-logo.svg/500px-Russia-today-logo.svg.png",
    "url": "https://rt-arb.rttv.com/dvr/rtarab/playlist.m3u8"
  }
]

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
QUALITY_RE = re.compile(r'\s*\((?:\d{3,4}p|\d{3,4}i|SD|HD|FHD|UHD|4K)\)\s*', re.I)
BACKUP_RE = re.compile(r'\s*\(Secours\s+\d+\)\s*$', re.I)
MARKS_RE = re.compile(r'[ⓈⓎⒼⒹ]')

BLOCKED_HOST_BITS = (
    "edgenextcdn.net",
    "m-iptv.net",
    "sigma-iptv.net",
    "vip-max.com",
    "janjua.pw",
    "freechannelsonly.xyz",
)

def base_id(value):
    value = (value or "").strip()
    return value.split("@", 1)[0].casefold()

def norm_name(value):
    value = MARKS_RE.sub("", value or "")
    value = BACKUP_RE.sub("", value)
    value = QUALITY_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value

def key_for(tvg_id, name):
    bid = base_id(tvg_id)
    return ("id", bid) if bid else ("name", norm_name(name))

def test_hls(item):
    url = item["url"]
    try:
        host = (urlparse(url).hostname or "").casefold()
        if any(x in host for x in BLOCKED_HOST_BITS):
            return item, False, "blocked-host"
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; FranceMaghrebPlaylist/1.0)",
            "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,application/mpegurl,*/*",
        })
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            status = getattr(r, "status", 200) or 200
            final_url = r.geturl()
            final_host = (urlparse(final_url).hostname or "").casefold()
            if any(x in final_host for x in BLOCKED_HOST_BITS):
                return item, False, "redirect-blocked-host"
            data = r.read(65536)
            text = data.decode("utf-8", "ignore")
            ctype = (r.headers.get("Content-Type") or "").casefold()
            valid = (
                200 <= status < 300
                and (
                    "#EXTM3U" in text
                    or "#EXT-X-" in text
                    or "mpegurl" in ctype
                )
            )
            return item, valid, f"HTTP {status}"
    except Exception as exc:
        return item, False, type(exc).__name__

with open(PATH, encoding="utf-8") as f:
    lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

# Parse current channels and URLs.
entries = []
url_set = set()
counts = {}
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
        name = block[0].split(",", 1)[1].strip() if "," in block[0] else ""
        url = next((x.strip() for x in reversed(block[1:]) if x.strip() and not x.startswith("#")), "")
        if url:
            url_set.add(url)
        key = key_for(attrs.get("tvg-id", ""), name)
        counts[key] = counts.get(key, 0) + 1
        entries.append((block, key))
        continue
    i += 1

# Network verification in parallel.
results = []
with ThreadPoolExecutor(max_workers=16) as pool:
    futures = [pool.submit(test_hls, c) for c in CANDIDATES if c["url"] not in url_set]
    for fut in as_completed(futures):
        results.append(fut.result())

live = [item for item, ok, why in results if ok]
for item, ok, why in sorted(results, key=lambda x: x[0]["name"].casefold()):
    print(("PASS" if ok else "FAIL"), why, item["name"], item["url"])

added_blocks = []
added = 0
new_channels = 0
backups = 0

# Deterministic order by group then name.
for item in sorted(live, key=lambda x: (x["group"].casefold(), x["name"].casefold(), x["url"])):
    if item["url"] in url_set:
        continue
    key = key_for(item.get("id", ""), item["name"])
    existing = counts.get(key, 0)
    if existing >= MAX_STREAMS_PER_CHANNEL:
        continue

    display_name = item["name"]
    if existing:
        display_name = f"{display_name} (Secours {existing + 1})"
        backups += 1
    else:
        new_channels += 1

    attrs = []
    if item.get("id"):
        attrs.append(f'tvg-id="{item["id"]}"')
    if item.get("logo"):
        attrs.append(f'tvg-logo="{item["logo"]}"')
    attrs.append(f'group-title="{item["group"]}"')
    extinf = "#EXTINF:-1 " + " ".join(attrs) + "," + display_name
    added_blocks.extend([extinf, item["url"]])
    url_set.add(item["url"])
    counts[key] = existing + 1
    added += 1

# Remove previous report line, then add the current report line near the top.
report_prefix = "# Import fichier utilisateur:"
clean = [x for x in lines if not x.startswith(report_prefix)]
report = (
    f"{report_prefix} {len(results)} nouveaux liens testés, "
    f"{len(live)} actifs, {added} ajoutés "
    f"({new_channels} nouvelles chaînes, {backups} secours)"
)
insert_at = 1 if clean and clean[0].startswith("#EXTM3U") else 0
clean.insert(insert_at, report)

if added_blocks:
    while clean and not clean[-1].strip():
        clean.pop()
    clean.extend(["", "# ===== IMPORT UTILISATEUR VÉRIFIÉ ====="])
    clean.extend(added_blocks)
    clean.append("")

with open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(clean).rstrip() + "\n")

print(report)
