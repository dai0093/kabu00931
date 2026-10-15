"""検証14：検証13の急落予測モデルは、買い候補以外の一般の保有株にも当てはまるか（予測出来た？）
2024-01〜の全銘柄・全営業日（20日おきに抽出）で、5日以内に−10%以上の急落を予測できたか。
モデルは2023年末までの買い候補だけで学習したもの（試験データは使っていない）"""
import json, pickle
import numpy as np, pandas as pd, yfinance as yf
from sklearn.metrics import roc_auc_score
from core import add_indicators
from data import load
from risk import factors
M = pickle.load(open("data/crash_model.pkl", "rb")); FE = M["FE"]
U = json.load(open("data/universe_all.json", encoding="utf-8"))
raw = load("4y", codes=list(U), size=50, wait=10)
F = factors("6y"); n225 = F["n225"].dropna()
def gy(s):
    x = yf.download(s, start="2021-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
sox, vix, vix3 = gy("^SOX"), gy("^VIX"), gy("^VIX3M")
nkr, soxr = n225.pct_change(), sox.pct_change()
rows = []
for code, df in raw.items():
    df = df.copy(); df.index = pd.to_datetime(df.index).tz_localize(None); d = add_indicators(df); rr = d.Close.pct_change()
    for i in range(260, len(d) - 6, 20):
        dt = d.index[i]
        if dt < pd.Timestamp("2024-01-01"): continue
        r = d.iloc[i]
        if pd.isna(r.atr) or pd.isna(r.sma25): continue
        w = rr.iloc[i-59:i+1]; m = nkr.reindex(w.index); sx = soxr.reindex(w.index, method="ffill"); nn = n225[n225.index <= dt]
        f = {"atrp": r.atr / r.Close, "ext": r.Close / r.sma25 - 1, "r1": rr.iloc[i], "r5": r.Close / d.Close.iloc[i-5] - 1,
             "r20": r.Close / d.Close.iloc[i-20] - 1, "vr": r.Volume / r.vol20 if r.vol20 else np.nan, "to": np.log(max(r.turnover20, 1)),
             "hi250": r.Close / d.High.iloc[i-250:i+1].max() - 1, "upstreak": int((rr.iloc[i-4:i+1] > 0).sum()),
             "vol20": rr.iloc[i-19:i+1].std() * np.sqrt(252), "beta_nk": w.cov(m) / m.var(), "beta_sox": w.cov(sx) / sx.var(),
             "mkt5": nn.iloc[-1] / nn.iloc[-6] - 1, "mkt_ma25": nn.iloc[-1] / nn.tail(25).mean() - 1,
             "sox1": float(soxr[soxr.index <= dt].iloc[-1]), "term": float(vix[vix.index <= dt].iloc[-1] / vix3[vix3.index <= dt].iloc[-1])}
        f["crash"] = int(d.Low.iloc[i+1:i+6].min() / r.Close - 1 <= -0.10); f["fwd5"] = d.Close.iloc[i+5] / r.Close - 1
        rows.append(f)
P = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
p = M["model"].predict_proba(P[FE].astype(float).fillna(M["med"]))[:, 1]; P["p"] = p
L = [f"一般の銘柄・日 {len(P)}件（2024-01〜）。普段の急落率 {P.crash.mean()*100:.2f}%",
     f"予測精度 AUC {roc_auc_score(P.crash, P.p):.3f}（0.5=当てずっぽう）", "", "## 予測確率の10段階ごとの実際の急落率と5日後の平均"]
P["dec"] = pd.qcut(P.p, 10, labels=False, duplicates="drop")
for k, g in P.groupby("dec"):
    L.append(f"- 第{k+1}段階（確率 {g.p.min()*100:.0f}〜{g.p.max()*100:.0f}%）：{len(g)}件 急落率 {g.crash.mean()*100:.1f}% / 5日後平均 {g.fwd5.mean()*100:+.2f}%")
hi = P[P.p >= M["thr"][0.8]]; lo = P[P.p < M["thr"][0.8]]
L.append(f"\n除外ライン（{M['thr'][0.8]*100:.0f}%）以上：{len(hi)}件 急落率 {hi.crash.mean()*100:.1f}% / 未満：{len(lo)}件 急落率 {lo.crash.mean()*100:.1f}%")
L.append("→ " + ("予測出来た" if hi.crash.mean() > 2 * lo.crash.mean() else "予測出来なかった"))
open("data/compare14.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
