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
ok = valid.copy()
yrs = sorted(set(cal[ok].year)); P = pd.Series(np.nan, index=cal); THR = {}
for Yr in [v for v in yrs if v >= 2012]:
    tr = ok & (cal.year < Yr - 0) & (cal <= pd.Timestamp(Yr, 1, 1) - pd.Timedelta(days=15))  # 学習の結果ラベルが翌年に食い込まないよう15日空ける
    te = ok & (cal.year == Yr) | (pd.Series(cal.year == Yr, index=cal) & (cal > nk.index[valid][-1]))
    te = pd.Series(cal.year == Yr, index=cal)
    med = X[tr].median().fillna(0)
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, class_weight="balanced", max_iter=500))
    m.fit(X[tr].fillna(med), y[tr])
    ptr = pd.Series(m.predict_proba(X[tr].fillna(med))[:, 1], index=cal[tr])
    P[te] = m.predict_proba(X[te].fillna(med))[:, 1]
    THR[Yr] = (ptr.quantile(0.80), ptr.quantile(0.95))
th80 = pd.Series({d: THR[d.year][0] for d in cal if d.year in THR}); th95 = pd.Series({d: THR[d.year][1] for d in cal if d.year in THR}).reindex(cal)
oos = P.notna() & valid
print(f"検証期間 {cal[oos][0].date()}〜{cal[oos][-1].date()}  営業日{int(oos.sum())}  平均発生率 {y[oos].mean()*100:.1f}%")
print(f"AUC {roc_auc_score(y[oos], P[oos]):.3f}")
for nm, th in (("上位20%", th80), ("上位5%", th95)):
    s = (P >= th) & oos
    print(f"{nm}（学習期間で決めた閾値）: {int(s.sum())}日 発生{y[s].mean()*100:.0f}%（×{y[s].mean()/y[oos].mean():.1f}）")
ret = nk.pct_change().fillna(0)
def run(expo):
    e = expo.shift(1).fillna(1.0); cost = e.diff().abs().fillna(0) * 0.001
    return e * ret - cost
def stats(r, a=None, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{((eq/eq.cummax()-1).min())*100:.0f}%"
def hyst(sig, quiet_n, lvl):
    e = pd.Series(1.0, index=cal); st = 1.0; q = 0
    for k in range(len(cal)):
        e.iloc[k] = st
        if sig.iloc[k]: st, q = lvl, 0
        else:
            q += 1
            if q >= quiet_n: st = 1.0
    return e
s20 = ((P >= th80) & oos).reindex(cal).fillna(False); s5 = ((P >= th95) & oos).reindex(cal).fillna(False)
# compare19の単独条件（同じ条件を全期間データで固定。参考）
lit = pd.Series(False, index=cal)
for g, c, th in [("EU", "d1", -6), ("EU", "d5", -15), ("US", "d1", -5), ("US", "d5", -10), ("JP", "d1", -5), ("JP", "d5", -10), ("JP", "dd", -25)]: lit |= (F[g][c] <= th).fillna(False)
start = cal[oos][0]
def two(s20, s5):
    e = hyst(s20, 10, 0.5); e5 = hyst(s5, 10, 0.0); return pd.concat([e, e5], axis=1).min(axis=1)
strats = {"①持ちっぱなし": pd.Series(1.0, index=cal), "②単独条件→全額現金(5日)": hyst(lit, 5, 0.0),
          "③組み合わせ上位20%→50%(10日)": hyst(s20, 10, 0.5), "④2段階(上位5%→0%、上位20%→50%)": two(s20, s5)}
print("\n## 検証期間全体（コスト込み）")
for k, e in strats.items(): print(f"{k}: {stats(run(e), start)} ／ 縮小していた日{(e[start:] < 1).mean()*100:.0f}%")
print("\n## 局面別")
for nm, a, b in (("コロナ 2020-01〜04", "2020-01-15", "2020-04-30"), ("2022年", "2022-01-01", "2022-12-31"), ("2024-07〜09", "2024-07-01", "2024-09-30"),
                 ("2025-03〜05", "2025-03-01", "2025-05-31"), ("2026-09〜10", "2026-09-01", "2026-10-20")):
    print(nm + "  " + " ／ ".join(f"{k[:2]} {stats(run(e), a, b)}" for k, e in strats.items()))
print("\n今日(最新)の確率:", f"{P.dropna().iloc[-1]:.3f}", "上位20%閾値", f"{th80.dropna().iloc[-1]:.3f}", "上位5%閾値", f"{th95.dropna().iloc[-1]:.3f}", "→", "上位5%" if P.dropna().iloc[-1] >= th95.dropna().iloc[-1] else "上位20%" if P.dropna().iloc[-1] >= th80.dropna().iloc[-1] else "通常")
