"""検証63：今週（2026-11-09〜13）は11/6の信号6本から20日間0%を維持する間に、日経が+6.5%戻った（57,435→61,142）。
『信号から11〜20日目は段階的に戻す（25%/50%）』と、急落の損失を増やさずに取りこぼしを減らせるか。
基準＝今の方針C（維持20日＋社債HYG÷IEF 20日≤−2%で0%）。条件：なし／日経が25日線の上／SOX5日≥+5%。
採用の条件：前半(〜2011)・後半(2012〜)とも最大下落が悪化せず、急落40件の平均・最悪も悪化せず、成績が上がること。先読みなし（判定は引け後→翌日反映）。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, st, epi, mid, nk = G["cal"], np.asarray(G["score"]), G["run"], G["st"], G["epi"], G["mid"], G["nk"]
def dl(t):
    x = yf.download(t, start="1995-01-01", auto_adjust=True, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
hy = dl("HYG") / dl("IEF"); cc = (prev(hy.pct_change(20)) <= -0.02).fillna(False).values
sox5 = (prev(dl("^SOX").pct_change(5)) >= 0.05).fillna(False).values
nkc = nk.reindex(cal).ffill(); ma25 = (nkc > nkc.rolling(25).mean()).values
f = lambda sh: 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0.0
def pol(L=None, cond=None):
    e = np.ones(len(sc0))
    for i in range(len(sc0)):
        sh20 = sc0[max(0, i - 19):i + 1].max(); sh10 = sc0[max(0, i - 9):i + 1].max(); v = f(sh20)
        if L is not None and sh10 < sh20 and (cond is None or cond[i]): v = max(v, min(f(sh10), L))
        if cc[i]: v = 0.0
        e[i] = v
    return pd.Series(e, index=cal)
res = {}
def show(nm, e):
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); mm, md, w = epi(r); res[nm] = (a1, d1, a2, d2, mm, w)
    a, b = st(r, "2026-10-01", None)
    print(f"{nm} | 前半 {a1:+.0f}%・最大下落{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{mm:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}% | 2026/10〜 {a:+.1f}%・{b:.1f}%")
show("新C（今）", pol())
for L in (0.25, 0.5):
    for cn, c in (("条件なし", None), ("25日線の上", ma25), ("SOX5日≥+5%", sox5)):
        show(f"11〜20日目{int(L*100)}%（{cn}）", pol(L, c))
b = res["新C（今）"]
print("\n判定（前半・後半とも 成績↑ かつ 最大下落・急落平均・最悪が悪化しない）")
for k, v in res.items():
    if k == "新C（今）": continue
    ok = v[0] > b[0] and v[2] > b[2] and v[1] >= b[1] and v[3] >= b[3] and v[4] >= b[4] and v[5] >= b[5]
    print(f"  {k}: {'予測出来た（採用候補）' if ok else '予測出来なかった（不採用）'}")
print("最終日:", cal[-1].date())
