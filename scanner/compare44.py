"""検証44：①方針Cの『10営業日で戻す』を20・40日に延ばす ②社債（HYG÷IEF、配当込み）20日≤−2%の間は上限をかける。前半/後半・急落40件で比較。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, st, epi, mid = G["cal"], np.asarray(G["score"]), G["run"], G["st"], G["epi"], G["mid"]
x = yf.download(["HYG", "IEF"], start="2007-01-01", auto_adjust=True, progress=False)["Close"].dropna(); x.index = pd.to_datetime(x.index).tz_localize(None)
q = (x["HYG"] / x["IEF"]).pct_change(20)
idx = cal.searchsorted(q.index, side="right"); m = idx < len(cal); q = pd.Series(q.values[m], index=cal[idx[m]]); q = q[~q.index.duplicated(keep="last")].reindex(cal).ffill()
def pol(hold=10, cap=None, lv=1.0):
    e = np.ones(len(sc0))
    for i in range(len(sc0)):
        sh = sc0[max(0, i - hold + 1):i + 1].max(); v = 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
        if cap is not None and cap[i]: v = min(v, lv)
        e[i] = v
    return pd.Series(e, index=cal)
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); mm, md, w = epi(r)
    print(f"{nm} | 前半 {a1:+.0f}%・最大下落{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{mm:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
for h in (10, 20, 40, 60): show(f"C 維持{h}日", pol(h))
for th in (-0.02, -0.03):
    c = (q <= th).fillna(False).values
    for lv in (0.5, 0.25, 0.0):
        for h in (10, 20): show(f"C 維持{h}日＋社債20日≤{int(th*100)}%で上限{int(lv*100)}%", pol(h, c, lv))
show("持ちっぱなし", pd.Series(1.0, index=cal))
print("今の社債20日:", round(float(q.iloc[-1]) * 100, 2), "%", cal[-1].date())
for nm_, a, b in (("リーマン", "2008-09-01", "2008-12-31"), ("コロナ", "2020-02-01", "2020-04-30"), ("2026/10〜", "2026-10-01", "2026-12-31")):
    f = lambda e: st(run(e), a, b)
    print(nm_, "持ちっぱなし", [round(v) for v in f(pd.Series(1.0, index=cal))], "C", [round(v) for v in f(pol())], "C維持20日+社債-2%上限25%", [round(v) for v in f(pol(20, (q <= -0.02).fillna(False).values, .25))])
