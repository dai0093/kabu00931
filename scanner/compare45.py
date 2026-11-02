"""検証45：改定版仕様書の購入開始ルールを新C（維持20日＋社債20日≤−2%で0%）に足した時の成績（前半/後半/急落40件）。
P3：基準0%の間に SOX5日≥+5% かつ当日信号0本 かつ 社債5日≥0% → 25%（基準が変わるまで）
M200：基準100%でも日経が200日線の下なら75%
VL：社債20日<0 かつ VIX÷VIX3M>1.0 の間は持ち高を増やさない（前日以下に据え置き）"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, st, epi, mid, nk = G["cal"], np.asarray(G["score"]), G["run"], G["st"], G["epi"], G["mid"], G["nk"]
def dl(t, adj=True):
    x = yf.download(t, start="1995-01-01", auto_adjust=adj, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
hy = dl("HYG") / dl("IEF"); q20 = prev(hy.pct_change(20)); q5 = prev(hy.pct_change(5))
sox5 = prev(dl("^SOX").pct_change(5)); vr = prev(dl("^VIX") / dl("^VIX3M"))
nkc = nk.reindex(cal).ffill(); below200 = (nkc < nkc.rolling(200).mean()).values
cc = (q20 <= -0.02).fillna(False).values; p3sig = ((sox5 >= 0.05) & (q5 >= 0)).fillna(False).values
vl = ((q20 < 0) & (vr > 1.0)).fillna(False).values
def pol(P3=False, M200=False, VL=False):
    e = np.ones(len(sc0)); p3 = False
    for i in range(len(sc0)):
        sh = sc0[max(0, i - 19):i + 1].max(); v = 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
        if cc[i]: v = 0.0
        if P3:
            if v == 0 and p3sig[i] and sc0[i] == 0: p3 = True
            if v > 0: p3 = False
            if v == 0 and p3: v = 0.25
            if sc0[i] > 0: p3 = False if v == 0 else p3
        if M200 and v == 1.0 and below200[i]: v = 0.75
        if VL and vl[i] and i > 0: v = min(v, e[i - 1])
        e[i] = v
    return pd.Series(e, index=cal)
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); mm, md, w = epi(r)
    print(f"{nm} | 前半 {a1:+.0f}%・最大下落{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{mm:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
print("（HYGは2007年〜、VIX3Mは2006年〜。それ以前は条件なしと同じ）")
show("新C（今）", pol())
show("新C＋P3 打診25%", pol(P3=True))
show("新C＋M200 200日線割れ75%", pol(M200=True))
show("新C＋VL VIX逆転ロック", pol(VL=True))
show("新C＋全部", pol(True, True, True))
show("持ちっぱなし", pd.Series(1.0, index=cal))
for nm_, a, b in (("リーマン", "2008-09-01", "2008-12-31"), ("コロナ", "2020-02-01", "2020-06-30"), ("2026/10〜", "2026-10-01", "2026-12-31")):
    f = lambda e: [round(v) for v in st(run(e), a, b)]
    print(nm_, "新C", f(pol()), "＋P3", f(pol(P3=True)), "＋全部", f(pol(True, True, True)))
