#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Türkçe TTS Değerlendirme Harness'i (deneme sürümü)
--------------------------------------------------
Üç bacaklı yapı:
  1) Anlaşılabilirlik : normalizasyon katmanı -> CER/WER  (bu dosyada tam çalışır)
  2) Doğallık         : UTMOSv2 (göreli MOS)              (gerçek .wav ister -> demo'da mock)
  3) İnsan spot-check : [insan] bayraklı cümleler          (otomatik metriğin kör olduğu yer)

Kullanım:
  python turkish_tts_eval.py --demo      # ses olmadan simüle ASR ile tam pipeline
  (gerçek koşu için: faster-whisper çıktısını asr_hypothesis alanına ver)

Bağımlılık: yok (saf Python). Gerçek ASR için opsiyonel: faster-whisper.
"""

import argparse
import re
import unicodedata

# =============================================================================
# BÖLÜM 1 — TÜRKÇE NORMALİZASYON KATMANI (yıldız bileşen)
# Referans metni VE ASR çıktısını aynı "sözlü forma" indirir.
# "1.500,50 TL" -> "bin beş yüz lira elli kuruş"
# =============================================================================

ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
SCALES = ["", "bin", "milyon", "milyar", "trilyon"]
MONTHS = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
          "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# Kısaltma okunuş sözlüğü — KARAR NOKTASI: ürün ekibiyle mutabakat gerekir.
# (Burada projedeki varsayılan tercih uygulanmıştır.)
ABBREV = {
    "KVKK": "ka ve ka ka",
    "IBAN": "iban",
    "TTS":  "te te se",
    "WER":  "ve e er",
    "CER":  "ce e er",
    "API":  "ey pi ay",
    "CPU":  "si pi yu",
    "POS":  "pos",
    "IVR":  "ay vi ar",
}


def _uc_uc_basamak(n):
    """0-999 arası -> Türkçe kelime."""
    p = []
    y, kalan = n // 100, n % 100
    o, b = kalan // 10, kalan % 10
    if y:
        p.append("yüz" if y == 1 else ONES[y] + " yüz")
    if o:
        p.append(TENS[o])
    if b:
        p.append(ONES[b])
    return " ".join(p)


def sayi_to_turkce(n):
    """Tam sayı -> Türkçe kelime (bin/milyon dahil, 'bir bin' -> 'bin' düzeltmeli)."""
    if n == 0:
        return "sıfır"
    if n < 0:
        return "eksi " + sayi_to_turkce(-n)
    gruplar = []
    while n > 0:
        gruplar.append(n % 1000)
        n //= 1000
    parcalar = []
    for i in range(len(gruplar) - 1, -1, -1):
        g = gruplar[i]
        if g == 0:
            continue
        if i == 1 and g == 1:          # "bin", "bir bin" değil
            parcalar.append("bin")
        else:
            parcalar.append(_uc_uc_basamak(g))
            if i > 0:
                parcalar.append(SCALES[i])
    return " ".join(parcalar)


def _para_oku(m):
    """32.500,00 TL -> otuz iki bin beş yüz lira ; kuruş 0 ise okunmaz."""
    tam = int(m.group(1).replace(".", ""))
    kurus = int(m.group(2)) if m.group(2) else 0
    out = sayi_to_turkce(tam) + " lira"
    if kurus:                          # sonda sıfırsa kuruş okunmaz (kural)
        out += " " + sayi_to_turkce(kurus) + " kuruş"
    return out


def _tarih_oku(m):
    """29.06.2026 -> yirmi dokuz Haziran iki bin yirmi altı."""
    g, a, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= a <= 12):
        return m.group(0)
    return f"{sayi_to_turkce(g)} {MONTHS[a]} {sayi_to_turkce(y)}"


def _saat_oku(m):
    """09:00 -> dokuz ; 17:30 -> on yedi otuz."""
    s, d = int(m.group(1)), int(m.group(2))
    out = sayi_to_turkce(s)
    if d:
        out += " " + sayi_to_turkce(d)
    return out


def _sade_sayi_oku(m):
    """1.245 -> bin iki yüz kırk beş (binlik nokta ayracı)."""
    return sayi_to_turkce(int(m.group(0).replace(".", "")))


def _kisaltma_oku(m):
    return ABBREV.get(m.group(0), " ".join(list(m.group(0).lower())))


def turkce_kucuk(s):
    """Türkçe-farkında küçük harf: I->ı, İ->i."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def sapka_temizle(s):
    """â/î/û -> a/i/u. DİKKAT: kâr->kar burada çöker (homograf kör noktası)."""
    return (s.replace("â", "a").replace("î", "i").replace("û", "u")
             .replace("Â", "a").replace("Î", "i").replace("Û", "u"))


def normalize(text):
    """Referans ve hipotezi aynı sözlü forma indirir. Sıralama önemli."""
    t = text
    # Para (TL, kuruşlu). Örn: 1.750,50 TL / 32.500,00 TL / 49,90 TL
    t = re.sub(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL", _para_oku, t)
    t = re.sub(r"(\d{1,3}(?:\.\d{3})*|\d+)\s*TL",
               lambda m: sayi_to_turkce(int(m.group(1).replace(".", ""))) + " lira", t)
    # Tarih gg.aa.yyyy
    t = re.sub(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", _tarih_oku, t)
    # Saat HH:MM
    t = re.sub(r"(\d{1,2}):(\d{2})", _saat_oku, t)
    # Kısaltmalar (büyük harfli 2+ blok)
    t = re.sub(r"\b[A-ZĞÜŞİÖÇ]{2,}\b", _kisaltma_oku, t)
    # Kalan sayılar (binlik ayraçlı veya düz)
    t = re.sub(r"\b\d{1,3}(?:\.\d{3})+\b", _sade_sayi_oku, t)
    t = re.sub(r"\b\d+\b", lambda m: sayi_to_turkce(int(m.group(0))), t)
    # Türkçe küçük harf + şapka temizliği + noktalama sadeleştirme
    t = turkce_kucuk(t)
    t = sapka_temizle(t)
    t = re.sub(r"['’]", " ", t)                # kesme işareti -> boşluk
    t = re.sub(r"[^\wğüşıöç ]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# =============================================================================
# BÖLÜM 2 — CER / WER (saf Python Levenshtein)
# =============================================================================

def _edit_distance(a, b):
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[n]


def cer(ref, hyp):
    ref = ref.replace(" ", "")
    hyp = hyp.replace(" ", "")
    return _edit_distance(ref, hyp) / max(1, len(ref))


def wer(ref, hyp):
    r, h = ref.split(), hyp.split()
    return _edit_distance(r, h) / max(1, len(r))


# =============================================================================
# BÖLÜM 3 — TEST SETİ (22 cümle, 11 kategori)
# flags: "kritik" = bankacılık-kritik ; "insan" = homograf/otomatik metrik kör
# =============================================================================

TEST_SET = [
    ("normal", "Selam dostum, benim bilgisayarım var.", []),
    ("normal", "İşleminiz başarıyla tamamlandı.", []),
    ("uzun", "Bugün hava biraz güneşliydi, ben de buna güvenerek şemsiyesiz çıktım, fakat sonra bir anda hava karardı ve yağmur yağmaya başladı.", []),
    ("uzun", "Kredi kartı ekstrenizin son ödeme tarihi yaklaştığı için, asgari tutarın altında ödeme yapmanız durumunda gecikme faizi işleyeceğini hatırlatmak isteriz.", []),
    ("soru", "Bugün ofise gelecek misin?", []),
    ("soru", "Başka bir işlem yapmak ister misiniz?", []),
    ("sayi", "Bugün ofiste 2 stajyer vardı ve her biri 2 bilgisayar getirmişti.", ["sadik_asr"]),
    ("sayi", "Hesabınıza son bir yılda 1.245 kez giriş yapıldı.", ["kritik", "sadik_asr"]),
    ("tarih", "İş Bankası'nda staja 29.06.2026'da başladım, maalesef 27.07.2026'da bitecek.", ["kritik", "insan", "sadik_asr"]),
    ("tarih", "Şubelerimiz hafta içi 09:00 ile 17:00 arasında hizmet vermektedir.", ["kritik", "insan", "sadik_asr"]),
    ("para", "Bu ay maaşım 32.500,00 TL yattı ama 1.750,50 TL'lik faturayı ödeyince azaldı.", ["kritik", "insan", "sadik_asr"]),
    ("para", "Kartınızdan 49,90 TL tutarında alışveriş yapıldı.", ["kritik", "insan", "sadik_asr"]),
    ("kisaltma", "TTS konusunda bizim dilimizde WER ölçerken hata oranı yüksek çıkabiliyor.", ["kritik"]),
    ("kisaltma", "KVKK kapsamında verileriniz güvenle saklanmaktadır.", ["kritik"]),
    ("ozel_isim", "Bugün Türkiye İş Bankası Genel Müdürlüğü'ne giderken Barbaros Bulvarı'nda kaza gördüm ve arkadaşım Mehmet ile karşılaştım.", []),
    ("ozel_isim", "Sayın Ayşe Yılmaz, Kadıköy şubemizdeki işleminiz onaylanmıştır.", []),
    ("ing_karisik", "Bu kodların debug'ını bitirdim, sen de kodları tekrar check eder misin?", []),
    ("ing_karisik", "Mobil bankacılık uygulamasına login olduktan sonra dashboard ekranından bakiyenizi görüntüleyebilirsiniz.", []),
    ("cagri_merkezi", "Merhaba, size özel düşük faizli ihtiyaç kredisi kampanyası tanımlandı. Yararlanmak ister misiniz?", []),
    ("cagri_merkezi", "Müşteri temsilcisine bağlanmak için sıfırı, ana menüye dönmek için yıldız tuşuna basınız.", []),
    ("homograf", "Şirketimiz bu çeyrek beklenenden yüksek kâr açıkladı.", ["insan"]),
    ("homograf", "Hesabınız hâlâ aktif değildir.", ["insan"]),
]

# =============================================================================
# BÖLÜM 4 — DEMO ASR HİPOTEZLERİ (ses yok; illüstratif)
# Gerçek koşuda bu alan faster-whisper transkripsiyonuyla dolar.
# Aşağıdaki metinler "orta kalite bir Türkçe TTS"in tipik davranışını simüle eder.
# =============================================================================

DEMO_ASR = {
    0:  "selam dostum benim bilgisayarım var",
    1:  "işleminiz başarıyla tamamlandı",
    2:  "bugün hava biraz güneşliydi ben de buna güvenerek şemsiyesiz çıktım fakat sonra bir anda hava karardı ve yağmur yağmaya başladı",
    3:  "kredi kartı ekstrenizin son ödeme tarihi yaklaştığı için asgari tutarın altında ödeme yapmanız durumunda gecikme faizi işleyeceğini hatırlatmak isteriz",
    4:  "bugün ofise gelecek misin",
    5:  "başka bir işlem yapmak ister misiniz",
    6:  "bugün ofiste iki stajyer vardı ve her biri iki bilgisayar getirmişti",
    # İYİ: 1.245 doğru okunmuş -> düşük CER
    7:  "hesabınıza son bir yılda bin iki yüz kırk beş kez giriş yapıldı",
    # KÖTÜ: tarihi rakam rakam okumuş "yirmi dokuz sıfır altı..." tarzı bozulma
    8:  "iş bankasında staja yirmi dokuz sıfır altı iki bin yirmi altıda başladım maalesef yirmi yedi sıfır yedi iki bin yirmi altıda bitecek",
    9:  "şubelerimiz hafta içi dokuz sıfır sıfır ile on yedi sıfır sıfır arasında hizmet vermektedir",
    # KÖTÜ: 00 kuruşu okumuş "sıfır kuruş" -> küçük sahte olmayan gerçek hata
    10: "bu ay maaşım otuz iki bin beş yüz lira sıfır kuruş yattı ama bin yedi yüz elli lira elli kuruşluk faturayı ödeyince azaldı",
    11: "kartınızdan kırk dokuz lira doksan kuruş tutarında alışveriş yapıldı",
    12: "te te se konusunda bizim dilimizde ve e er ölçerken hata oranı yüksek çıkabiliyor",
    # KÖTÜ: KVKK'yı "kıvık" okumuş -> round-trip yakalar
    13: "kıvık kapsamında verileriniz güvenle saklanmaktadır",
    14: "bugün türkiye iş bankası genel müdürlüğüne giderken barbaros bulvarında kaza gördüm ve arkadaşım mehmet ile karşılaştım",
    15: "sayın ayşe yılmaz kadıköy şubemizdeki işleminiz onaylanmıştır",
    16: "bu kodların debagını bitirdim sen de kodları tekrar çek eder misin",
    17: "mobil bankacılık uygulamasına login olduktan sonra dashboard ekranından bakiyenizi görüntüleyebilirsiniz",
    18: "merhaba size özel düşük faizli ihtiyaç kredisi kampanyası tanımlandı yararlanmak ister misiniz",
    19: "müşteri temsilcisine bağlanmak için sıfırı ana menüye dönmek için yıldız tuşuna basınız",
    # HOMOGRAF: TTS "kâr"ı "kar" (snow) okusa BİLE ASR ikisini de "kar" yazar -> CER=0
    20: "şirketimiz bu çeyrek beklenenden yüksek kar açıkladı",
    21: "hesabınız hala aktif değildir",
}


# =============================================================================
# BÖLÜM 5 — SKOR KARTI
# =============================================================================

def satir_degerlendir(idx, kategori, ref_metin, flags, asr_hyp):
    ref_norm = normalize(ref_metin)
    hyp_norm = normalize(asr_hyp)
    return {
        "idx": idx,
        "kategori": kategori,
        "flags": flags,
        "ref_norm": ref_norm,
        "hyp_norm": hyp_norm,
        "cer": cer(ref_norm, hyp_norm),
        "wer": wer(ref_norm, hyp_norm),
    }


def run_demo():
    print("=" * 92)
    print("TÜRKÇE TTS DEĞERLENDİRME — DEMO KOŞUSU (ses yok, simüle ASR)")
    print("Bacak 1: normalizasyon + CER | Bacak 2: UTMOSv2 = mock | Bacak 3: [insan] bayrağı")
    print("=" * 92)

    sonuclar = []
    for idx, (kat, metin, flags) in enumerate(TEST_SET):
        hyp = DEMO_ASR.get(idx, normalize(metin))  # eksikse mükemmel oku varsay
        sonuclar.append(satir_degerlendir(idx, kat, metin, flags, hyp))

    # ---- Cümle bazlı tablo ----
    print("\n{:<3} {:<14} {:>7} {:>7}  {:<6} {}".format(
        "#", "kategori", "CER%", "WER%", "bayrak", "durum"))
    print("-" * 92)
    for r in sonuclar:
        bayrak = ""
        if "kritik" in r["flags"]:
            bayrak += "K"
        if "insan" in r["flags"]:
            bayrak += "İ"
        # Karar mantığı: CER eşiği + insan bayrağı
        if "insan" in r["flags"]:
            durum = ">> İNSANA YOLLA (homograf; CER kör)"
        elif r["cer"] > 0.15:
            durum = "!! KIRMIZI BAYRAK (yüksek CER)"
        elif r["cer"] > 0.05:
            durum = " ~ gözden geçir"
        else:
            durum = " ok"
        print("{:<3} {:<14} {:>7.1f} {:>7.1f}  {:<6} {}".format(
            r["idx"], r["kategori"], r["cer"] * 100, r["wer"] * 100, bayrak or "-", durum))

    # ---- Kategori bazlı özet ----
    print("\n" + "=" * 92)
    print("KATEGORİ BAZLI ORTALAMA CER (bankacılık-kritik kategoriler işaretli)")
    print("=" * 92)
    kritik_kat = {"sayi", "tarih", "para", "kisaltma"}
    from collections import defaultdict
    grup = defaultdict(list)
    for r in sonuclar:
        grup[r["kategori"]].append(r["cer"])
    print("{:<14} {:>10} {:>8}  {}".format("kategori", "ort_CER%", "cümle", "not"))
    print("-" * 92)
    for kat in ["normal", "uzun", "soru", "sayi", "tarih", "para",
                "kisaltma", "ozel_isim", "ing_karisik", "cagri_merkezi", "homograf"]:
        vals = grup[kat]
        ort = sum(vals) / len(vals) * 100
        isaret = "  <-- KRİTİK" if kat in kritik_kat and ort > 5 else (
                 "  (homograf: CER yanıltıcı, insan şart)" if kat == "homograf" else "")
        print("{:<14} {:>10.1f} {:>8}{}".format(kat, ort, len(vals), isaret))

    # ---- İnsan spot-check kuyruğu ----
    insan_kuyruk = [r for r in sonuclar if "insan" in r["flags"]]
    print("\n" + "=" * 92)
    print(f"İNSAN SPOT-CHECK KUYRUĞU ({len(insan_kuyruk)} cümle) — otomatik metriğin kör olduğu yer")
    print("=" * 92)
    for r in insan_kuyruk:
        metin = TEST_SET[r["idx"]][1]
        print(f"  #{r['idx']}  CER={r['cer']*100:.1f}%  ->  {metin}")
    print("\n  NOT: Bu cümlelerde CER düşük (hatta 0) ama okuma yine de yanlış olabilir.")
    print("  Örn #20 kâr(profit)/kar(snow): ASR ikisini de 'kar' yazar -> CER=0 -> insan şart.")

    # ---- Bacak 2 durumu ----
    print("\n" + "=" * 92)
    print("BACAK 2 — UTMOSv2 (DOĞALLIK)")
    print("=" * 92)
    print("  Bu bacak GERÇEK .wav dosyası ister; demo modunda hesaplanmaz.")
    print("  Gerçek koşu: her .wav -> UTMOSv2 -> göreli MOS (A/B, sürüm regresyonu).")
    print("  Mutlak skora güvenilmez (Türkçe eğitilmedi); ayarı bozuk ama tutarlı tartı.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="ses olmadan simüle ASR ile koş")
    args = ap.parse_args()
    if args.demo or True:   # bu sürüm yalnız demo modunda gelir
        run_demo()
