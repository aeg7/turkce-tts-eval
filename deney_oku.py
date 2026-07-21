#!/usr/bin/env python3
"""
deney_oku.py — Normalizasyon deneyini uc kosu uzerinden okur.
A (baseline, norm=False), K (kontrol, norm=False), N (deney, norm=True)

A vs K = modelin gurultusu (ayni ayar)
A vs N = normalizasyonun etkisi
Etki gurultuden buyukse gercek.
"""
import json

A = json.load(open("voxcpm.json"))
K = json.load(open("voxcpm_k2.json"))
N = json.load(open("voxcpm_norm.json"))

def cer(d, f):  return (d.get(f, {}).get("cer") or 0) * 100
def ayr(d, f):
    v = d.get(f, {}).get("ayrisma")
    return v * 100 if v is not None else None
def kat(f):     return A.get(f, {}).get("kategori", "?")

print(f"{'dosya':<14} {'kat':<12} {'CER A':>6} {'CER K':>6} {'CER N':>6}   "
      f"{'ayr A':>6} {'ayr K':>6} {'ayr N':>6}   not")
print("-" * 110)

for f in sorted(A):
    ca, ck, cn = cer(A, f), cer(K, f), cer(N, f)
    aa, ak, an = ayr(A, f), ayr(K, f), ayr(N, f)

    # A ile K arasindaki oynama = gurultu
    gurultu_cer = abs(ca - ck)
    # A ile N arasindaki oynama = ham etki
    etki_cer = abs(ca - cn)

    notlar = []
    if etki_cer > gurultu_cer + 5:
        yon = "duzeldi" if cn < ca else "KOTULESTI"
        notlar.append(f"norm {yon} ({ca:.0f}->{cn:.0f}, gurultu {gurultu_cer:.0f})")
    if gurultu_cer > 5:
        notlar.append(f"model oynak (A/K farki {gurultu_cer:.0f})")

    def s(x): return f"{x:>6.1f}" if x is not None else "     -"
    def sa(x): return f"{x:>+6.0f}" if x is not None else "     -"

    print(f"{f:<14} {kat(f):<12} {ca:>6.1f} {ck:>6.1f} {cn:>6.1f}   "
          f"{sa(aa)} {sa(ak)} {sa(an)}   {'; '.join(notlar)}")

# Ozet
def kor(d): return sum(1 for v in d.values() if v.get("ayrisma") and v["ayrisma"] > 0.10)
def ort_cer(d): return sum((v.get("cer") or 0) for v in d.values())/len(d)*100

print("-" * 110)
print(f"kor nokta:   A={kor(A)}  K={kor(K)}  N={kor(N)}")
print(f"ort CER:     A={ort_cer(A):.1f}  K={ort_cer(K):.1f}  N={ort_cer(N):.1f}")
print()
print("YORUM:")
print(f"  A vs K (ayni ayar) = modelin gurultusu. Kor nokta {kor(A)} vs {kor(K)}.")
print(f"  A vs N (norm acik) = normalizasyonun etkisi.")
print(f"  Bir satirdaki N degisimi, o satirin A/K oynamasindan buyukse GERCEK.")
