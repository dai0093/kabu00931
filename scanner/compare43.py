"""検証43：見逃している撤退の指標はないか。ゆっくり動く『地合い』の指標を広く並べ、点灯後60営業日以内に日経が −10%/−20% に達した割合を前半/後半で比べる。
さらに有望なものを方針Cに『点灯中は戻さない（上限25%）』として足した成績。米国の値は東京の翌営業日に使う。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, s="1995-01-01"):
    x = yf.download(t, start=s, auto_adjust=False, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225"); cal = nk.index; mid = pd.Timestamp("2012-01-01")
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal)
    o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
T = {k: dl(v) for k, v in {"sox": "^SOX", "vix": "^VIX", "vix3m": "^VIX3M", "bkx": "^BKX", "jpy": "JPY=X", "tnx": "^TNX", "irx": "^IRX", "hg": "HG=F", "gc": "GC=F", "cl": "CL=F", "spx": "^GSPC", "hyg": "HYG", "ief": "IEF", "lqd": "LQD", "mu": "MU", "wdc": "WDC"}.items()}
P = {k: prev(v) for k, v in T.items()}
mdd = pd.Series([(nk.iloc[i:i+61].min()/nk.iloc[i]-1) if i+61 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
ma = lambda s, n: s / s.rolling(n).mean() - 1
I = {
 "日経が200日線の下": ma(nk, 200) < 0,
 "日経が200日線の下かつ200日線が下向き": (ma(nk, 200) < 0) & (nk.rolling(200).mean().diff(20) < 0),
 "日経が高値から−10%以下（250日）": nk / nk.rolling(250).max() - 1 <= -0.10,
 "日経が高値から−15%以下（250日）": nk / nk.rolling(250).max() - 1 <= -0.15,
 "SOXが200日線の下": ma(P["sox"], 200) < 0,
 "SOXが60日高値から−15%以下": P["sox"] / P["sox"].rolling(60).max() - 1 <= -0.15,
 "S&P500が200日線の下": ma(P["spx"], 200) < 0,
 "米銀指数が200日線の下": ma(P["bkx"], 200) < 0,
 "米銀指数が60日高値から−15%以下": P["bkx"] / P["bkx"].rolling(60).max() - 1 <= -0.15,
 "VIXが3か月VIXより高い（逆転）": P["vix"] / P["vix3m"] > 1,
 "VIXが25以上": P["vix"] >= 25,
 "社債HYG÷IEF 20日≤−2%": (P["hyg"] / P["ief"]).pct_change(20) <= -0.02,
 "社債HYG÷IEFが200日線の下": ma(P["hyg"] / P["ief"], 200) < 0,
 "社債LQD÷IEF 20日≤−1%": (P["lqd"] / P["ief"]).pct_change(20) <= -0.01,
 "長短金利差（10年−3か月）がマイナス": (P["tnx"] - P["irx"]) < 0,
 "ドル円20日で−5%以下（円急騰）": P["jpy"].pct_change(20) <= -0.05,
 "銅÷金が200日線の下": ma(P["hg"] / P["gc"], 200) < 0,
 "原油が1年で+50%以上": P["cl"].pct_change(250) >= 0.5,
 "メモリー株（MU）が60日高値から−25%以下": P["mu"] / P["mu"].rolling(60).max() - 1 <= -0.25,
}
print("指標 | 前半：点灯日数 / 60日内−10% / 60日内−20% | 後半：点灯日数 / −10% / −20% | 判定 | 今")
H = {"前半": cal < mid, "後半": cal >= mid}
base = {k: ((mdd[m] <= -.1).mean(), (mdd[m] <= -.2).mean()) for k, m in H.items()}
print(f"（全日の基準）| 前半 −10% {base['前半'][0]*100:.0f}% −20% {base['前半'][1]*100:.1f}% | 後半 −10% {base['後半'][0]*100:.0f}% −20% {base['後半'][1]*100:.1f}%")
good = []
for nm, s in I.items():
    s = s.reindex(cal).fillna(False).astype(bool); row = []; ok = True
    for k, m in H.items():
        e = mdd[s & m].dropna(); n = int((s & m).sum())
        if n < 40: row.append(f"{n}日 / —"); ok = False; continue
        a, b = (e <= -.1).mean(), (e <= -.2).mean(); row.append(f"{n}日 / {a*100:.0f}% / {b*100:.1f}%")
        if not (a >= 1.5 * base[k][0] and b >= 1.5 * base[k][1]): ok = False
    if ok: good.append(nm)
    print(f"{nm} | {row[0]} | {row[1]} | {'予測出来た' if ok else '予測出来なかった'} | {'点灯中' if s.iloc[-1] else '消灯'}")
# 方針Cに足す
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal2, sc0, run, st, epi, mid2 = G["cal"], np.asarray(G["score"]), G["run"], G["st"], G["epi"], G["mid"]
def pol(cap=None, hold=10):
    e = np.ones(len(sc0))
    for i in range(len(sc0)):
        sh = sc0[max(0, i - hold + 1):i + 1].max(); v = 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
        if cap is not None and cap[i]: v = min(v, cap_lv)
        e[i] = v
    return pd.Series(e, index=cal2)
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid2); a2, d2 = st(r, mid2, None); m, md, w = epi(r)
    print(f"{nm} | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{m:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
print("\n=== 方針Cに『点灯中は持ち高に上限』を足す（予測出来た指標のみ） ===")
show("C（今）", pol())
for nm in good:
    c = I[nm].reindex(cal2).fillna(False).astype(bool).values
    for cap_lv in (0.5, 0.25, 0.0):
        globals()["cap_lv"] = cap_lv; show(f"C＋{nm}→上限{int(cap_lv*100)}%", pol(c))
show("持ちっぱなし", pd.Series(1.0, index=cal2))
