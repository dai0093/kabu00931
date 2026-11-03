"""検証46：取れない指標の代替（ロジックツリー用）。点灯後60営業日以内に日経−10%／20営業日以内に−5%の割合を前半/後半で、全日と比べる（1.3倍以上が両方で＝予測出来た）。
IG OAS代替：LQD÷IEF 20日 ／ NFCI代替：金融ストレス合成（VIX・社債・米銀のzスコア平均） ／ 私募信用代替：私募信用運用会社株（BX・APO・KKR・ARES）中央値5日
日経先物代替：日経1日 ／ SOX下落：SOX60日高値比"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, adj=True):
    x = yf.download(t, start="1995-01-01", auto_adjust=adj, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225", False); cal = nk.index; mid = pd.Timestamp("2012-01-01")
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
m60 = pd.Series([(nk.iloc[i:i+61].min()/nk.iloc[i]-1) if i+61 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
m20 = pd.Series([(nk.iloc[i:i+21].min()/nk.iloc[i]-1) if i+21 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
lq = prev((dl("LQD") / dl("IEF")).pct_change(20)); hy = prev((dl("HYG") / dl("IEF")).pct_change(20))
vix = prev(dl("^VIX", False)); bk = prev(dl("^BKX", False).pct_change(20))
z = lambda s: (s - s.rolling(500, min_periods=250).mean()) / s.rolling(500, min_periods=250).std()
fs = (z(vix) + z(-hy) + z(-bk)) / 3
pcs = pd.concat([dl(t, False).pct_change(5) for t in ("BX", "APO", "KKR", "ARES")], axis=1).median(axis=1); pc = prev(pcs)
sx = dl("^SOX", False); sdd = prev(sx / sx.rolling(60).max() - 1)
r1 = nk.pct_change()
C = {"IG代替 LQD÷IEF 20日≤−1%": lq <= -0.01, "IG代替 LQD÷IEF 20日≤−1.5%": lq <= -0.015, "IG代替 LQD÷IEF 20日≤−2%": lq <= -0.02,
     "HY代替 HYG÷IEF 20日≤−1%": hy <= -0.01, "HY代替 HYG÷IEF 20日≤−2%": hy <= -0.02,
     "NFCI代替 金融ストレス合成≥1.0": fs >= 1.0, "NFCI代替 金融ストレス合成≥1.5": fs >= 1.5, "NFCI代替 金融ストレス合成≥2.0": fs >= 2.0,
     "私募信用代替 運用会社株5日≤−8%": pc <= -0.08, "私募信用代替 運用会社株5日≤−5%": pc <= -0.05,
     "日経先物代替 日経1日≤−2.5%": r1 <= -0.025, "日経先物代替 日経1日≤−1.5%": r1 <= -0.015,
     "SOX下落 60日高値比≤−20%": sdd <= -0.20, "SOX下落 60日高値比≤−10%": sdd <= -0.10}
H = {"前半": cal < mid, "後半": cal >= mid}
B = {k: ((m60[m] <= -.1).mean(), (m20[m] <= -.05).mean()) for k, m in H.items()}
print(f"全日：前半 60日−10% {B['前半'][0]*100:.0f}% 20日−5% {B['前半'][1]*100:.0f}% ／ 後半 {B['後半'][0]*100:.0f}% {B['後半'][1]*100:.0f}%")
for nm, s in C.items():
    s = s.reindex(cal).fillna(False).astype(bool); out = []; ok = True
    for k, m in H.items():
        n = int((s & m).sum())
        if n < 30: out.append(f"{n}日"); ok = False; continue
        a, b = (m60[s & m].dropna() <= -.1).mean(), (m20[s & m].dropna() <= -.05).mean(); out.append(f"{n}日 {a*100:.0f}%/{b*100:.0f}%")
        if not (a >= 1.3 * B[k][0] and b >= 1.3 * B[k][1]): ok = False
    print(f"{nm} | 前半 {out[0]} | 後半 {out[1]} | {'予測出来た' if ok else '予測出来なかった'} | 今 {'点灯' if s.iloc[-1] else '消灯'}")
print("今の値: LQD20日", round(float(lq.iloc[-1])*100, 2), "HYG20日", round(float(hy.iloc[-1])*100, 2), "合成", round(float(fs.iloc[-1]), 2), "運用会社5日", round(float(pc.iloc[-1])*100, 2), "SOX60日比", round(float(sdd.iloc[-1])*100, 1))
