#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_wav.py — Bir .wav dosyasını üç bacaklı yapıya göre puanlar.
================================================================
Zincir:  .wav --(faster-whisper)--> metin --(normalize)--> CER/WER  (+ opsiyonel UTMOSv2)

Aynı klasörde 'turkish_tts_eval.py' bulunmalı (normalize/cer/wer motorunu ondan alır).

KULLANIM
--------
# 1) Tam koşu (ses -> Whisper -> skor):
python score_wav.py --wav cikti_11.wav --ref "Kartınızdan 49,90 TL tutarında alışveriş yapıldı."

# 2) Whisper'ı atla, elindeki transkripsiyonu ver (motoru test etmek için, ses gerekmez):
python score_wav.py --hyp "kartınızdan kırk dokuz lira doksan kuruş tutarında alışveriş yapıldı" \
                    --ref "Kartınızdan 49,90 TL tutarında alışveriş yapıldı."

# 3) Toplu koşu (bir klasördeki tüm .wav'lar, referanslar bir tsv'de):
python score_wav.py --batch ./sesler --refs refs.tsv
#   refs.tsv formatı (sekmeyle ayrık):  dosya_adi.wav <TAB> referans metin <TAB> flags(opsiyonel)

LİSANS NOTU
-----------
- faster-whisper: MIT -> banka için uygun, self-hosted.
- UTMOSv2       : kurulmadan çalışır (opsiyonel); LİSANSI TEYİT EDİLMELİ (dokümanda "kontrol").
"""

import argparse
import os
import sys

# --- Motoru harness'tan al ---
try:
    from turkish_tts_eval import normalize, cer, wer, TEST_SET
except ImportError:
    sys.exit("HATA: 'turkish_tts_eval.py' aynı klasörde olmalı.")

def kategori_bul(fname):
    """cikti_08.wav -> TEST_SET[8][0] -> 'tarih'"""
    try:
        i = int(fname.split("_")[1].split(".")[0])
        return TEST_SET[i][0]
    except Exception:
        return "?"


# =============================================================================
# BACAK 1 — ASR (faster-whisper). Model ağırlıkları HF'ten iner (ilk koşuda).
# =============================================================================
_WHISPER = None

def get_whisper(model_size="large-v3", device="auto", compute_type="auto"):
    """Modeli bir kez yükle (lazy). GPU yoksa device='cpu', compute_type='int8'."""
    global _WHISPER
    if _WHISPER is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            sys.exit("HATA: faster-whisper yok. Kur: pip install faster-whisper")
        _WHISPER = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _WHISPER


def transcribe(wav_path, model_size="large-v3"):
    """.wav -> ham Türkçe transkripsiyon (normalize edilmemiş)."""
    model = get_whisper(model_size)
    segments, _info = model.transcribe(
    wav_path,
    language="tr",
    beam_size=5,
    condition_on_previous_text=False,   # bağlamdan "düzeltme" eğilimini kır
    temperature=0.0,                     # deterministik, uydurma yok
    without_timestamps=True,
)
    return " ".join(seg.text for seg in segments).strip()

# =============================================================================
# BACAK 1-B — SADIK ASR (wav2vec2 / CTC). Whisper'ın maskelediği okuma
# hatalarını görünür kılar. Sadece 'sadik_asr' bayraklı cümlelerde koşar.
# =============================================================================
_W2V2 = None      # (model, processor) bir kez yüklenir

def get_w2v2(model_id="mpoyraz/wav2vec2-xls-r-300m-cv8-turkish"):
    """wav2vec2 modelini + processor'ı bir kez yükle (lazy)."""
    global _W2V2
    if _W2V2 is None:
        try:
            import librosa  # noqa: F401  (kullanımı transcribe_w2v2 içinde)
            import torch     # noqa: F401
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        except ImportError:
            sys.exit("HATA: wav2vec2 için kur: pip install torch transformers librosa soundfile")
        processor = Wav2Vec2Processor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id)
        _W2V2 = (model, processor)
    return _W2V2


def transcribe_w2v2(wav_path):
    """.wav -> sadık (fonetik) transkripsiyon. Duyduğunu yorumlamadan yazar."""
    import librosa
    import torch
    model, processor = get_w2v2()
    ses, _ = librosa.load(wav_path, sr=16000)
    girdi = processor(ses, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = model(girdi).logits
    ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(ids)[0].strip()


# =============================================================================
# BACAK 2 — UTMOSv2 (doğallık, göreli MOS). Opsiyonel; kuruluysa çalışır.
# =============================================================================
_UTMOS = None

def utmos_score(wav_path):
    """.wav -> tahmini MOS (1-5). Kurulu değilse None döner (bacak atlanır)."""
    global _UTMOS
    try:
        import utmosv2
    except ImportError:
        return None
    if _UTMOS is None:
        _UTMOS = utmosv2.create_model(pretrained=True)
    try:
        return float(_UTMOS.predict(input_path=wav_path, device="cpu"))
    except Exception as e:
        print(f"  (UTMOSv2 hatası, bacak atlandı: {e})")
        return None


# =============================================================================
# SKORLAMA + KARAR
# =============================================================================
def karar(cer_val, flags, ayrisma=None, esik=0.10):
    kor_nokta = ayrisma is not None and ayrisma > esik
    insan = "insan" in flags

    # Kör nokta + insan aynı anda: ikisini birleştir
    if kor_nokta and insan:
        return f"!! KÖR NOKTA + İNSAN (w2v2 ayrışma +{ayrisma*100:.0f} puan; insan bayrağı da var)"
    if kor_nokta:
        return f"!! KÖR NOKTA (Whisper maskeledi; w2v2 ayrışma +{ayrisma*100:.0f} puan)"
    if insan:
        return ">> İNSANA YOLLA (insan bayrağı; CER kör olabilir)"
    if cer_val > 0.15:
        return "!! KIRMIZI BAYRAK (yüksek CER)"
    if cer_val > 0.05:
        return " ~ gözden geçir"
    return " ok"


def score_one(ref, hyp_ham, wav_path=None, flags=None, esik=0.10):
    flags = flags or []
    ref_n = normalize(ref)
    cer_ham = cer(ref, hyp_ham)          # normalizasyon ONCESI ham CER
    hyp_n = normalize(hyp_ham)
    c, w = cer(ref_n, hyp_n), wer(ref_n, hyp_n)
    mos = utmos_score(wav_path) if wav_path else None

    # --- Sadık ASR ayrışma kontrolü (yalnız 'sadik_asr' bayraklı + gerçek ses) ---
    w2v2_cer = None
    ayrisma = None
    w2v2_ham = None
    w2v2_n = None
    if "sadik_asr" in flags and wav_path:
        try:
            w2v2_ham = transcribe_w2v2(wav_path)
            w2v2_n = normalize(w2v2_ham)
            w2v2_cer = cer(ref_n, w2v2_n)
            ayrisma = w2v2_cer - c        # wav2vec2 ne kadar fazla hata goruyor
        except Exception as e:
            print(f"  (wav2vec2 hatasi, ayrisma atlandi: {e})")

    return {"ref_ham": ref, "ref_n": ref_n,
            "hyp_ham": hyp_ham, "hyp_n": hyp_n,
            "w2v2_ham": w2v2_ham, "w2v2_n": w2v2_n,
            "cer": c, "wer": w, "cer_ham": cer_ham,
            "mos": mos, "flags": flags,
            "w2v2_cer": w2v2_cer, "ayrisma": ayrisma,
            "karar": karar(c, flags, ayrisma, esik)}

def yazdir_tek(res, ref_ham, hyp_ham):
    print("=" * 88)
    print("REFERANS (ham) :", ref_ham)
    print("ASR ÇIKTISI    :", hyp_ham)
    print("-" * 88)
    print("REF  (normalize):", res["ref_n"])
    print("HYP  (normalize):", res["hyp_n"])
    print("-" * 88)
    print(f"CER (Türkçe için asıl metrik) : {res['cer']*100:6.2f} %")
    print(f"WER (bilgi amaçlı)            : {res['wer']*100:6.2f} %")
    if res["mos"] is not None:
        print(f"UTMOSv2 (göreli MOS, mutlak değil): {res['mos']:.2f} / 5")
    else:
        print("UTMOSv2: kurulu değil -> doğallık bacağı atlandı")
    print("-" * 88)
    print("KARAR:", res["karar"])
    print("=" * 88)


# =============================================================================
# MAIN
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", help="Puanlanacak .wav (faster-whisper ile yazıya dökülür)")
    ap.add_argument("--ref", help="Referans (girdi) metni")
    ap.add_argument("--hyp", help="Whisper'ı atla; hazır transkripsiyonu ver")
    ap.add_argument("--batch", help="Klasör: içindeki tüm .wav'ları puanla")
    ap.add_argument("--refs", help="Toplu mod için tsv: dosya<TAB>referans<TAB>flags")
    ap.add_argument("--model", default="large-v3", help="faster-whisper model boyutu")
    ap.add_argument("--json", help="Sonuclari JSON dosyasina yaz (karsilastirma icin)")
    ap.add_argument("--esik", type=float, default=0.10,
                    help="Sadık ASR ayrışma eşiği (oran, 0.10 = yuzde 10). Aşılırsa KÖR NOKTA.")
    args = ap.parse_args()

    # --- TOPLU MOD ---
    if args.batch:
        if not args.refs:
            sys.exit("Toplu mod --refs tsv ister.")
        ref_map = {}
        with open(args.refs, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    fname, ref = parts[0], parts[1]
                    flags = parts[2].split(",") if len(parts) > 2 and parts[2] else []
                    ref_map[fname] = (ref, flags)
        print("{:<18} {:>7} {:>7} {:>7} {:>7} {:>6}  {}".format(
            "dosya", "CER%", "WER%", "w2v2%", "ayrış", "MOS", "karar"))
        print("-" * 100)
        mos_list = []
        sonuclar = {}
        for fname in sorted(ref_map):
            wpath = os.path.join(args.batch, fname)
            if not os.path.exists(wpath):
                print(f"{fname:<20}  (bulunamadı)")
                continue
            ref, flags = ref_map[fname]
            hyp = transcribe(wpath, args.model)
            r = score_one(ref, hyp, wpath, flags, args.esik)
            w2 = f"{r['w2v2_cer']*100:.1f}" if r["w2v2_cer"] is not None else "-"
            ay = f"+{r['ayrisma']*100:.0f}" if r["ayrisma"] is not None else "-"
            ms = f"{r['mos']:.2f}" if r["mos"] is not None else "-"
            if r["mos"] is not None:
                mos_list.append(r["mos"])
            print("{:<18} {:>7.1f} {:>7.1f} {:>7} {:>7} {:>6}  {}".format(
                fname, r["cer"]*100, r["wer"]*100, w2, ay, ms, r["karar"]))
            sonuclar[fname] = {
		"kategori": kategori_bul(fname),
                "ref": ref,
                "ref_n": r["ref_n"],
                "whisper_ham": r["hyp_ham"],
                "whisper_n": r["hyp_n"],
                "w2v2_ham": r["w2v2_ham"],
                "w2v2_n": r["w2v2_n"],
                "cer": r["cer"],
                "wer": r["wer"],
                "cer_ham": r["cer_ham"],
                "w2v2_cer": r["w2v2_cer"],
                "ayrisma": r["ayrisma"],
                "mos": r["mos"],
                "karar": r["karar"],
                "flags": flags,
            }

        if mos_list:
            ort = sum(mos_list) / len(mos_list)
            print("-" * 100)
            print(f"UTMOSv2 ortalama: {ort:.2f} / 5  ({len(mos_list)} dosya)")
            print("NOT: goreli sinyal. Mutlak kalite degil, A/B karsilastirmasi icin.")
        if args.json:
            import json
            with open(args.json, "w", encoding="utf-8") as jf:
                json.dump(sonuclar, jf, ensure_ascii=False, indent=2)
            print(f"[json] yazildi -> {args.json}")
        return

    # --- TEK DOSYA MOD ---
    if not args.ref:
        sys.exit("--ref (referans metin) zorunlu.")
    if args.hyp:
        hyp_ham = args.hyp
        wav = None
    elif args.wav:
        print(f"[faster-whisper] '{args.wav}' yazıya dökülüyor...")
        hyp_ham = transcribe(args.wav, args.model)
        wav = args.wav
    else:
        sys.exit("--wav veya --hyp gerekli.")
    res = score_one(args.ref, hyp_ham, wav, esik=args.esik)
    yazdir_tek(res, args.ref, hyp_ham)


if __name__ == "__main__":
    main()
