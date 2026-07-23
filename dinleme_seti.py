#!/usr/bin/env python3
"""
dinleme_seti.py — Kor dinleme / MOS toplama seti hazirlar.

Sesleri anonim isimlerle kopyalar, karistirir, cevap anahtarini AYRI tutar.
Ciktisi tarayicida acilan bir HTML: dinleyici 1-5 puanlar, JSON indirir.

Kullanim:
    python3 dinleme_seti.py \
      --set Piper:./sesler --set VoxCPM:./sesler_voxcpm \
      --capa insan:./capa_insan --capa bozuk:./capa_bozuk \
      --sayi 10 -o ./dinleme_seti

--sayi: her ureticiden kac cumle secilecek (rastgele, ayni cumleler her uretici icin)
--capa: kalibrasyon capasi (opsiyonel ama onerilir)
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import hashlib
import html
from datetime import datetime

try:
    from turkish_tts_eval import TEST_SET
except ImportError:
    TEST_SET = []


def kategori_bul(fname):
    try:
        i = int(fname.split("_")[1].split(".")[0])
        return TEST_SET[i][0]
    except Exception:
        return "?"


def ref_bul(fname):
    try:
        i = int(fname.split("_")[1].split(".")[0])
        return TEST_SET[i][1]
    except Exception:
        return ""


def anon_id(uretici, fname, tuz):
    h = hashlib.sha1(f"{tuz}|{uretici}|{fname}".encode()).hexdigest()
    return h[:8]


HTML_SABLON = """<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Turkce TTS Dinleme Testi</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
       background: #f4f6f8; color: #1d2733; line-height: 1.55; }
.wrap { max-width: 720px; margin: 0 auto; padding: 28px 18px 100px; }
h1 { font-size: 22px; color: #0d2b45; margin: 0 0 6px; }
.yonerge { background: #fff; border: 1px solid #dbe2e8; border-radius: 8px;
           padding: 16px 18px; font-size: 14px; margin-bottom: 20px; }
.yonerge b { color: #0d2b45; }
.yonerge ul { margin: 8px 0 0; padding-left: 20px; }
.ad-kutu { margin-bottom: 20px; }
.ad-kutu input { font: inherit; padding: 8px 12px; border: 1px solid #c8d2db;
                 border-radius: 6px; width: 100%; max-width: 320px; }
.kart { background: #fff; border: 1px solid #dbe2e8; border-radius: 8px;
        padding: 16px 18px; margin-bottom: 14px; }
.kart .no { font-size: 11px; color: #62707f; text-transform: uppercase;
            letter-spacing: .5px; margin-bottom: 6px; }
audio { width: 100%; height: 36px; margin: 4px 0 12px; display: block; }
.skala { display: flex; gap: 6px; flex-wrap: wrap; }
.skala label { flex: 1; min-width: 60px; }
.skala input { display: none; }
.skala span { display: block; text-align: center; padding: 9px 4px; font-size: 13px;
              border: 1px solid #c8d2db; border-radius: 6px; cursor: pointer;
              background: #fff; transition: .12s; }
.skala span:hover { background: #eef2f6; }
.skala input:checked + span { background: #0d2b45; border-color: #0d2b45;
                              color: #fff; font-weight: 600; }
.skala .alt { font-size: 10px; color: #95a5a6; display: block; margin-top: 2px; }
.skala input:checked + span .alt { color: #b8c8d8; }
.bitir { position: fixed; bottom: 0; left: 0; right: 0; background: #fff;
         border-top: 1px solid #dbe2e8; padding: 12px 18px; text-align: center; }
.bitir button { font: inherit; font-size: 15px; font-weight: 600; padding: 11px 30px;
                background: #0d2b45; color: #fff; border: none; border-radius: 8px;
                cursor: pointer; }
.bitir button:disabled { background: #b8c2cc; cursor: not-allowed; }
.durum { font-size: 12px; color: #62707f; margin-top: 6px; }
</style></head><body><div class="wrap">
<h1>Turkce TTS Dinleme Testi</h1>
<div class="yonerge">
<b>Ne yapman gerekiyor:</b> Asagidaki her sesi dinle ve <b>ne kadar dogal</b>
oldugunu 1 ile 5 arasinda puanla.
<ul>
<li>Sadece <b>dogalliga</b> bak. Metni dogru okuyup okumadigi onemli degil.</li>
<li>Kulaga insan gibi mi geliyor, robot gibi mi?</li>
<li>Sesler karisik sirada. Hangi sistemden geldigini bilmiyorsun, bilmene gerek de yok.</li>
<li>Sessiz bir ortamda, kulaklikla dinle.</li>
<li>Hepsini puanlayinca en alttaki butona bas, dosya inecek. O dosyayi bana yolla.</li>
</ul>
</div>
<div class="ad-kutu">
<input id="ad" placeholder="Adin veya rumuzun (or: dinleyici_01)">
</div>
<div id="liste"></div>
</div>
<div class="bitir">
<button id="btn" disabled>Bitir ve dosyayi indir</button>
<div class="durum" id="durum">0 / __TOPLAM__ puanlandi</div>
</div>
<script>
var SESLER = __SESLER__;
var TOPLAM = SESLER.length;
var liste = document.getElementById("liste");
var etiketler = ["cok kotu","kotu","orta","iyi","cok iyi"];

SESLER.forEach(function(s, i) {
  var k = document.createElement("div");
  k.className = "kart";
  var h = '<div class="no">' + (i+1) + ' / ' + TOPLAM + '</div>';
  h += '<audio controls preload="none" src="sesler/' + s + '.wav"></audio>';
  h += '<div class="skala">';
  for (var p = 1; p <= 5; p++) {
    h += '<label><input type="radio" name="' + s + '" value="' + p + '">' +
         '<span>' + p + '<span class="alt">' + etiketler[p-1] + '</span></span></label>';
  }
  h += '</div>';
  k.innerHTML = h;
  liste.appendChild(k);
});

function guncelle() {
  var n = 0;
  SESLER.forEach(function(s) {
    if (document.querySelector('input[name="' + s + '"]:checked')) n++;
  });
  document.getElementById("durum").textContent = n + " / " + TOPLAM + " puanlandi";
  document.getElementById("btn").disabled = (n < TOPLAM);
}
liste.addEventListener("change", guncelle);

document.getElementById("btn").addEventListener("click", function() {
  var ad = document.getElementById("ad").value.trim() || "isimsiz";
  var puanlar = {};
  SESLER.forEach(function(s) {
    var el = document.querySelector('input[name="' + s + '"]:checked');
    puanlar[s] = el ? parseInt(el.value) : null;
  });
  var veri = { dinleyici: ad, zaman: new Date().toISOString(), puanlar: puanlar };
  var blob = new Blob([JSON.stringify(veri, null, 2)], {type: "application/json"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "mos_" + ad + ".json";
  a.click();
});
</script></body></html>"""


SESSIZ = ("silenceremove=start_periods=1:start_duration=0:"
          "start_threshold=-45dB:detection=peak")
FILTRE = SESSIZ + ",areverse," + SESSIZ + ",areverse,loudnorm=I=-23:TP=-2:LRA=7"


def hazirla(kaynak, hedef):
    """Her dosya ayni yoldan gecer: kirp -> loudnorm -> 22050 mono."""
    k = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", kaynak,
         "-af", FILTRE, "-ar", "22050", "-ac", "1",
         "-c:a", "pcm_s16le", hedef],
        capture_output=True, text=True)
    if k.returncode != 0:
        raise SystemExit("ffmpeg hatasi: " + kaynak + "\n" + k.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", required=True,
                    help="Ad:klasor (or: Piper:./sesler). Birden fazla verilebilir.")
    ap.add_argument("--capa", action="append", default=[],
                    help="Ad:klasor kalibrasyon capasi (or: insan:./capa_insan)")
    ap.add_argument("--sayi", type=int, default=10,
                    help="Her ureticiden kac cumle secilecek")
    ap.add_argument("--tohum", type=int, default=42, help="Rastgelelik tohumu")
    ap.add_argument("-o", "--cikti", default="./dinleme_seti")
    args = ap.parse_args()

    random.seed(args.tohum)
    tuz = str(random.randint(10**6, 10**7))

    setler = []
    for s in args.set:
        ad, yol = s.split(":", 1)
        setler.append((ad, yol))

    # Ortak dosyalari bul (her uretecide olan cumleler)
    ortak = None
    for ad, yol in setler:
        wavlar = {f for f in os.listdir(yol) if f.endswith(".wav")}
        ortak = wavlar if ortak is None else (ortak & wavlar)
    ortak = sorted(ortak)

    if args.sayi < len(ortak):
        secilen = sorted(random.sample(ortak, args.sayi))
    else:
        secilen = ortak

    ses_dizin = os.path.join(args.cikti, "sesler")
    os.makedirs(ses_dizin, exist_ok=True)

    anahtar = {}
    kopyalar = []

    for ad, yol in setler:
        for f in secilen:
            sid = anon_id(ad, f, tuz)
            hazirla(os.path.join(yol, f), os.path.join(ses_dizin, sid + ".wav"))
            anahtar[sid] = {"uretici": ad, "dosya": f,
                            "kategori": kategori_bul(f), "ref": ref_bul(f),
                            "tip": "test"}
            kopyalar.append(sid)

    # Kalibrasyon capalari
    for c in args.capa:
        ad, yol = c.split(":", 1)
        if not os.path.isdir(yol):
            print(f"[uyari] capa klasoru yok, atlandi: {yol}")
            continue
        for f in sorted(os.listdir(yol)):
            if not f.endswith(".wav"):
                continue
            sid = anon_id("CAPA_" + ad, f, tuz)
            hazirla(os.path.join(yol, f), os.path.join(ses_dizin, sid + ".wav"))
            anahtar[sid] = {"uretici": "CAPA_" + ad, "dosya": f,
                            "kategori": "capa", "ref": "", "tip": "capa"}
            kopyalar.append(sid)

    random.shuffle(kopyalar)

    with open(os.path.join(args.cikti, "cevap_anahtari.json"), "w", encoding="utf-8") as f:
        json.dump({"olusturuldu": datetime.now().isoformat(),
                   "tohum": args.tohum, "anahtar": anahtar}, f,
                  ensure_ascii=False, indent=2)

    h = (HTML_SABLON
         .replace("__SESLER__", json.dumps(kopyalar))
         .replace("__TOPLAM__", str(len(kopyalar))))
    with open(os.path.join(args.cikti, "dinle.html"), "w", encoding="utf-8") as f:
        f.write(h)

    print(f"[ok] {len(kopyalar)} ses hazirlandi -> {args.cikti}/")
    print(f"     {len(secilen)} cumle x {len(setler)} uretici"
          + (f" + {len(kopyalar) - len(secilen)*len(setler)} capa" if args.capa else ""))
    print(f"[ok] dinleyiciye ver : {args.cikti}/dinle.html (sesler/ klasoruyle birlikte)")
    print(f"[!!] SEN sakla, ACMA : {args.cikti}/cevap_anahtari.json")


if __name__ == "__main__":
    main()
