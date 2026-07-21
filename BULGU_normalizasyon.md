# Bulgu: VoxCPM normalize=True Turkce rakami Ingilizce okuyor

## Deney
- A (norm=False, baseline), K (norm=False, kontrol), N (norm=True, deney)
- A vs K = model gurultusu, A vs N = normalizasyon etkisi

## Sonuc
normalize=True acikken sayi/tarih/para Ingilizce okunuyor:
- cikti_08 tarih: "29.06" -> "the 29th of june"  (CER 0 -> 32)
- cikti_09 saat:  "09:00" -> "nine o clock"       (CER 24 -> 22, ing)
- cikti_10 para:  sayilar -> "forty two point five" (ayrisma +53)
- cikti_11 para:  "49,90 TL" -> "forty nine ninety" (CER 0 -> 37)

Model bu cumlelerde tutarli (A=K=0), yani rastgelelik degil.

## Cikarim
Uc yol da cozmuyor:
1. Daha iyi model (VoxCPM 2B) -> ham metinde yine yanlis
2. Modelin kendi normalizasyonu -> Turkce'yi Ingilizce'ye ceviriyor
3. Sonuc: Turkce'ye ozel ayri katman ZORUNLU

## Metodoloji notu
Kor nokta sayisi a/K arasinda 4<->2 oynuyor. Ortalamaya bakma, cumle bazli oku.
