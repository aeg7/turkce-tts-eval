"""Alan bazli CFER. Kritik alanlari metinden otomatik cikarir,
hizalama ile duyulan bolgeyi bulur, alan bazinda hatali/dogru der."""
import re, json, argparse
from turkish_tts_eval import normalize, cer

ALAN_ESIK = 0.25      # alan CER esigi (gurultu tavani %12.5, hata tabani %37.5)
WHISPER_ESIK = 0.15   # kisaltma icin, mevcut kural

DESENLER = [
    ("para",     r"[\d.]*\d,\d{2}\s*TL"),
    ("tarih",    r"\d{2}\.\d{2}\.\d{4}"),
    ("saat",     r"\d{2}:\d{2}"),
    ("sayi",     r"\d{1,3}(?:\.\d{3})+"),
    ("kisaltma", r"\b[A-ZÇĞİÖŞÜ]{2,}\b"),
    ("sayi",     r"\b\d+\b"),
]

def alanlari_bul(metin):
    dolu = [False] * len(metin)
    bulunan = []
    for tip, desen in DESENLER:
        for m in re.finditer(desen, metin):
            b, s = m.start(), m.end()
            if any(dolu[b:s]):
                continue
            for i in range(b, s):
                dolu[i] = True
            bulunan.append((b, tip, m.group()))
    bulunan.sort()
    return [(t, d) for _, t, d in bulunan]

def hizala_harita(ref, hyp):
    n, m = len(ref), len(hyp)
    D = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): D[i][0] = i
    for j in range(m+1): D[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            c = 0 if ref[i-1] == hyp[j-1] else 1
            D[i][j] = min(D[i-1][j]+1, D[i][j-1]+1, D[i-1][j-1]+c)
    yol = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            c = 0 if ref[i-1] == hyp[j-1] else 1
            if D[i][j] == D[i-1][j-1] + c:
                yol.append(("esle", i-1, j-1)); i -= 1; j -= 1; continue
        if i > 0 and D[i][j] == D[i-1][j] + 1:
            yol.append(("sil", i-1, j)); i -= 1; continue
        yol.append(("ekle", i, j-1)); j -= 1
    yol.reverse()
    harita = {}
    for op, ri, hj in yol:
        if op in ("esle", "sil") and ri not in harita:
            harita[ri] = hj
    harita[n] = m
    return harita

def alan_degerlendir(kayit, alan_esik=ALAN_ESIK, whisper_esik=WHISPER_ESIK):
    ref   = kayit.get("ref") or ""
    ref_n = kayit.get("ref_n") or ""
    hyp_n = kayit.get("w2v2_n")
    w_cer = kayit.get("cer")
    sonuc = []
    ara_bas = 0
    harita = hizala_harita(ref_n, hyp_n) if hyp_n else None
    for tip, deger in alanlari_bul(ref):
        d = {"tip": tip, "deger": deger}
        if tip == "kisaltma" or not hyp_n:
            d["yontem"]   = "whisper_cer"
            d["beklenen"] = normalize(deger)
            d["duyulan"]  = None
            d["alan_cer"] = None
            d["hatali"]   = bool(w_cer is not None and w_cer > whisper_esik)
            sonuc.append(d); continue
        nrm = normalize(deger)
        bas = ref_n.find(nrm, ara_bas)
        if bas < 0:
            d["yontem"] = "ESLESMEDI"; d["beklenen"] = nrm
            d["duyulan"] = None; d["alan_cer"] = None; d["hatali"] = None
            sonuc.append(d); continue
        son = bas + len(nrm)
        ara_bas = son
        hb = harita.get(bas, 0)
        hs = harita.get(son, len(hyp_n))
        bolge = hyp_n[hb:hs]
        ac = cer(nrm, bolge)
        d.update(yontem="hizalama", beklenen=nrm, duyulan=bolge,
                 alan_cer=ac, hatali=bool(ac > alan_esik))
        sonuc.append(d)
    return sonuc

def cfer_hesapla(veri, alan_esik=ALAN_ESIK, whisper_esik=WHISPER_ESIK):
    toplam = hatali = belirsiz = 0
    kirilim = {}
    detay = {}
    for fname in sorted(veri):
        alanlar = alan_degerlendir(veri[fname], alan_esik, whisper_esik)
        if not alanlar:
            continue
        detay[fname] = alanlar
        for a in alanlar:
            k = kirilim.setdefault(a["tip"], [0, 0])
            if a["hatali"] is None:
                belirsiz += 1; continue
            toplam += 1; k[1] += 1
            if a["hatali"]:
                hatali += 1; k[0] += 1
    oran = (hatali / toplam) if toplam else 0.0
    return {"cfer": oran, "hatali": hatali, "toplam": toplam,
            "belirsiz": belirsiz, "kirilim": kirilim, "detay": detay}

def yazdir(ad, r, detay=False):
    print(f"\n{ad}  CFER %{r['cfer']*100:.1f}  ({r['hatali']}/{r['toplam']} alan)")
    if r["belirsiz"]:
        print(f"  UYARI: {r['belirsiz']} alan eslesmedi, sayima girmedi")
    for tip in sorted(r["kirilim"]):
        h, t = r["kirilim"][tip]
        print(f"    {tip:9} {h}/{t}  %{(h/t*100) if t else 0:.0f}")
    if not detay:
        return
    for fname in sorted(r["detay"]):
        print(f"  {fname}")
        for a in r["detay"][fname]:
            ac = f"%{a['alan_cer']*100:.1f}" if a["alan_cer"] is not None else "-"
            im = {True: "HATALI", False: "dogru", None: "?"}[a["hatali"]]
            print(f"    [{im:6}] {a['tip']:9} {a['deger']!r} -> {a['duyulan']!r} ({ac}, {a['yontem']})")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("json_a")
    p.add_argument("json_b", nargs="?")
    p.add_argument("--ad-a", default="A")
    p.add_argument("--ad-b", default="B")
    p.add_argument("--alan-esik", type=float, default=ALAN_ESIK)
    p.add_argument("--whisper-esik", type=float, default=WHISPER_ESIK)
    p.add_argument("--detay", action="store_true")
    args = p.parse_args()
    ra = cfer_hesapla(json.load(open(args.json_a)), args.alan_esik, args.whisper_esik)
    yazdir(args.ad_a, ra, args.detay)
    if args.json_b:
        rb = cfer_hesapla(json.load(open(args.json_b)), args.alan_esik, args.whisper_esik)
        yazdir(args.ad_b, rb, args.detay)


# --- rapor.py uyumluluk katmani -------------------------------------
# Eski cfer.py imzasi: (toplam, hatali, oran, {kat: [toplam, hatali]}, detay)
# Kirilim sirasi eskide [toplam, hatali], yenide [hatali, toplam]. Cevriliyor.

# Alan tipi -> kart kategorisi (kart kategorisi JSON'daki 'kategori' alani).
# 'saat' yeni bir alan tipi, kartlarda karsiligi 'tarih'.
FILTRE_ESLEME = {"saat": "tarih"}

def filtre_kategorisi(alan_tipi):
    return FILTRE_ESLEME.get(alan_tipi, alan_tipi)

def cfer_hesapla_uyumlu(veri, esik=None):
    """rapor.py icin eski imza. Gelen 'esik' ayrisma esigidir, alan
    esigi DEGILDIR, o yuzden yok sayilir. Alan esigi ALAN_ESIK."""
    r = cfer_hesapla(veri)
    kat = {k: [t, h] for k, (h, t) in r["kirilim"].items()}
    return r["toplam"], r["hatali"], r["cfer"], kat, r["detay"]


# --- URETIM ONCESI NORMALIZASYON ------------------------------------
# Ayni desenler, ters yon: olcmek yerine onlemek.
# TTS'e rakam gostermezsen rakami yanlis okuyamaz.

ON_NORM_TIPLERI = ("sayi", "tarih", "saat", "para")   # kisaltma disarida

def alanlari_bul_konumlu(metin):
    """alanlari_bul ile ayni mantik, konum da doner: (bas, son, tip, deger)."""
    dolu = [False] * len(metin)
    bulunan = []
    for tip, desen in DESENLER:
        for m in re.finditer(desen, metin):
            b, s = m.start(), m.end()
            if any(dolu[b:s]):
                continue
            for i in range(b, s):
                dolu[i] = True
            bulunan.append((b, s, tip, m.group()))
    bulunan.sort()
    return bulunan

def on_normalize(metin, tipler=ON_NORM_TIPLERI):
    """Kritik alanlari sozlu formuyla degistirir. Cumlenin geri kalanina,
    noktalamaya, buyuk harfe DOKUNMAZ (tonlama bozulmasin)."""
    parcalar = [(b, s, normalize(d))
                for b, s, t, d in alanlari_bul_konumlu(metin) if t in tipler]
    for b, s, yeni in reversed(parcalar):
        metin = metin[:b] + yeni + metin[s:]
    if parcalar:
        metin = kesme_duzelt(metin)
    return metin


# --- KESME EKI UYUMU ------------------------------------------------
# Alan sozlu forma cevrilince kesme eki ortada kalir ve unlu uyumu bozulur.
# Ornek: "TL'lik" -> "... kurus'lik"  (yanlis, "kurusluk" olmali)
# Ek yazili formun okunusuna gore secilmisti, sozlu form degisti.

_KALIN = "aıou"
_INCE  = "eiöü"
_SERT  = "fstkçşhp"   # sert unsuz -> d/t degisimi

def _son_unlu(kelime):
    for ch in reversed(kelime.lower()):
        if ch in _KALIN or ch in _INCE:
            return ch
    return None

def _ek_uyumla(govde, ek):
    """ek: kesme sonrasi ham ek (da, de, lik, lık, den, ...)."""
    u = _son_unlu(govde)
    if u is None:
        return ek
    kalin = u in _KALIN
    duz   = u in "aeıi"
    dort  = ("ı" if (kalin and duz) else "i" if duz else "u" if kalin else "ü")
    iki   = "a" if kalin else "e"
    son_h = govde and govde[-1].lower() in _SERT
    yeni = []
    for i, ch in enumerate(ek.lower()):
        if i == 0 and ch in "dt":
            yeni.append("t" if son_h else "d"); continue
        yeni.append(dort if ch in "ıiuü" else iki if ch in "ae" else ch)
    return "".join(yeni)

_KESME = re.compile(r"['’]([a-zçğıöşü]+)")

def kesme_duzelt(metin):
    def f(m):
        ek = m.group(1)
        govde = metin[:m.start()].rstrip()
        son_kelime = govde.split()[-1] if govde.split() else ""
        return _ek_uyumla(son_kelime, ek)
    return _KESME.sub(f, metin)
