#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
synth_voxcpm.py — 22 cümlelik test setini VoxCPM2 ile seslendirir.
==================================================================
synth_piper.py ile aynı sözleşme:
  <out>/cikti_00.wav ... cikti_21.wav
  <out>/refs.tsv

Sonra (ANA ORTAMDA, venv'den çıkıp):
  python3 score_wav.py --batch <out> --refs <out>/refs.tsv

Tasarım kararları:
  - reference_wav_path ile ses SABİTLENİR (yoksa her cümle farklı konuşmacı olur).
  - normalize=False: VoxCPM'in kendi metin normalizasyonu KAPALI.
    Piper'a ham metin verdik, buna da ham veriyoruz. Adil A/B için.
  - denoise=False: sıfırdan sentez, temizlenecek referans yok.

LİSANS: VoxCPM Apache-2.0, self-hosted -> veri kurum dışına çıkmaz (KVKK uyumlu).
"""

import argparse
import os
import sys
import time

import numpy as np
import soundfile as sf

try:
    from turkish_tts_eval import TEST_SET
    from alan_cfer import on_normalize
except ImportError:
    sys.exit("HATA: 'turkish_tts_eval.py' aynı klasörde olmalı.")

from voxcpm import VoxCPM


def sample_rate_bul(model, varsayilan=48000):
    """Modelden örnekleme hızını okumaya çalış, bulamazsan varsayılana düş."""
    for yol in (model, getattr(model, "tts_model", None)):
        if yol is None:
            continue
        for ad in ("sample_rate", "sr", "output_sample_rate"):
            deger = getattr(yol, ad, None)
            if isinstance(deger, int) and deger > 0:
                return deger, ad
    return varsayilan, "VARSAYILAN (modelden okunamadi)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-wav", required=True,
                    help="Sesi sabitleyen referans .wav (klonlanacak ses)")
    ap.add_argument("--out", default="./sesler_voxcpm", help="çıktı klasörü")
    ap.add_argument("--device", default="cpu", help="cpu / mps / cuda")
    ap.add_argument("--normalize", action="store_true",
                    help="VoxCPM'in KENDI metin normalizasyonunu ac (deney icin).")
    ap.add_argument("--on-normalize", action="store_true",
                    help="BIZIM katman: kritik alanlari sozlu forma cevirip modele oyle ver.")
    ap.add_argument("--atla", action="store_true",
                    help="Zaten üretilmiş .wav'ları atla (yarıda kalan koşuyu sürdür)")
    args = ap.parse_args()

    if not os.path.isfile(args.ref_wav):
        sys.exit(f"HATA: referans ses bulunamadi: {args.ref_wav}")

    os.makedirs(args.out, exist_ok=True)

    # refs.tsv — synth_piper.py ile birebir aynı format
    refs_path = os.path.join(args.out, "refs.tsv")
    with open(refs_path, "w", encoding="utf-8") as f:
        for idx, (_kat, metin, flags) in enumerate(TEST_SET):
            f.write(f"cikti_{idx:02d}.wav\t{metin}\t{','.join(flags)}\n")
    print(f"[refs] yazildi -> {refs_path}  ({len(TEST_SET)} satir)")

    print(f"[model] VoxCPM yukleniyor (device={args.device})... bir kez yuklenir.")
    model = VoxCPM.from_pretrained(
        "openbmb/VoxCPM2",
        device=args.device,
        optimize=False,      # torch.compile CUDA icin, CPU'da kapali
        load_denoiser=False, # referans temizleme gereksiz
    )

    sr, kaynak = sample_rate_bul(model)
    print(f"[model] sample_rate = {sr} Hz  (kaynak: {kaynak})")
    print(f"[synth] referans ses = {args.ref_wav}")
    if args.normalize:
        print("[synth] normalize=True  (VoxCPM KENDI normalizasyonunu yapiyor - DENEY KOSUSU)\n")
    else:
        print("[synth] normalize=False (VoxCPM kendi normalizasyonunu YAPMIYOR - baseline)\n")
    if args.on_normalize:
        print("[synth] on-normalize=True (BIZIM katman: kritik alanlar sozlu forma cevriliyor)\n")

    basari = 0
    t0 = time.time()
    for idx, (kat, metin, _flags) in enumerate(TEST_SET):
        wav = os.path.join(args.out, f"cikti_{idx:02d}.wav")

        if args.atla and os.path.isfile(wav) and os.path.getsize(wav) > 0:
            print(f"  - cikti_{idx:02d}.wav  [{kat}]  (atlandi, zaten var)")
            basari += 1
            continue

        soylenecek = on_normalize(metin) if args.on_normalize else metin
        if args.on_normalize and soylenecek != metin:
            print(f"    [on-norm] {soylenecek}")

        try:
            ts = time.time()
            ses = model.generate(
                text=soylenecek,
                reference_wav_path=args.ref_wav,
                normalize=args.normalize,
                denoise=False,
            )
            ses = np.asarray(ses, dtype=np.float32)
            sf.write(wav, ses, sr)
            sure = time.time() - ts
            uzunluk = len(ses) / sr
            print(f"  + cikti_{idx:02d}.wav  [{kat}]  {uzunluk:.1f}s ses / {sure:.0f}s uretim")
            basari += 1
        except Exception as e:
            print(f"  x cikti_{idx:02d}.wav  [{kat}]  HATA: {e}")

    dk = (time.time() - t0) / 60
    print(f"\n[bitti] {basari}/{len(TEST_SET)} ses uretildi. Toplam {dk:.1f} dakika.")
    print("Simdi venv'den cik ve ana ortamda puanla:")
    print("  deactivate")
    print(f"  python3 score_wav.py --batch {args.out} --refs {refs_path}")


if __name__ == "__main__":
    main()
