"""検証80：深い下落の中で『信号が20日消えたら戻す』は早すぎないか。（2026-11-21 週次点検、結果を見る前に条件を固定）
基準：今の方針C（信号の最大本数で 1本50%/2本25%/3本以上0%、維持20営業日、社債HYG÷IEF 20日≤−2%の間は0%）。
深い下落＝日経の終値が250営業日の高値から−20%以下（当日引けで判定、翌日から反映）。
V1 深い下落中は維持を40日に延長　V2 深い下落中は上限50%　V3 深い下落中は日経が25日線の上に戻るまで0%
採用の条件（事前に固定）：前半(〜2011)・後半(2012〜)の両方で、最大下落が1pt以上小さく、かつ累積が基準−10pt以内。さらに急落40件の最悪が悪化しないこと。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, st, epi, mid, nk = G["cal"], np.asarray(G["score"]), G["run"], G["st"], G["epi"], G["mid"], G["nk"]
x = yf.download(["HYG", "IEF"], start="2007-01-01", auto_adjust=True, progress=False)["Close"].dropna(); x.index = pd.to_datetime(x.index).tz_localize(None)
q = (x["HYG"] / x["IEF"]).pct_change(20)
idx = cal.searchsorted(q.index, side="right"); m = idx < len(cal); q = pd.Series(q.values[m], index=cal[idx[m]]); q = q[~q.index.duplicated(keep="last")].reindex(cal).ffill()
cap = (q <= -0.02).fillna(False).values
deep = ((nk / nk.rolling(250, min_periods=60).max() - 1) <= -0.20).fillna(False).values
above25 = (nk > nk.rolling(25).mean()).fillna(False).values
def lvl(sh): return 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0.0
def pol(kind="base"):
    e = np.ones(len(sc0)); lock = False
    for i in range(len(sc0)):
        h = 40 if (kind == "V1" and deep[i]) else 20
        v = lvl(sc0[max(0, i - h + 1):i + 1].max())
        if cap[i]: v = 0.0
        if kind == "V2" and deep[i]: v = min(v, 0.5)
        if kind == "V3":
            if deep[i] and v == 0.0: lock = True
            if lock and above25[i]: lock = False
            if lock: v = 0.0
        e[i] = v
    return pd.Series(e, index=cal)
R = {}
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); mm, md, w = epi(r); R[nm] = (a1, d1, a2, d2, w)
    print(f"{nm} | 前半 {a1:+.0f}%・最大下落{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{mm:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
print("深い下落の日の割合:", round(deep.mean() * 100, 1), "%  前半", round(deep[cal < mid].mean() * 100, 1), "% 後半", round(deep[cal >= mid].mean() * 100, 1), "%")
show("基準 今のC", pol("base"))
for k, nm in (("V1", "V1 深い下落中は維持40日"), ("V2", "V2 深い下落中は上限50%"), ("V3", "V3 深い下落中は25日線の上まで0%")): show(nm, pol(k))
show("持ちっぱなし", pd.Series(1.0, index=cal))
b = R["基準 今のC"]
for nm in [k for k in R if k.startswith("V")]:
    a1, d1, a2, d2, w = R[nm]
    ok = d1 >= b[1] + 1 and d2 >= b[3] + 1 and a1 >= b[0] - 10 and a2 >= b[2] - 10 and w >= b[4] - 0.05
    print(nm, "→", "予測出来た（採用条件を満たす）" if ok else "予測出来なかった（採用条件を満たさない）", f"最大下落の差 前半{d1-b[1]:+.1f} 後半{d2-b[3]:+.1f}・累積の差 前半{a1-b[0]:+.0f} 後半{a2-b[2]:+.0f}")
for nm_, a, z in (("リーマン", "2008-09-01", "2009-06-30"), ("2000-02", "2000-04-01", "2003-04-30"), ("コロナ", "2020-02-01", "2020-12-31"), ("2026/10〜", "2026-10-01", None)):
    print(nm_, {k: [round(v) for v in st(run(pol(k)), a, z)] for k in ("base", "V1", "V2", "V3")}, "持ちっぱなし", [round(v) for v in st(run(pd.Series(1.0, index=cal)), a, z)])
print("今：深い下落", bool(deep[-1]), "25日線の上", bool(above25[-1]), cal[-1].date())
