#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
karsilastir.py — iki TTS'in skor JSON'larini yan yana basar.

Kullanim:
  python3 karsilastir.py piper.json voxcpm.json --ad-a Piper --ad-b VoxCPM

UYARI (kalibrasyon):
  UTMOSv2'nin olcum gurultusu ~0.2 puan (ayni dosya, iki kosu).
  MOS farki 0.3'un altindaysa ANLAMSIZ sayilir, tabloda "~" ile isaretlenir.
"""
import argparse
import json
import sys

GURULTU = 0.30  # MOS anlamlilik esigi (olculen ~0.2 gurultunun uzerinde)


def yukle(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"HATA: {yol} yok. Once score_wav.py --json ile uret.")


def kazanan_cer(a, b):
    fark = a - b
    if abs(fark) < 0.01:      # 1 puan CER farki
        return "="
    return "B" if fark > 0 else "A"


def kazanan_mos(a, b):
    if a is None or b is None:
        return "-"
    fark = b - a
    if abs(fark) < GURULTU:
        return "~"            # gurultu icinde, ayirt edilemez
    return "B" if fark > 0 else "A"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_a")
    ap.add_argument("json_b")
    ap.add_argument("--ad-a", default="A")
    ap.add_argument("--ad-b", default="B")
    args = ap.parse_args()

    A, B = yukle(args.json_a), yukle(args.json_b)
    ortak = sorted(set(A) & set(B))
    if not ortak:
        sys.exit("HATA: iki JSON'da ortak dosya yok.")

    a, b = args.ad_a, args.ad_b
    print()
    print(f"{'dosya':<14} {'kategori':<13} "
          f"{a+' CER':>10} {b+' CER':>10} {'CER kaz':>8}   "
          f"{a+' MOS':>10} {b+' MOS':>10} {'MOS kaz':>8}   bayrak")
    print("-" * 118)

    mos_a, mos_b = [], []
    cer_a, cer_b = [], []
    for f in ortak:
        ra, rb = A[f], B[f]
        kat = (ra.get("flags") or ["-"])
        # kategori refs.tsv'de yok, dosya sirasindan cikaramayiz -> flag'lerden ozet
        bayrak = ",".join(x for x in ra.get("flags", []) if x in ("kritik", "insan", "sadik_asr")) or "-"

        ca, cb = ra["cer"] * 100, rb["cer"] * 100
        ma, mb = ra.get("mos"), rb.get("mos")
        cer_a.append(ca); cer_b.append(cb)
        if ma is not None: mos_a.append(ma)
        if mb is not None: mos_b.append(mb)

        kor = ""
        if ra.get("ayrisma") is not None or rb.get("ayrisma") is not None:
            aa = (ra.get("ayrisma") or 0) * 100
            ab = (rb.get("ayrisma") or 0) * 100
            kor = f" KOR:{aa:+.0f}/{ab:+.0f}"

        print(f"{f:<14} {bayrak:<13} "
              f"{ca:>10.1f} {cb:>10.1f} {kazanan_cer(ca/100, cb/100):>8}   "
              f"{(f'{ma:.2f}' if ma else '-'):>10} {(f'{mb:.2f}' if mb else '-'):>10} "
              f"{kazanan_mos(ma, mb):>8}   {kor}")

    print("-" * 118)
    oa = sum(cer_a) / len(cer_a)
    ob = sum(cer_b) / len(cer_b)
    print(f"{'ORTALAMA CER':<28} {oa:>10.1f} {ob:>10.1f} {kazanan_cer(oa/100, ob/100):>8}")

    if mos_a and mos_b:
        pa = sum(mos_a) / len(mos_a)
        pb = sum(mos_b) / len(mos_b)
        fark = pb - pa
        karar = kazanan_mos(pa, pb)
        print(f"{'ORTALAMA MOS':<28} {'':>10} {'':>10} {'':>8}   "
              f"{pa:>10.2f} {pb:>10.2f} {karar:>8}")
        print()
        print(f"MOS farki: {fark:+.2f} puan")
        if karar == "~":
            print(f"-> Fark {GURULTU} esiginin ALTINDA. UTMOSv2 bu iki sistemi AYIRT EDEMIYOR.")
            print("   'X daha dogal' denemez. Karar insana kalir (bacak 3).")
        else:
            kazanan = a if karar == "A" else b
            print(f"-> Fark anlamli. UTMOSv2 {kazanan} lehine sinyal veriyor (goreli).")

    print()
    print("LEJANT:")
    print("  CER kaz / MOS kaz : A = " + a + " daha iyi, B = " + b + " daha iyi, = / ~ : ayirt edilemez")
    print(f"  ~  : MOS farki {GURULTU} puanin altinda (olcum gurultusu icinde)")
    print("  KOR: cift-ASR ayrisma puani (A/B). >10 ise gizli okuma hatasi var.")
    print("  NOT: KOR NOKTA satirlarinda CER=0 GUVENILMEZ. Whisper hatayi maskeliyor.")
    print()


if __name__ == "__main__":
    main()
