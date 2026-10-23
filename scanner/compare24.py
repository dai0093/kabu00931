"""検証24：「今の状態から持ち続けたら、日経は数か月後どこにいるか」の分布予測（機械学習・分位点回帰）。
点の予測ではなく、5/25/50/75/95%の範囲を出す。毎年、その年より前のデータだけで学習し直して（先読みなし）、
無条件の分布（過去全体の分位点）より精度が上がるか／5-95%範囲が本当に90%を含むかを検証してから、今日の予測を出す。"""
import warnings, json
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare21.py").read().split('y = Y["C_10日内-7%"]')[0])
from sklearn.ensemble import GradientBoostingRegressor
QS = [0.05, 0.25, 0.5, 0.75, 0.95]
HS = [10, 20, 40, 60, 90, 120]
Xf = X.copy().replace([np.inf, -np.inf], np.nan)
lastrow = Xf.iloc[[-1]].copy()
Xf = Xf.ffill(limit=3)
med = Xf.median()
Xn = Xf.fillna(med)
def fwd(h): return (nk.shift(-h) / nk - 1) * 100
def pin(y, q, p): d = y - p; return float(np.mean(np.maximum(q * d, (q - 1) * d)))
def fit(Xtr, ytr, q):
    m = GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.8, min_samples_leaf=40, random_state=0)
    m.fit(Xtr, ytr); return m
val = {}
for h in (20, 60, 120):
    yh = fwd(h); ok = yh.notna() & Xn.notna().all(axis=1)
    P = {q: pd.Series(np.nan, index=cal) for q in QS}; U = {q: pd.Series(np.nan, index=cal) for q in QS}
    for yr in range(2012, int(cal[-1].year) + 1):
        te = ok & (cal.year == yr) if False else (yh.notna() | True) & pd.Series(cal.year == yr, index=cal)
        tr = ok & pd.Series(cal <= pd.Timestamp(f"{yr}-01-01") - pd.Timedelta(days=int(h * 1.5) + 3), index=cal)
        if tr.sum() < 1500 or te.sum() == 0: continue
        for q in QS:
            m = fit(Xn[tr], yh[tr], q); P[q][te] = m.predict(Xn[te]); U[q][te] = float(yh[tr].quantile(q))
    msk = yh.notna() & P[0.5].notna()
    r = {"n": int(msk.sum()), "pinball_ratio": {}, "coverage90": float(((yh[msk] >= P[0.05][msk]) & (yh[msk] <= P[0.95][msk])).mean()),
         "coverage90_uncond": float(((yh[msk] >= U[0.05][msk]) & (yh[msk] <= U[0.95][msk])).mean()),
         "below_p05": float((yh[msk] < P[0.05][msk]).mean()), "below_p05_uncond": float((yh[msk] < U[0.05][msk]).mean())}
    for q in QS: r["pinball_ratio"][str(q)] = round(pin(yh[msk], q, P[q][msk]) / pin(yh[msk], q, U[q][msk]), 3)
    # 直近の下落局面での5%点の当たり具合（低い方の裾）：後半
    h2m = msk & (cal > mid)
    r["h2_below_p05"] = float((yh[h2m] < P[0.05][h2m]).mean()); r["h2_below_p05_uncond"] = float((yh[h2m] < U[0.05][h2m]).mean())
    val[h] = r
    print(f"h={h}日 n={r['n']} 5-95%範囲が実際を含んだ割合 モデル{r['coverage90']*100:.0f}% 無条件{r['coverage90_uncond']*100:.0f}% (理想90%) / 5%点を下回った割合 モデル{r['below_p05']*100:.1f}% 無条件{r['below_p05_uncond']*100:.1f}% (理想5%) / pinball比(1未満＝モデルが良い) {r['pinball_ratio']}")
# 今日の予測
x0 = lastrow.fillna(med)
out = {"asOf": str(cal[-1].date()), "close": float(nk.iloc[-1]), "horizons": {}, "uncond": {}, "validation": {str(k): v for k, v in val.items()},
       "features_today": {k: (None if pd.isna(lastrow[k].iloc[0]) else round(float(lastrow[k].iloc[0]), 2)) for k in ["nk_r5", "nk_dd", "sox_r5", "vix", "vix_term"] if k in lastrow}}
for h in HS:
    yh = fwd(h); ok = yh.notna() & Xn.notna().all(axis=1)
    out["horizons"][str(h)] = {str(q): round(float(fit(Xn[ok], yh[ok], q).predict(x0)[0]), 2) for q in QS}
    out["uncond"][str(h)] = {str(q): round(float(yh[ok].quantile(q)), 2) for q in QS}
    print(h, "今日のモデル", out["horizons"][str(h)], "無条件", out["uncond"][str(h)])
json.dump(out, open("data/forecast.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
