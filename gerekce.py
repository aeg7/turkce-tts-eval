#!/usr/bin/env python3
"""
gerekce.py — Skor JSON'undaki sayilara bakip NEDEN oyle ciktigini
kural bazli aciklar. Tahmin yok, LLM yok, deterministik if-else.

Kullanim:
    python3 gerekce.py piper.json
    python3 gerekce.py piper.json --sadece tarih
"""

import argparse
import json
import difflib

ESIK_AYRISMA = 0.10
CER_KIRMIZI  = 0.15
CER_SARI     = 0.05
NORM_ANLAMLI = 0.01

# VoxCPM normalize=True acikken Turkce rakami Ingilizce okuyor.
# Bu sozcukler Turkce transkriptte gorunuyorsa: normalizasyon Ingilizce'ye kaymis.
ING_SAYILAR = ("one", "two", "three", "four", "five", "six", "seven", "eight",
               "nine", "ten", "eleven", "twelve", "twenty", "thirty", "forty",
               "fifty", "hundred", "thousand", "june", "july", "of june", "th of",
               "ninety", "ninty", "fortu", "fifti")


def diff_isaretle(ref_n, hyp_n, limit=90):
    sm = difflib.SequenceMatcher(None, ref_n, hyp_n)
    parca = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            parca.append(ref_n[i1:i2])
        elif op == "delete":
            parca.append(f"[-{ref_n[i1:i2]}-]")
        elif op == "insert":
            parca.append(f"{{+{hyp_n[j1:j2]}+}}")
        elif op == "replace":
            parca.append(f"[-{ref_n[i1:i2]}-]{{+{hyp_n[j1:j2]}+}}")
    s = "".join(parca)
    return s if len(s) <= limit * 3 else s[: limit * 3] + " ..."


def gerekce_uret(v, esik=ESIK_AYRISMA):
    kodlar = []
    satirlar = []

    cer = v.get("cer") or 0.0
    cer_ham = v.get("cer_ham")
    ayr = v.get("ayrisma")
    w2c = v.get("w2v2_cer")
    flags = v.get("flags") or []
    kategori = v.get("kategori", "?")

    kor_nokta = ayr is not None and ayr > esik

    # --- 1. Maskeleme / cift tetik ---
    if kor_nokta and cer <= CER_SARI:
        kodlar.append("MASKELEME")
        satirlar.append(
            f"Whisper CER yüzde {cer*100:.1f} gösteriyor ama bu sahte. "
            f"Sadık ASR (wav2vec2) yüzde {w2c*100:.1f} hata görüyor, "
            f"ayrışma +{ayr*100:.0f} puan (eşik {esik*100:.0f}). "
            f"Whisper duyduğunu düzeltip yazıya döküyor, gerçek okuma hatasını gizliyor."
        )
    elif kor_nokta and cer > CER_SARI:
        kodlar.append("CIFT_TETIK")
        satirlar.append(
            f"İki mekanizma birden. Whisper zaten yüzde {cer*100:.1f} hata görüyor "
            f"(gerçek okuma hatası var), üstüne sadık ASR yüzde {w2c*100:.1f} ile "
            f"+{ayr*100:.0f} puan ayrışıyor (maskeleme de var). En kötü durum."
        )
    elif cer > CER_KIRMIZI:
        kodlar.append("GERCEK_HATA")
        satirlar.append(
            f"Whisper CER yüzde {cer*100:.1f}. Whisper düzeltici bir model, "
            f"buna rağmen hatayı örtemiyor. TTS metni gerçekten yanlış okumuş."
        )
    elif cer > CER_SARI:
        kodlar.append("SINIRDA")
        satirlar.append(
            f"Whisper CER yüzde {cer*100:.1f}. Kırmızı eşiğin (yüzde 15) altında "
            f"ama temiz de değil. Gözden geçir."
        )

    # --- 2. wav2vec2 kendi gurultusu ---
    if ayr is not None and 0 < ayr <= esik:
        kodlar.append("W2V2_GURULTU")
        satirlar.append(
            f"Sadık ASR +{ayr*100:.0f} puan ayrışıyor ama eşik {esik*100:.0f}. "
            f"Bu wav2vec2'nin kendi gürültüsü, gerçek hata değil. Alarm verilmedi."
        )

    # --- 3. Insan bayragi ---
    if "insan" in flags:
        kodlar.append("INSAN")
        if kategori == "homograf":
            satirlar.append(
                "Homograf cümlesi (kâr/kar, hâlâ/hala). Seste bilgi kaybı var, "
                "iki okunuşun fonemleri neredeyse aynı. Hiçbir ASR çözemez. "
                "CER'e bakılmaz, doğrudan insana gider."
            )
        else:
            satirlar.append(
                "İnsan bayrağı var. Otomatik metrik burada tek başına karar veremez, "
                "kulakla dinlenmeli."
            )

    # --- 3.5 Normalizasyon Ingilizce'ye mi kaydi ---
    metin_bak = ((v.get("whisper_n") or "") + " " + (v.get("w2v2_n") or "")).lower()
    if any(sz in metin_bak.split() or sz in metin_bak for sz in ING_SAYILAR):
        if cer > CER_SARI:
            kodlar.append("NORM_INGILIZCE")
            satirlar.append(
                "Model sayı/tarih/parayı İngilizce okumuş (ör. 'twenty nine', "
                "'the 29th of june', 'forty nine'). VoxCPM normalizasyonu Türkçe "
                "rakamı ana diline çeviriyor. Türkçe bir sistemde kabul edilemez."
            )

    # --- 4. Normalizasyon: kazanc mi, kanit silme mi ---
    if cer_ham is not None and (cer_ham - cer) > NORM_ANLAMLI \
            and "NORM_INGILIZCE" not in kodlar:
        kazanc = (cer_ham - cer) * 100
        if kategori == "homograf":
            kodlar.append("CER_ANLAMSIZ")
            satirlar.append(
                f"CER yüzde {cer*100:.1f} ama bu 'doğru okundu' demek değil, "
                f"'ölçemedim' demek. Normalizasyon şapkayı siliyor (kâr → kar), "
                f"Whisper zaten şapkasız yazıyor. İki okunuş da aynı metne düşüyor. "
                f"Bu satırda CER hiçbir şey söylemiyor, sinyal boş."
            )
        else:
            kodlar.append("NORM_KAZANC")
            satirlar.append(
                f"Normalizasyon öncesi CER yüzde {cer_ham*100:.1f}, sonrası yüzde {cer*100:.1f}. "
                f"Katman {kazanc:.1f} puan sahte hatayı temizledi."
            )

    # --- 5. Kritik bayrak ---
    if "kritik" in flags:
        kodlar.append("KRITIK")

    for ho in hata_ozeti(v):
        satirlar.append("OKUMA HATASI: " + ho)

    if not kodlar:
        kodlar.append("TEMIZ")
        satirlar.append("İki ASR de temiz, ayrışma yok. Okuma doğru.")

    return kodlar, satirlar



def hata_ozeti(v):
    """w2v2 transkriptinde bilinen okuma hatalarini yakalar, insan diliyle listeler.
    Sadece sadik_asr bayrakli (sayi/tarih/saat/para) cumlelerde anlamli."""
    w = (v.get("w2v2_n") or "").lower()
    notlar = []
    if not w:
        return notlar

    # Para/sayi hatalari
    if "virgül" in w or "virgul" in w:
        notlar.append("Virgül sesli okunuyor ('kırk dokuz virgül doksan'). "
                      "Ayraç olmalı, 'lira' diye okunmalı.")
    if "sıfır sıfır" in w or "sıfırsıfır" in w or "sifir sifir" in w:
        notlar.append("Kuruş sıfırken 'sıfır sıfır' okunuyor. Sonu ,00 ise kuruş "
                      "hiç okunmamalı.")
    for tl in ("tele", "tehle", "tele li", "teleli", "terali", "telel"):
        if tl in w:
            notlar.append("'TL' anlamsız sese çevriliyor ('tele/tehle'). "
                          "'lira' diye okunmalı.")
            break
    # Tarih/saat hatalari
    if "nokta" in w:
        notlar.append("Tarih ayracı 'nokta' diye okunuyor ('sıfır altı nokta'). "
                      "Ay adına çevrilmeli ('Haziran').")
    if "o clock" in w or "oklok" in w or "o klok" in w:
        notlar.append("Saat 'o clock' diye İngilizce okunuyor.")
    # Ingilizce kacis (norm deneyinden)
    for ing in ("june", "july", "twenty", "thirty", "forty", "fifty",
                "hundred", "thousand", "point", "ninety"):
        if ing in w.split() or (" " + ing + " ") in (" " + w + " "):
            notlar.append("Sayı/tarih İngilizce okunuyor ('" + ing + "'). "
                          "Türkçe bir sistemde kabul edilemez.")
            break
    return notlar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_dosya")
    ap.add_argument("--esik", type=float, default=ESIK_AYRISMA)
    ap.add_argument("--sadece", help="Sadece bu kategoriyi bas (or: tarih)")
    args = ap.parse_args()

    with open(args.json_dosya, encoding="utf-8") as f:
        d = json.load(f)

    sayac = {}
    for fname in sorted(d):
        v = d[fname]
        if args.sadece and v.get("kategori") != args.sadece:
            continue

        kodlar, satirlar = gerekce_uret(v, args.esik)
        for k in kodlar:
            sayac[k] = sayac.get(k, 0) + 1

        mos = v.get("mos")
        mos_s = f"{mos:.2f}" if mos is not None else "-"

        print("=" * 78)
        print(f"{fname}  [{v.get('kategori','?')}]  bayrak: {','.join(v.get('flags') or []) or '-'}")
        print(f"  KOD : {' + '.join(kodlar)}")
        print(f"  CER : {v['cer']*100:.1f}   MOS: {mos_s}")
        print(f"  REF : {v.get('ref_n','')[:100]}")
        print(f"  WHIS: {v.get('whisper_n','')[:100]}")
        if v.get("w2v2_n"):
            print(f"  W2V2: {v['w2v2_n'][:100]}")
        print(f"  DIFF: {diff_isaretle(v.get('ref_n',''), v.get('whisper_n',''))}")
        print("  NEDEN:")
        for s in satirlar:
            print(f"    - {s}")

    print("=" * 78)
    print("OZET (kod dagilimi):")
    for k, n in sorted(sayac.items(), key=lambda x: -x[1]):
        print(f"  {k:<14} {n}")


if __name__ == "__main__":
    main()
