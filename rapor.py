#!/usr/bin/env python3
"""
rapor.py — Skor JSON'larindan tek dosya HTML rapor uretir.
Eslestirilmis gorunum: her cumle tek kart, A ve B yan yana.

Kullanim:
    python3 rapor.py piper.json voxcpm.json \
      --ad-a Piper --ad-b VoxCPM \
      --ses-a ./sesler --ses-b ./sesler_voxcpm \
      -o rapor_ab.html
"""

import argparse
import json
import html
import difflib
from gerekce import gerekce_uret, ESIK_AYRISMA
from alan_cfer import (cfer_hesapla_uyumlu as cfer_hesapla,
                       filtre_kategorisi, ALAN_ESIK)

MOS_ESIK = 0.30

KOD_SOZLUK = {
    "TEMIZ":        ("İki ASR de temiz, ayrışma yok. Okuma doğru.", "ok"),
    "MASKELEME":    ("Whisper duyduğunu düzeltip yazıyor, gerçek okuma hatasını gizliyor. "
                     "Sadık ASR hatayı görüyor. CER burada sahte.", "kirmizi"),
    "CIFT_TETIK":   ("Hem gerçek okuma hatası hem maskeleme var. En kötü durum.", "kirmizi"),
    "GERCEK_HATA":  ("Whisper düzeltici bir model, buna rağmen hatayı örtemiyor. "
                     "TTS metni gerçekten yanlış okumuş.", "kirmizi"),
    "SINIRDA":      ("CER yüzde 5 ile 15 arası. Kırmızı değil ama temiz de değil.", "sari"),
    "W2V2_GURULTU": ("Sadık ASR biraz ayrışıyor ama eşiğin altında. "
                     "Bu wav2vec2'nin kendi gürültüsü, alarm değil.", "ok"),
    "INSAN":        ("Otomatik metrik burada tek başına karar veremez. Kulakla dinlenmeli.", "mavi"),
    "CER_ANLAMSIZ": ("CER sıfır ama bu 'doğru okundu' demek değil, 'ölçemedim' demek. "
                     "Homografta iki okunuş aynı metne düşüyor. Sinyal boş.", "mavi"),
    "NORM_KAZANC":  ("Normalizasyon katmanı sahte hatayı temizledi. "
                     "Bu katman olmasaydı yanlış alarm verilirdi.", "yesil"),
    "KRITIK":       ("Bankacılık açısından yanlış okumak pahalı.", "kirmizi"),
}

BAYRAK_SOZLUK = {
    "kritik":    "Bankacılıkta yanlış okumak pahalı (tarih, para, sayı).",
    "sadik_asr": "Whisper burada maskeleme yapabilir. İkinci ASR (wav2vec2) devreye girer.",
    "insan":     "Otomatik metrik burada kör. CER'e bakılmaz, insana gider.",
}

CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0;
       background: #f4f6f8; color: #1d2733; line-height: 1.55; }
.wrap { max-width: 1240px; margin: 0 auto; padding: 32px 20px 80px; }
h1 { font-size: 26px; margin: 0 0 4px; color: #0d2b45; }
.sub { color: #62707f; font-size: 14px; margin-bottom: 24px; }
h2 { font-size: 19px; margin: 34px 0 12px; color: #0d2b45;
     border-bottom: 2px solid #d7dee5; padding-bottom: 6px; }
h3.kat { font-size: 15px; border: none; margin: 26px 0 10px; color: #0d2b45;
         text-transform: uppercase; letter-spacing: .6px; }
.ozet { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.kutu { background: #fff; border: 1px solid #dbe2e8; border-radius: 8px;
        padding: 13px 17px; min-width: 140px; }
.kutu .n { font-size: 23px; font-weight: 700; color: #0d2b45; }
.kutu .l { font-size: 11px; color: #62707f; text-transform: uppercase; letter-spacing: .4px; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border: 1px solid #dbe2e8; border-radius: 8px; overflow: hidden;
        font-size: 13px; margin-bottom: 10px; }
th { background: #eef2f6; text-align: left; padding: 9px 12px;
     font-size: 11px; text-transform: uppercase; letter-spacing: .4px; color: #4a5764; }
td { padding: 9px 12px; border-top: 1px solid #eef1f4; vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }

.cift { background: #fff; border: 1px solid #dbe2e8; border-radius: 8px;
        margin-bottom: 14px; overflow: hidden; }
.cift-bas { padding: 12px 16px; border-bottom: 1px solid #eef1f4; background: #fafbfc; }
.cift-bas .ad { font-family: ui-monospace, Menlo, monospace; font-size: 14px;
                font-weight: 600; color: #0d2b45; }
.cift-bas .cumle { font-size: 13px; color: #3d4a57; font-style: italic; margin-top: 4px; }
.cift-govde { display: grid; grid-template-columns: 1fr 1fr; }
.yan { padding: 12px 16px; border-left: 4px solid #b8c2cc; }
.yan + .yan { border-top: none; box-shadow: inset 1px 0 0 #eef1f4; }
.yan.kirmizi { border-left-color: #c0392b; }
.yan.sari    { border-left-color: #d68910; }
.yan.mavi    { border-left-color: #2471a3; }
.yan.ok      { border-left-color: #27ae60; }
.yan .uretici { font-size: 11px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .6px; color: #62707f; margin-bottom: 6px; }

.rozet { display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 7px;
         border-radius: 3px; margin: 0 4px 4px 0; letter-spacing: .3px; }
.r-kirmizi { background: #fdeceb; color: #a93226; }
.r-sari    { background: #fdf3e3; color: #9c640c; }
.r-mavi    { background: #eaf2f8; color: #1a5276; }
.r-ok      { background: #eafaf1; color: #1e8449; }
.r-yesil   { background: #eafaf1; color: #1e8449; }
.r-gri     { background: #eef1f4; color: #566573; }

audio { width: 100%; height: 32px; margin: 6px 0 8px; display: block; }
.metin { font-family: ui-monospace, Menlo, monospace; font-size: 11px;
         background: #f7f9fa; border: 1px solid #e6ebef; border-radius: 4px;
         padding: 6px 8px; margin: 3px 0; white-space: pre-wrap; word-break: break-word; }
.metin b { color: #62707f; font-family: inherit; }
.ekle { background: #d5f5e3; color: #145a32; }
.sil  { background: #fadbd8; color: #922b21; }
.neden { margin: 7px 0 0; padding-left: 17px; font-size: 12px; color: #3d4a57; }
.neden li { margin-bottom: 3px; }

.filtre { display: flex; gap: 6px; flex-wrap: wrap; margin: 16px 0 6px; }
.fbtn { font: inherit; font-size: 12px; padding: 5px 12px; border-radius: 14px;
        border: 1px solid #c8d2db; background: #fff; color: #4a5764; cursor: pointer; }
.fbtn:hover { background: #eef2f6; }
.fbtn.aktif { background: #0d2b45; border-color: #0d2b45; color: #fff; font-weight: 600; }
.kat-blok.gizli { display: none; }

.sozluk td:first-child { font-family: ui-monospace, Menlo, monospace;
                         font-weight: 600; white-space: nowrap; }
.uyari { background: #fef9e7; border: 1px solid #f4d03f; border-radius: 6px;
         padding: 12px 16px; font-size: 13px; margin-bottom: 18px; }
.tilde { color: #95a5a6; }
.cfer-banner { background: linear-gradient(135deg, #0d2b45, #1a3a5c); color: #fff;
               border-radius: 10px; padding: 22px 26px; margin-bottom: 20px; }
.cfer-banner .baslik { font-size: 12px; text-transform: uppercase; letter-spacing: 1px;
                       color: #9db8d0; margin-bottom: 10px; }
.cfer-banner .satir { display: flex; gap: 34px; align-items: baseline; flex-wrap: wrap; }
.cfer-banner .uret { display: flex; align-items: baseline; gap: 8px; }
.cfer-banner .buyuk { font-size: 40px; font-weight: 700; font-variant-numeric: tabular-nums; }
.cfer-banner .ad { font-size: 14px; color: #c5d5e5; }
.cfer-banner .kucuk { font-size: 13px; color: #9db8d0; }
.cfer-banner .yorum { margin-top: 12px; font-size: 13px; color: #d5e0ea;
                      border-top: 1px solid #2c4a68; padding-top: 10px; }
.kirilim { width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #dbe2e8; border-radius: 8px; overflow: hidden;
           font-size: 13px; margin-bottom: 20px; }
.kirilim th { background: #eef2f6; text-align: left; padding: 9px 12px; font-size: 11px;
              text-transform: uppercase; letter-spacing: .4px; color: #4a5764; }
.kirilim td { padding: 9px 12px; border-top: 1px solid #eef1f4; }
.kirilim td.num { text-align: right; font-variant-numeric: tabular-nums; }
.kirilim tr.k100 td { background: #fdeceb; }
.kirilim tr.k100 td:first-child { font-weight: 700; color: #a93226; }
.kirilim tr.k0 td:first-child { color: #1e8449; }
.kirilim tr.tikla { cursor: pointer; }
.kirilim tr.tikla:hover td { background: #eef2f6; }
.kirilim .bar { display: inline-block; height: 8px; border-radius: 4px;
                background: #c0392b; vertical-align: middle; margin-left: 6px; }
@media (max-width: 900px) { .cift-govde { grid-template-columns: 1fr; }
                            .yan + .yan { border-top: 1px solid #eef1f4; box-shadow: none; } }
"""


def esc(s):
    return html.escape(str(s or ""))


def cfer_banner_html(da, db, ad_a, ad_b, esik):
    ta, ha, ca, kat_a, _ = cfer_hesapla(da, esik)
    h = ['<div class="cfer-banner">']
    h.append('<div class="baslik">Kritik Alan Hata Orani — CFER</div>')
    h.append('<div class="satir">')
    h.append(f'<div class="uret"><span class="buyuk">%{ca*100:.0f}</span>'
             f'<span class="ad">{esc(ad_a)}</span>'
             f'<span class="kucuk">({ha}/{ta})</span></div>')
    if db is not None:
        tb, hb, cb, kat_b, _ = cfer_hesapla(db, esik)
        h.append(f'<div class="uret"><span class="buyuk">%{cb*100:.0f}</span>'
                 f'<span class="ad">{esc(ad_b)}</span>'
                 f'<span class="kucuk">({hb}/{tb})</span></div>')
        h.append('</div>')
        if abs(ca - cb) < 0.01:
            h.append('<div class="yorum">Model degisti, kritik alan hata orani '
                     'DEGISMEDI. Sorun model kalitesinde degil, metin normalizasyonunda. '
                     'Daha iyi TTS almak bu orani dusurmuyor.</div>')
        else:
            iyi = ad_b if cb < ca else ad_a
            h.append(f'<div class="yorum">{esc(iyi)} kritik alanlarda daha iyi. '
                     f'Fark: {abs(ca-cb)*100:.0f} puan.</div>')
    else:
        h.append('</div>')
    h.append('</div>')
    return "".join(h)


def kirilim_tablo_html(da, db, ad_a, ad_b, esik):
    _, _, _, kat_a, _ = cfer_hesapla(da, esik)
    kat_b = cfer_hesapla(db, esik)[3] if db is not None else None
    kats = sorted(kat_a.keys())
    h = ['<table class="kirilim">']
    if db is not None:
        h.append(f'<tr><th>kategori</th><th class="num">{esc(ad_a)}</th>'
                 f'<th class="num">{esc(ad_b)}</th><th>durum</th></tr>')
    else:
        h.append('<tr><th>kategori</th><th class="num">hata</th><th>durum</th></tr>')
    for k in kats:
        ta, ha = kat_a[k]
        oa = ha / ta * 100 if ta else 0
        cls = "k100" if oa >= 100 else ("k0" if oa == 0 else "")
        durum = "TAMAMEN HATALI" if oa >= 100 else ("temiz" if oa == 0 else "kismi")
        bar = f'<span class="bar" style="width:{oa:.0f}px"></span>' if oa > 0 else ""
        if db is not None:
            tb, hb = kat_b.get(k, [0, 0])
            ob = hb / tb * 100 if tb else 0
            h.append(f'<tr class="{cls} tikla" data-git="{esc(k)}"><td>{esc(k)} &rsaquo;</td>'
                     f'<td class="num">{ha}/{ta} (%{oa:.0f})</td>'
                     f'<td class="num">{hb}/{tb} (%{ob:.0f})</td>'
                     f'<td>{durum}{bar}</td></tr>')
        else:
            h.append(f'<tr class="{cls} tikla" data-git="{esc(k)}"><td>{esc(k)} &rsaquo;</td>'
                     f'<td class="num">{ha}/{ta} (%{oa:.0f})</td>'
                     f'<td>{durum}{bar}</td></tr>')
    h.append('</table>')
    return "".join(h)


def diff_html(ref_n, hyp_n):
    sm = difflib.SequenceMatcher(None, ref_n or "", hyp_n or "")
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(esc(ref_n[i1:i2]))
        elif op == "delete":
            out.append(f'<span class="sil">{esc(ref_n[i1:i2])}</span>')
        elif op == "insert":
            out.append(f'<span class="ekle">{esc(hyp_n[j1:j2])}</span>')
        elif op == "replace":
            out.append(f'<span class="sil">{esc(ref_n[i1:i2])}</span>'
                       f'<span class="ekle">{esc(hyp_n[j1:j2])}</span>')
    return "".join(out)


def renk(kodlar):
    for k in ("MASKELEME", "CIFT_TETIK", "GERCEK_HATA"):
        if k in kodlar:
            return "kirmizi"
    if "SINIRDA" in kodlar:
        return "sari"
    if "INSAN" in kodlar or "CER_ANLAMSIZ" in kodlar:
        return "mavi"
    return "ok"


def yan_html(fname, v, esik, ad, ses_dizin):
    """Tek ureticinin sutunu."""
    if not v:
        return f'<div class="yan"><div class="uretici">{esc(ad)}</div>(veri yok)</div>'

    kodlar, satirlar = gerekce_uret(v, esik)
    r = renk(kodlar)
    mos = v.get("mos")
    mos_s = f"{mos:.2f}" if mos is not None else "-"

    h = [f'<div class="yan {r}">']
    h.append(f'<div class="uretici">{esc(ad)}</div>')
    if ses_dizin:
        h.append(f'<audio controls preload="none" src="{esc(ses_dizin)}/{esc(fname)}"></audio>')
    h.append("".join(
        f'<span class="rozet r-{KOD_SOZLUK.get(k, ("", "gri"))[1]}">{k}</span>' for k in kodlar))
    h.append(f'<div class="metin"><b>CER</b> {v["cer"]*100:.1f}   '
             f'<b>ham</b> {(v.get("cer_ham") or 0)*100:.1f}   '
             f'<b>MOS</b> {mos_s}')
    if v.get("w2v2_cer") is not None:
        h.append(f'   <b>w2v2</b> {v["w2v2_cer"]*100:.1f}   '
                 f'<b>ayrışma</b> +{v["ayrisma"]*100:.0f}')
    h.append('</div>')
    h.append(f'<div class="metin"><b>WHIS</b> {esc(v.get("whisper_n",""))}</div>')
    if v.get("w2v2_n"):
        h.append(f'<div class="metin"><b>W2V2</b> {esc(v.get("w2v2_n"))}</div>')
    h.append(f'<div class="metin"><b>DIFF</b> {diff_html(v.get("ref_n"), v.get("whisper_n"))}</div>')
    h.append('<ul class="neden">')
    for s in satirlar:
        h.append(f'<li>{esc(s)}</li>')
    h.append('</ul></div>')
    return "".join(h)


def cift_kart(fname, va, vb, esik, ad_a, ad_b, ses_a, ses_b):
    """Bir cumle, iki uretici yan yana."""
    ref = (va or vb or {}).get("ref", "")
    kat = (va or vb or {}).get("kategori", "?")
    flags = (va or vb or {}).get("flags") or []
    ref_n = (va or vb or {}).get("ref_n", "")

    h = ['<div class="cift">']
    h.append('<div class="cift-bas">')
    h.append(f'<span class="ad">{esc(fname)}</span> '
             f'<span class="rozet r-gri">{esc(kat)}</span>')
    for f in flags:
        h.append(f'<span class="rozet r-gri">{esc(f)}</span>')
    h.append(f'<div class="cumle">{esc(ref)}</div>')
    h.append(f'<div class="metin"><b>REF</b> {esc(ref_n)}</div>')
    h.append('</div>')
    h.append('<div class="cift-govde">')
    h.append(yan_html(fname, va, esik, ad_a, ses_a))
    if vb is not None:
        h.append(yan_html(fname, vb, esik, ad_b, ses_b))
    h.append('</div></div>')
    return "".join(h)


def ozet_kutulari(d, esik):
    kor = insan = kritik = 0
    norm_toplam = 0.0
    for v in d.values():
        kodlar, _ = gerekce_uret(v, esik)
        if "MASKELEME" in kodlar or "CIFT_TETIK" in kodlar:
            kor += 1
        if "NORM_KAZANC" in kodlar:
            norm_toplam += (v.get("cer_ham", 0) - v.get("cer", 0)) * 100
        if "INSAN" in kodlar:
            insan += 1
        if "KRITIK" in kodlar:
            kritik += 1
    toplam_alan, hatali_alan, cfer, _, _ = cfer_hesapla(d, esik)
    return [(len(d), "cümle"), (kor, "kör nokta"), (insan, "insana giden"),
            (f"%{cfer*100:.0f}", "CFER (kritik alan hata)"),
            (f"{hatali_alan}/{toplam_alan}", "hatalı kritik alan"),
            (f"{norm_toplam:.0f}", "puan sahte hata silindi")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_a")
    ap.add_argument("json_b", nargs="?")
    ap.add_argument("--ad-a", default="A")
    ap.add_argument("--ad-b", default="B")
    ap.add_argument("--ses-a", help="A ureticisinin wav klasoru")
    ap.add_argument("--ses-b", help="B ureticisinin wav klasoru")
    ap.add_argument("--esik", type=float, default=ESIK_AYRISMA)
    ap.add_argument("-o", "--cikti", default="rapor.html")
    args = ap.parse_args()

    da = json.load(open(args.json_a, encoding="utf-8"))
    db = json.load(open(args.json_b, encoding="utf-8")) if args.json_b else None

    H = ['<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>Türkçe TTS Değerlendirme Raporu</title>',
         f'<style>{CSS}</style></head><body><div class="wrap">']

    baslik = f"{args.ad_a} vs {args.ad_b}" if db else args.ad_a
    H.append('<h1>Türkçe TTS Değerlendirme Raporu</h1>')
    H.append(f'<div class="sub">{esc(baslik)} · {len(da)} cümle · '
             f'faster-whisper + wav2vec2 + UTMOSv2 · ayrışma eşiği {args.esik*100:.0f} puan</div>')

    H.append(cfer_banner_html(da, db, args.ad_a, args.ad_b, args.esik))
    H.append('<h2>CFER kategori kırılımı</h2>')
    H.append(kirilim_tablo_html(da, db, args.ad_a, args.ad_b, args.esik))

    H.append('<div class="uyari"><b>Bu rapor nasıl okunur:</b> Tek bir ortalama sayıya bakma. '
             'KÖR NOKTA (MASKELEME, CIFT_TETIK) işaretli satırlarda CER sahtedir, Whisper hatayı '
             'düzeltip gizlemiştir. Homograf satırlarında CER hiçbir şey ölçmez. MOS farkları '
             '0.3 puanın altındaysa ölçüm gürültüsüdür, anlamsızdır.</div>')

    H.append(f'<h2>{esc(args.ad_a)} özeti</h2><div class="ozet">')
    for n, l in ozet_kutulari(da, args.esik):
        H.append(f'<div class="kutu"><div class="n">{n}</div><div class="l">{l}</div></div>')
    H.append('</div>')

    if db:
        H.append(f'<h2>{esc(args.ad_b)} özeti</h2><div class="ozet">')
        for n, l in ozet_kutulari(db, args.esik):
            H.append(f'<div class="kutu"><div class="n">{n}</div><div class="l">{l}</div></div>')
        H.append('</div>')

        H.append('<h2>Yan yana tablo</h2><table>')
        H.append(f'<tr><th>dosya</th><th>kategori</th><th class="num">CER {esc(args.ad_a)}</th>'
                 f'<th class="num">CER {esc(args.ad_b)}</th><th class="num">MOS {esc(args.ad_a)}</th>'
                 f'<th class="num">MOS {esc(args.ad_b)}</th><th>MOS farkı</th>'
                 f'<th>ayrışma A/B</th></tr>')
        for f in sorted(da):
            va, vb = da[f], db.get(f, {})
            ma, mb = va.get("mos"), vb.get("mos")
            if ma is not None and mb is not None:
                fark = mb - ma
                fs = ('<span class="tilde">~ ayırt edilemiyor</span>'
                      if abs(fark) < MOS_ESIK else f'{fark:+.2f}')
            else:
                fs = "-"
            aya = f'+{va["ayrisma"]*100:.0f}' if va.get("ayrisma") is not None else "-"
            ayb = f'+{vb["ayrisma"]*100:.0f}' if vb.get("ayrisma") is not None else "-"
            H.append(f'<tr><td>{esc(f)}</td><td>{esc(va.get("kategori"))}</td>'
                     f'<td class="num">{va["cer"]*100:.1f}</td>'
                     f'<td class="num">{vb.get("cer",0)*100:.1f}</td>'
                     f'<td class="num">{ma:.2f}</td><td class="num">{mb:.2f}</td>'
                     f'<td>{fs}</td><td>{aya} / {ayb}</td></tr>')
        H.append('</table>')

        oa = sum(v["mos"] for v in da.values() if v.get("mos")) / len(da)
        ob = sum(v["mos"] for v in db.values() if v.get("mos")) / len(db)
        dm = ob - oa
        yorum = ("Fark ölçüm gürültüsünün altında. UTMOSv2 bu iki sistemi ayırt edemiyor. "
                 "Bu 'biri daha doğal' demek değil, 'araç göremiyor' demek."
                 if abs(dm) < MOS_ESIK else "Fark 0.3 eşiğinin üstünde, anlamlı olabilir.")
        H.append(f'<div class="uyari"><b>MOS ortalaması:</b> {args.ad_a} {oa:.2f} · '
                 f'{args.ad_b} {ob:.2f} · fark {dm:+.2f}. {yorum}</div>')

    # --- Eslestirilmis kartlar ---
    H.append('<h2>Cümle bazlı detay</h2>')
    kats = []
    for f in sorted(da):
        k = da[f].get("kategori", "?")
        if k not in kats:
            kats.append(k)

    H.append('<div class="filtre">')
    H.append('<button class="fbtn aktif" data-k="__hepsi__">hepsi</button>')
    for k in kats:
        H.append(f'<button class="fbtn" data-k="{esc(k)}">{esc(k)}</button>')
    H.append('</div>')

    for k in kats:
        H.append(f'<div class="kat-blok" data-kat="{esc(k)}">')
        H.append(f'<h3 class="kat">{esc(k)}</h3>')
        for f in sorted(da):
            if da[f].get("kategori") == k:
                vb = db.get(f) if db else None
                H.append(cift_kart(f, da[f], vb, args.esik,
                                   args.ad_a, args.ad_b, args.ses_a, args.ses_b))
        H.append('</div>')

    H.append('<h2>Kod sözlüğü</h2><table class="sozluk">')
    for k, (aciklama, _) in KOD_SOZLUK.items():
        H.append(f'<tr><td>{k}</td><td>{esc(aciklama)}</td></tr>')
    H.append('</table>')

    H.append('<h2>Bayrak sözlüğü</h2><table class="sozluk">')
    for k, aciklama in BAYRAK_SOZLUK.items():
        H.append(f'<tr><td>{k}</td><td>{esc(aciklama)}</td></tr>')
    H.append('</table>')

    H.append('''<script>
document.querySelectorAll(".kirilim tr.tikla").forEach(function(row){
  row.addEventListener("click", function(){
    var k = row.dataset.git;
    var btn = document.querySelector('.fbtn[data-k="' + k + '"]');
    if (btn) {
      btn.click();
      var blok = document.querySelector('.kat-blok[data-kat="' + k + '"]');
      if (blok) blok.scrollIntoView({behavior: "smooth", block: "start"});
    }
  });
});
document.querySelectorAll(".fbtn").forEach(function(b){
  b.addEventListener("click", function(){
    document.querySelectorAll(".fbtn").forEach(function(x){ x.classList.remove("aktif"); });
    b.classList.add("aktif");
    var sec = b.dataset.k;
    document.querySelectorAll(".kat-blok").forEach(function(blok){
      var goster = (sec === "__hepsi__") || (blok.dataset.kat === sec);
      blok.classList.toggle("gizli", !goster);
    });
  });
});
</script>''')

    H.append('</div></body></html>')

    with open(args.cikti, "w", encoding="utf-8") as f:
        f.write("".join(H))
    print(f"[rapor] yazildi -> {args.cikti}")


if __name__ == "__main__":
    main()
