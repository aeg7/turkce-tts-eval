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
