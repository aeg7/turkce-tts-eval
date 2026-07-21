# Turkce TTS Degerlendirme Harness

Self-hosted, KVKK uyumlu Turkce TTS degerlendirme akisi.
Uc bacak: okuma dogrulugu (cift ASR + CER), dogallik (UTMOSv2),
insan spot-check (homograf, tonlama).

## Ana bulgu

| Kosu | CFER |
|---|---|
| Piper ham metin | %54 |
| VoxCPM ham metin | %54 |
| VoxCPM kendi normalizasyonu | %77 |
| Piper + Turkce katman | %0 |
| VoxCPM + Turkce katman | %0 |

Kritik alan hatalarinin sebebi model kalitesi degil, TTS'e rakam
gosterilmesi. Sozlu forma cevrilince iki ureticide de sifira iniyor.

Detay: DEGISIKLIKLER.md

## Raporlar

    rapor_katman.html          Piper ham vs Piper + katman
    rapor_katman_voxcpm.html   VoxCPM ham vs VoxCPM + katman

Ses yollari goreli, ses klasorleri repoda. cikti_11 karti farki en net
gosteren yer.

Yeniden uretmek icin:

    python3 rapor.py piper.json piper_norm.json \
      --ad-a "Piper ham" --ad-b "Piper + katman" \
      --ses-a sesler --ses-b sesler_piper_norm -o r.html

## Dosyalar

| Dosya | Is |
|---|---|
| turkish_tts_eval.py | normalizasyon katmani, CER/WER, TEST_SET |
| score_wav.py | skorlayici (Whisper + wav2vec2 + UTMOSv2) |
| alan_cfer.py | alan bazli CFER + on-normalizasyon |
| gerekce.py | kural motoru (deterministik sebep kodlari) |
| rapor.py | HTML skor karti |
| synth_piper.py / synth_voxcpm.py | ureticiler |
| cfer.py | eski surum, kullanilmiyor |

## Notlar

- Turkce'de WER degil CER (sondan eklemeli dil).
- Karsilastirmadan once iki taraf da ayni sozlu forma normalize edilir.
- Homograf (kâr/kar) hicbir otomatik metrikle yakalanmaz, insana gider.
- Piper modeli (tr_TR-dfki-medium.onnx) repoda yok.
- Lisans: faster-whisper MIT, wav2vec2 Apache 2.0, VoxCPM2 Apache 2.0.
  Hepsi self-hosted. NISQA kullanilmadi, agirliklari ticari degil.
