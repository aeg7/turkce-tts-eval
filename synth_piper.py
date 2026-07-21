#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synth_piper.py — 22 cümlelik test setini Piper (self-hosted) ile seslendirir.
============================================================================
Üretir:
  <out>/cikti_00.wav ... cikti_21.wav
  <out>/refs.tsv                         (score_wav.py --batch için hazır)

Sonra:
  python3 score_wav.py --batch <out> --refs <out>/refs.tsv

Piper'ı komut satırından çağırır (sende çalışan form):
    echo "metin" | piper -m <model> -f <cikti.wav>

Aynı klasörde bulunmalı:
  - turkish_tts_eval.py  (TEST_SET buradan gelir)
  - tr_TR-dfki-medium.onnx  +  .onnx.json  (indirdiğin Türkçe model)

LİSANS NOTU:
  Piper self-hosted, API yok -> veri kurum dışına çıkmaz (KVKK uyumlu).
  Kullanım: TTS araştırması/değerlendirme. Prod ürün için sesin MODEL_CARD lisansı teyit edilmeli.
"""

import argparse
import os
import subprocess
import sys

try:
    from turkish_tts_eval import TEST_SET
except ImportError:
    sys.exit("HATA: 'turkish_tts_eval.py' aynı klasörde olmalı.")

try:
    from alan_cfer import on_normalize
except ImportError:
    on_normalize = None


def synth_one(text, model, wav_path):
    """Tek cümle -> .wav.  echo "metin" | piper -m <model> -f <wav>"""
    proc = subprocess.run(
        ["piper", "-m", model, "-f", wav_path],
        input=text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "ignore").strip() or "piper hata")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="tr_TR-dfki-medium",
                    help="Piper model adı/yolu (indirdiğin .onnx ile aynı ad)")
    ap.add_argument("--out", default="./sesler", help="çıktı klasörü")
    ap.add_argument("--on-normalize", action="store_true",
                    help="kritik alanlari TTS'e vermeden once sozlu forma cevir")
    args = ap.parse_args()

    if args.on_normalize and on_normalize is None:
        sys.exit("HATA: --on-normalize icin alan_cfer.py gerekli.")

    os.makedirs(args.out, exist_ok=True)

    # refs.tsv (batch scorer için): dosya <TAB> referans <TAB> flags
    refs_path = os.path.join(args.out, "refs.tsv")
    with open(refs_path, "w", encoding="utf-8") as f:
        for idx, (_kat, metin, flags) in enumerate(TEST_SET):
            f.write(f"cikti_{idx:02d}.wav\t{metin}\t{','.join(flags)}\n")
    print(f"[refs] yazıldı -> {refs_path}  ({len(TEST_SET)} satır)")

    print(f"[synth] model={args.model}, çıktı={args.out}")
    basari = 0
    for idx, (kat, metin, _flags) in enumerate(TEST_SET):
        wav = os.path.join(args.out, f"cikti_{idx:02d}.wav")
        soylenecek = on_normalize(metin) if args.on_normalize else metin
        if args.on_normalize and soylenecek != metin:
            print(f"    [on-norm] {soylenecek}")
        try:
            synth_one(soylenecek, args.model, wav)
            print(f"  ✓ cikti_{idx:02d}.wav  [{kat}]")
            basari += 1
        except Exception as e:
            print(f"  ✗ cikti_{idx:02d}.wav  HATA: {e}")

    print(f"\n[bitti] {basari}/{len(TEST_SET)} ses üretildi.")
    print(f"Şimdi puanla:\n  python3 score_wav.py --batch {args.out} --refs {refs_path}")


if __name__ == "__main__":
    main()
