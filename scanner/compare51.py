"""検証51：日経の急落局面（10営業日以内に−8%、検証28の40件と同じ定義）の間、何を持っていれば利益が出たか。前半/後半。
円建てで評価（ドル資産はドル円の変化を含む）。空売りなし。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, mid, nk = G["cal"], G["mid"], G["nk"]
def dl(t):
    x = yf.download(t, start="1995-01-01", auto_adjust=True, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x.reindex(cal, method="ffill")
jpy = dl("JPY=X")
A = {"現金（円）": None, "金（円建て）": dl("GC=F") * jpy, "米国債7-10年 IEF（円建て）": dl("IEF") * jpy, "米国長期債 TLT（円建て）": dl("TLT") * jpy,
     "米ドル（円→ドル）": jpy, "日本国債ETF 2510": dl("2510.T"), "スイスフラン（円建て）": dl("CHFJPY=X"), "銀（円建て）": dl("SI=F") * jpy, "日本株 高配当・ディフェンシブ 1489": dl("1489.T")}
nkc = nk.reindex(cal).ffill()
# 急落：10営業日先までの最安が−8%以下となる日の、その10日間
f10 = pd.Series([(nkc.iloc[i+1:i+11].min()/nkc.iloc[i]-1) if i+11 <= len(nkc) else np.nan for i in range(len(nkc))], index=cal)
ev = []
for d in cal[(f10 <= -0.08).values]:
    if not ev or (d - ev[-1]).days > 40: ev.append(d)
print(f"急落 {len(ev)}件（前半{sum(d<mid for d in ev)}・後半{sum(d>=mid for d in ev)}）")
for nm, s in A.items():
    out = []
    for half in ("前半", "後半"):
        rr = []
        for d in ev:
            if (d < mid) != (half == "前半"): continue
            i = cal.get_loc(d); j = min(i + 10, len(cal) - 1)
            if s is None: rr.append(0.0); continue
            if pd.isna(s.iloc[i]) or pd.isna(s.iloc[j]): continue
            rr.append(s.iloc[j] / s.iloc[i] - 1)
        rr = pd.Series(rr) * 100
        out.append(f"{len(rr)}件 平均{rr.mean():+.1f}% 上がった割合{(rr>0).mean()*100:.0f}% 最悪{rr.min():+.1f}%" if len(rr) else "データなし")
    print(f"{nm} | 前半 {out[0]} | 後半 {out[1]}")
r = []
for d in ev:
    i = cal.get_loc(d); j = min(i + 10, len(cal) - 1); r.append((d < mid, nkc.iloc[j] / nkc.iloc[i] - 1))
print("参考：日経 | 前半 平均", round(np.mean([x for h, x in r if h]) * 100, 1), "% | 後半 平均", round(np.mean([x for h, x in r if not h]) * 100, 1), "%")
