#!/usr/bin/env python3
"""
cfer.py — Critical Field Error Rate (Kritik Alan Hata Orani)

CFER = hatali kritik alan / toplam kritik alan

Bankacilik-kritik alanlar: sayi, tarih, saat, para, kisaltma.
CER "sesin yuzde kaci bozuk" der; CFER "kritik degerlerden kaci yanlis okundu" der.
Karar verici icin CER degil CFER anlamli.

"Hatali" tanimi kategoriye gore:
  - sayi/tarih/saat/para : KOR NOKTA (w2v2 ayrisma > esik) VEYA yuksek Whisper CER
    (Whisper kritik alandaki hatayi maskeliyor, CER'e guvenilmez, sadik ASR gerekir)
  - kisaltma             : yuksek Whisper CER
    (kisaltmada sadik_asr yok, w2v2 sahte alarm uretir; Whisper CER'ine bakilir)

Kullanim:
    python3 cfer.py piper.json
    python3 cfer.py piper.json voxcpm.json --ad-a Piper --ad-b VoxCPM
"""

import argparse
import json

ESIK_AYRISMA = 0.10
CER_HATA = 0.15   # kisaltmada bu ustu = hatali kritik alan

# Kritik alan kategorileri ve her cumlede kac kritik alan var
# (Yol B: cumle icindeki kritik deger sayisi)
KRITIK_KATEGORILER = {"sayi", "tarih", "saat", "para", "kisaltma"}

# Her cumlede kac kritik alan var (elle, test setine gore).
# tarih/para gibi cift degerli cumleler 2 sayilir.
ALAN_SAYISI = {
    "cikti_06.wav": 2,   # sayi: iki "2"
    "cikti_07.wav": 1,   # sayi: 1.245
    "cikti_08.wav": 2,   # tarih: iki tarih
    "cikti_09.wav": 2,   # saat: 09:00 ve 17:00
    "cikti_10.wav": 2,   # para: 32.500,00 ve 1.750,50
    "cikti_11.wav": 1,   # para: 49,90
    "cikti_12.wav": 2,   # kisaltma: TTS, WER
    "cikti_13.wav": 1,   # kisaltma: KVKK
}


def alan_sayisi(fname, kategori):
    if fname in ALAN_SAYISI:
        return ALAN_SAYISI[fname]
    return 1 if kategori in KRITIK_KATEGORILER else 0


def hatali_mi(v, esik=ESIK_AYRISMA):
    """Bu kritik cumle hatali okundu mu? Kategoriye gore sinyal."""
    kategori = v.get("kategori", "?")
    cer = v.get("cer") or 0.0
    ayr = v.get("ayrisma")

    if kategori in {"sayi", "tarih", "saat", "para"}:
        # Kor nokta VEYA gercek yuksek CER
        if ayr is not None and ayr > esik:
            return True, "kor nokta (maskeleme)"
        if cer > CER_HATA:
            return True, "yuksek Whisper CER"
        return False, ""
    elif kategori == "kisaltma":
        # sadik_asr yok, Whisper CER'ine bak
        if cer > CER_HATA:
            return True, "yuksek Whisper CER"
        return False, ""
    return False, ""


def cfer_hesapla(d, esik=ESIK_AYRISMA):
    """Doner: (toplam_alan, hatali_alan, cfer, kategori_kirilim, satirlar)"""
    toplam = 0
    hatali = 0
    kat_kirilim = {}   # kategori -> [toplam, hatali]
    satirlar = []

    for f in sorted(d):
        v = d[f]
        kategori = v.get("kategori", "?")
        n_alan = alan_sayisi(f, kategori)
        if n_alan == 0:
            continue

        hata, sebep = hatali_mi(v, esik)
        n_hatali = n_alan if hata else 0

        toplam += n_alan
        hatali += n_hatali

        kk = kat_kirilim.setdefault(kategori, [0, 0])
        kk[0] += n_alan
        kk[1] += n_hatali

        satirlar.append({
            "dosya": f, "kategori": kategori, "alan": n_alan,
            "hatali": hata, "sebep": sebep,
            "cer": v.get("cer"), "ayrisma": v.get("ayrisma"),
        })

    cfer = hatali / toplam if toplam else 0.0
    return toplam, hatali, cfer, kat_kirilim, satirlar


def yazdir(ad, d, esik):
    toplam, hatali, cfer, kat, satirlar = cfer_hesapla(d, esik)
    print("=" * 70)
    print(f"{ad}")
    print("=" * 70)
    print(f"{'dosya':<15} {'kategori':<10} {'alan':>4} {'durum':<8} {'sebep'}")
    print("-" * 70)
    for s in satirlar:
        durum = "HATALI" if s["hatali"] else "ok"
        print(f"{s['dosya']:<15} {s['kategori']:<10} {s['alan']:>4} "
              f"{durum:<8} {s['sebep']}")
    print("-" * 70)
    print("Kategori kirilim:")
    for k, (t, h) in sorted(kat.items()):
        oran = h / t * 100 if t else 0
        print(f"  {k:<10} {h}/{t} hatali  ({oran:.0f}%)")
    print("-" * 70)
    print(f"CFER = {hatali}/{toplam} = %{cfer*100:.1f}  "
          f"(kritik alanlarin yuzde {cfer*100:.1f}'i yanlis okundu)")
    print()
    return cfer, toplam, hatali


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_a")
    ap.add_argument("json_b", nargs="?")
    ap.add_argument("--ad-a", default="A")
    ap.add_argument("--ad-b", default="B")
    ap.add_argument("--esik", type=float, default=ESIK_AYRISMA)
    args = ap.parse_args()

    da = json.load(open(args.json_a, encoding="utf-8"))
    ca, ta, ha = yazdir(args.ad_a, da, args.esik)

    if args.json_b:
        db = json.load(open(args.json_b, encoding="utf-8"))
        cb, tb, hb = yazdir(args.ad_b, db, args.esik)
        print("=" * 70)
        print("KARSILASTIRMA")
        print("=" * 70)
        print(f"  {args.ad_a:<20} CFER %{ca*100:.1f}  ({ha}/{ta})")
        print(f"  {args.ad_b:<20} CFER %{cb*100:.1f}  ({hb}/{tb})")
        if cb < ca:
            print(f"  -> {args.ad_b} kritik alanlarda daha iyi")
        elif ca < cb:
            print(f"  -> {args.ad_a} kritik alanlarda daha iyi")
        else:
            print(f"  -> esit")


if __name__ == "__main__":
    main()
