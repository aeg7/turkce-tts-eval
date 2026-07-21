# Onceki surumden bu yana

## 1. Ikinci ASR (wav2vec2)

Whisper duydugunu degil, duzelttigini yaziyor. TTS "yirmi dokuz nokta
sifir alti" dese bile Whisper "29.06" yaziyor, CER sifir cikiyor, gercek
okuma hatasi hic gorunmuyor. wav2vec2 duzeltmiyor, duydugu fonemi
yaziyor. Iki ASR'in farki on puani gecerse kor nokta bayragi kalkiyor.

Esik veriye dayandi. Gurultu tavani alti puan, hata tabani on dort puan,
arada bosluk var, on tam ortasi.

wav2vec2 ana metrik degil. Kisaltmada sahte alarm uretiyor (KVKK'yi
"keve keke" yaziyor), o yuzden kisaltma kapsam disi.

## 2. Alan bazli CFER

CER "sesin yuzde kaci bozuk" diyor, muhendis metrigi. CFER "kritik
degerlerin kaci yanlis okundu" diyor, karar verici metrigi. Tek yanlis
tarih, cumlenin geri kalani kusursuz olsa bile felaket.

Kritik alanlari (tarih, saat, para, sayi, kisaltma) referans metinden
regex ile kendi buluyor. Elle etiketleme yok. Test setine yuz cumle
eklesen tek satir yazmiyorsun.

Olcum de cumle degil alan seviyesinde. "Bu cumlede sorun var" yerine
"bu cumledeki ikinci tarih yanlis, soyle okundu" diyor.

## 3. On-normalizasyon deneyi (ana bulgu)

Rakami TTS'e vermeden once sozlu forma cevirdim.

| Kosu | CFER |
|---|---|
| Piper ham metin | %54 |
| VoxCPM ham metin | %54 |
| VoxCPM kendi normalizasyonu | %77 |
| Piper + Turkce katman | %0 |
| VoxCPM + Turkce katman | %0 |

Uc sonuc:

- Daha iyi model almak cozmuyor. VoxCPM 2B parametre, Piper'la ayni
  hatayi yapiyor.
- Modelin kendi normalizasyonunu acmak daha beter yapiyor. Turkce
  rakami Ingilizce okuyor ("forty nine ninety"), CFER %77'ye cikiyor.
- Turkce'ye ozel ayri katman cozuyor, iki ureticide de sifir.

Yani sorun model kalitesinde degil, TTS'e rakam gostermemizde.

## Yan bulgu: katman naif yazilirsa yeni hata uretiyor

"TL'lik" ifadesindeki ek, TL'nin yazili okunusuna gore secilmis. Sozlu
forma cevirince "kurus'lik" cikiyor, dogrusu "kurusluk". Unlu uyumunu
da ceviren bir duzeltme ekledim. Katmanin Turkce'ye ozel olmak zorunda
olmasinin somut ornegi.

## Sinir

Deney kismen kendi kendini dogruluyor. TTS'e verdigim metinle
karsilastirma hedefini ayni fonksiyon uretiyor.

Kanitladigi sey: Piper ve VoxCPM sozlu form verilince dogru okuyor,
yani hata fonetik yetenekte degil format cozumlemesinde.

Kanitlamadigi sey: sozlu formun kendisinin dogru Turkce oldugu.
"09:00" icin "dokuz" mu, "saat dokuz" mu, "dokuz sifir sifir" mi?
Buna karar veren otomatik arac yok, urun ekibiyle mutabakat gerekiyor.

## Acik kalemler

- Kor dinleme testi henuz dagitilmadi, cipa eklenecek.
- Normalizasyon hedef formlari mutabakat bekliyor.
- Kisaltma okunusu: sozluk "ka ve ka ka" diyor, Piper "ke ve ke ke".
