"""検証20：複数の信号を組み合わせた暴落リスク判定の精度を、先読みなし（毎年、その年より前のデータだけで再学習）で検証する。
目的変数：10営業日以内に日経が-7%以下（C）。特徴量：金融機関株価（群の中央値）、日経・SOX・VIX・金利・原油・信用(HYG/IEF)。
比較：①持ちっぱなし ②compare19の単独条件（点灯で全額現金）③組み合わせ判定で50%に縮小 ④組み合わせ判定の2段階（上位5%は0%、上位20%は50%）
先読み防止：閾値（学習期間の予測確率の上位20%/5%）も学習期間だけで決める。売買コスト：エクスポージャー変更1.0あたり0.1%。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("out, rules, lines = [], [], []")[0])
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
def yf1(t):
    x = yf.download(t, start="2005-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None); return x["Close"].dropna()
al = lambda s: s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
sox, vix, v3, tnx, brent, hyg, ief = (al(yf1(t)) for t in ["^SOX", "^VIX", "^VIX3M", "^TNX", "BZ=F", "HYG", "IEF"])
X = pd.DataFrame(index=cal)
for g, f in F.items():
    for c in ("d1", "d5", "dd", "f1"): X[f"{g}_{c}"] = f[c]
X["nk_r5"] = nk.pct_change(5) * 100; X["nk_r20"] = nk.pct_change(20) * 100; X["nk_dd"] = (nk / nk.rolling(60).max() - 1) * 100
X["sox_r5"] = sox.pct_change(5) * 100; X["sox_dd"] = (sox / sox.rolling(252, min_periods=120).max() - 1) * 100
X["vix"] = vix; X["vix_term"] = vix / v3; X["tnx"] = tnx; X["tnx_d20"] = tnx.diff(20)
X["brent_d20"] = brent.pct_change(20) * 100; X["cred_d20"] = (hyg / ief).pct_change(20) * 100
X = X.replace([np.inf, -np.inf], np.nan)
y = Y["C_10日内-7%"].astype(float)
h1 = valid & (nk.index <= mid); h2 = valid & (nk.index > mid)
b1, b2 = float(y[h1].mean()), float(y[h2].mean())
# 基準信号（compare19：前半だけで選んだ点灯条件）
R = [("EU","d1",-6),("EU","d5",-15),("US","d1",-5),("US","d5",-10),("JP","d1",-5),("JP","d5",-10),("JP","dd",-25)]
hit = pd.DataFrame({f"{g}.{c}": (F[g][c] <= th).fillna(False) for g, c, th in R})
base = hit.any(axis=1); ngrp = pd.concat([hit[[f"{g}.{c}" for g2,c,t in R if g2==g]].any(axis=1) for g in ("EU","US","JP")], axis=1).sum(axis=1)
def rep(nm, s):
    o = []
    for lab, h, b in (("前半", h1, b1), ("後半", h2, b2)):
        m = s & h; n = int(m.sum()); o.append(f"{lab} {n}日 発生{(y[m].mean()*100 if n else 0):.0f}%(×{(y[m].mean()/b if n else 0):.1f})")
    print(f"{nm}: " + " / ".join(o))
rep("基準（どれか）", base); rep("2群以上が同時", ngrp >= 2); rep("3群すべて", ngrp >= 3)
# 追加の条件（AND）を前半だけで選ぶ：前半の発生率が最大で、前半の信号日が30日以上
cands = []
for c in ["nk_r5","nk_r20","nk_dd","sox_r5","sox_dd","vix","vix_term","tnx_d20","brent_d20","cred_d20","PC_d5","PC_dd","BDC_d5","US_dd","EU_dd"]:
    for q in (0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9):
        for side in ("<=", ">="):
            th = X[c][h1].quantile(q)
            f = (X[c] <= th) if side == "<=" else (X[c] >= th)
            m = base & f.fillna(False) & h1; n = int(m.sum())
            if n >= 30: cands.append((float(y[m].mean()), c, side, q, th, n))
cands.sort(reverse=True)
print("\n前半だけで選んだ追加条件（基準AND条件）上位5:")
for r, c, side, q, th, n in cands[:5]:
    f = (X[c] <= th) if side == "<=" else (X[c] >= th)
    print(f"  基準 AND {c}{side}{th:.2f}  前半n={n} 発生{r*100:.0f}%"); rep("    → ", base & f.fillna(False))
rr, c, side, q, th, n = cands[0]
fbest = ((X[c] <= th) if side == "<=" else (X[c] >= th)).fillna(False); sig = base & fbest
ret = nk.pct_change().fillna(0)
def hyst(s, quiet_n, lvl):
    e = pd.Series(1.0, index=cal); st = 1.0; q = 0
    for k in range(len(cal)):
        e.iloc[k] = st
        if s.iloc[k]: st, q = lvl, 0
        else:
            q += 1
            if q >= quiet_n: st = 1.0
    return e
def run(e): return e.shift(1).fillna(1.0) * ret - e.shift(1).fillna(1.0).diff().abs().fillna(0) * 0.001
def stats(r, a, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{((eq/eq.cummax()-1).min())*100:.0f}%"
print("\n## 後半（未見）の成績（コスト込み）")
for nm, e in (("持ちっぱなし", pd.Series(1.0, index=cal)), ("基準→50%(10日)", hyst(base, 10, .5)), ("基準→全額現金(5日)", hyst(base, 5, 0.)),
              ("基準AND追加条件→50%(10日)", hyst(sig, 10, .5)), ("基準AND追加条件→全額現金(5日)", hyst(sig, 5, 0.)), ("2群以上→50%(10日)", hyst(ngrp >= 2, 10, .5))):
    print(f"{nm}: {stats(run(e), mid)} ／ 縮小{(e[mid:]<1).mean()*100:.0f}%日", end="")
    print("  | " + " ".join(f"{k}:{stats(run(e),a,b).split(' ')[0]}" for k, a, b in (("コロナ","2020-01-15","2020-04-30"),("2022","2022-01-01","2022-12-31"),("24夏","2024-07-01","2024-09-30"),("25春","2025-03-01","2025-05-31"))))
print("\n今日: 基準", bool(base.iloc[-1]), " 2群以上", bool((ngrp>=2).iloc[-1]), " 追加条件", bool(fbest.iloc[-1]), " 値", {k: (round(float(X[k].iloc[-1]),2)) for k in [c]})
