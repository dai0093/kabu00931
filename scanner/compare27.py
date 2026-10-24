"""検証27：「どの資産を買ってもマイナス」（8資産が同時に下落）は、その後の暴落を予測したか。
ROBOPROの8資産（米国株SPY・先進国EFA・新興国株EEM・米国債AGG・ハイイールドHYG・新興国債EMB・米国不動産VNQ・金GLD）の直近21営業日リターンで、
下落している資産の本数を数える。信号＝8本中7本以上が下落／8本すべて下落。
結果：日経が10営業日内に-8%以上（検証26と同じ）／S&P500が60営業日内に-10%以上の最大下落。前半(〜2011)・後半(2012〜)で分けて、基準の発生率と比べる。"""
import warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
T = ["SPY", "EFA", "EEM", "AGG", "HYG", "EMB", "VNQ", "GLD"]
def get(t):
    x = yf.download(t, start="2003-01-01", auto_adjust=True, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None); return x["Close"].dropna()
A = pd.DataFrame({t: get(t) for t in T}).dropna()
nk = get("^N225"); sp = get("^GSPC")
cal = A.index
r21 = A.pct_change(21) * 100
neg = (r21 < 0).sum(axis=1)
nkc = nk.reindex(cal.union(nk.index)).ffill().reindex(cal); spc = sp.reindex(cal.union(sp.index)).ffill().reindex(cal)
def fmin(s, h):
    v = s.values; n = len(v); o = np.full(n, np.nan)
    for i in range(n - h): o[i] = v[i + 1:i + h + 1].min() / v[i] - 1
    return pd.Series(o, index=s.index)
ev_nk = fmin(nkc, 10) <= -0.08; ev_sp = fmin(spc, 60) <= -0.10
valid = fmin(nkc, 10).notna() & fmin(spc, 60).notna() & (neg.notna()) & r21.notna().all(axis=1)
mid = pd.Timestamp("2012-01-01"); h1 = valid & (cal < mid); h2 = valid & (cal >= mid)
print(f"期間 {cal[0].date()}〜{cal[-1].date()}  日数{int(valid.sum())}")
b = {}
for lab, h in (("前半", h1), ("後半", h2)):
    b[lab] = (ev_nk[h].mean(), ev_sp[h].mean()); print(f"基準({lab}): 日経10日内-8%の発生率{b[lab][0]*100:.1f}%  S&P60日内-10%の発生率{b[lab][1]*100:.1f}%")
def rep(nm, s):
    s = s & valid
    for lab, h in (("前半", h1), ("後半", h2)):
        m = s & h; n = int(m.sum())
        if n == 0: print(f"{nm} {lab}: 0日"); continue
        a, c = ev_nk[m].mean(), ev_sp[m].mean()
        print(f"{nm} {lab}: {n}日  日経急落{a*100:.0f}%(×{a/max(b[lab][0],1e-9):.1f}) / S&P60日内-10%{c*100:.0f}%(×{c/max(b[lab][1],1e-9):.1f})")
for k in (8, 7, 6): rep(f"8資産中{k}本以上が21日下落", neg >= k)
both = (r21["SPY"] < 0) & (r21["AGG"] < 0); rep("株(SPY)と債券(AGG)が同時に21日下落", both)
rep("8本以上かつ金も下落(逃げ場なし)", (neg >= 8))
print("\n直近:", cal[-1].date(), "下落資産数", int(neg.iloc[-1]), {t: round(float(r21[t].iloc[-1]), 1) for t in T})
last = neg[neg >= 7]; print("7本以上の直近日:", [str(d.date()) for d in last.index[-6:]])
yrs = {y: int(((neg >= 7) & (cal.year == y)).sum()) for y in sorted(set(cal.year))}; print("7本以上の年別日数:", yrs)
