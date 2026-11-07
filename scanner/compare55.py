"""検証55：今週（2026-10-29〜11-05）は日経がじわじわ−5.5%下げる間、広い信号（6本）が0〜1本で、鳴ったのは−6%の急落日（11/6）の後だった。
SOXの5日騰落（前夜まで）を7本目の信号に足すと、急落40件（検証28）の損失が前半(〜2011)・後半(2012〜)とも減るか。
比較の基準は今の方針C（維持20日＋社債HYG÷IEF 20日≤−2%で0%）。先読みなし（SOXは前夜まで、判定は引け後→翌日反映）。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, st, E, mid, sox = G["cal"], G["score"], G["run"], G["st"], G["E"], G["mid"], G["sox"]
x = yf.download(["HYG", "IEF"], start="2007-01-01", auto_adjust=True, progress=False)["Close"].dropna(); x.index = pd.to_datetime(x.index).tz_localize(None)
q = (x["HYG"] / x["IEF"]).pct_change(20)
idx = cal.searchsorted(q.index, side="right"); m = idx < len(cal); q = pd.Series(q.values[m], index=cal[idx[m]]); q = q[~q.index.duplicated(keep="last")].reindex(cal).ffill()
cap = (q <= -0.02).fillna(False).values
sox5 = (sox.reindex(cal).ffill().pct_change(5) * 100).shift(1)
def pol(sc, hold=20):
    sc = np.asarray(sc); e = np.ones(len(sc))
    for i in range(len(sc)):
        sh = sc[max(0, i - hold + 1):i + 1].max(); v = 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
        if cap[i]: v = 0.0
        e[i] = v
    return pd.Series(e, index=cal)
def half(r):
    eq = (1 + r).cumprod().values; out = {}
    for nm, sel in (("前半", lambda a: cal[a] < mid), ("後半", lambda a: cal[a] >= mid)):
        L = [eq[tr] / eq[a] - 1 for a, tr in E if sel(a)]; out[nm] = (len(L), np.mean(L) * 100, min(L) * 100)
    return out
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); h = half(r)
    print(f"{nm} | 前半 {a1:+.0f}%・最大下落{d1:.0f}%・急落{h['前半'][0]}件 平均{h['前半'][1]:.1f}% 最悪{h['前半'][2]:.1f}% | 後半 {a2:+.0f}%・{d2:.0f}%・急落{h['後半'][0]}件 平均{h['後半'][1]:.1f}% 最悪{h['後半'][2]:.1f}% | 持ち高{e.mean()*100:.0f}%")
    return a1, d1, a2, d2, h
b = show("基準 方針C（維持20日＋社債−2%で0%）", pol(sc0))
for th in (-8, -10, -15):
    f = (sox5 <= th).fillna(False).astype(int)
    for w in (1, 3):
        nm = f"＋SOX5日≤{th}%（{w}本扱い）"; t = show(nm, pol(np.asarray(sc0) + w * f.values))
        ok = all(t[4][k][1] > b[4][k][1] + 0.3 and t[4][k][2] >= b[4][k][2] for k in ("前半", "後半")) and t[0] >= b[0] - 15 and t[2] >= b[2] - 15
        print(f"   → {'予測出来た（前半・後半とも急落の損失が減り、上昇の取り逃しも小さい）' if ok else '予測出来なかった（前半・後半の両方では改善しない、または取り逃しが大きい）'}")
        print("   今週の点灯日:", [str(d.date()) for d in cal[-8:] if f.loc[d] == 1])
show("持ちっぱなし", pd.Series(1.0, index=cal))
print("SOX5日（前夜まで）直近:", {str(d.date()): round(float(v), 1) for d, v in sox5.tail(8).items()})
