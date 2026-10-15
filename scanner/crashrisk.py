"""検証13の急落予測モデルで、買い候補ごとの『5日以内に−10%以上の急落』確率を出す。
除外ライン：学習期間の確率の上位20%（2023〜の年ごとの検証で、除外すると日経比 +1,780,441円・急落率 12.8%→8.4%）"""
import pickle
import numpy as np, pandas as pd, yfinance as yf

M = pickle.load(open("data/crash_model.pkl", "rb"))
THR = M["thr"][0.8]


def _y(s):
    x = yf.download(s, period="6mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return x


def score(cands, frames, n225):
    if not cands: return
    sox, vix, vix3 = _y("^SOX"), _y("^VIX"), _y("^VIX3M")
    nkr, soxr = n225.pct_change(), sox.pct_change()
    for t in cands:
        d = frames[t["code"]]; i = len(d) - 1; r = d.iloc[i]; rr = d.Close.pct_change(); dt = d.index[i]
        w = rr.iloc[i-59:i+1]; m = nkr.reindex(w.index); sx = soxr.reindex(w.index, method="ffill")
        nn = n225[n225.index <= dt]
        f = {"atrp": r.atr / r.Close, "ext": r.Close / r.sma25 - 1, "r1": rr.iloc[i],
             "r5": r.Close / d.Close.iloc[i-5] - 1, "r20": r.Close / d.Close.iloc[i-20] - 1,
             "vr": r.Volume / r.vol20, "to": np.log(r.turnover20),
             "hi250": r.Close / d.High.iloc[max(0, i-250):i+1].max() - 1,
             "upstreak": int((rr.iloc[i-4:i+1] > 0).sum()), "vol20": rr.iloc[i-19:i+1].std() * np.sqrt(252),
             "beta_nk": w.cov(m) / m.var() if m.var() > 0 else np.nan,
             "beta_sox": w.cov(sx) / sx.var() if sx.var() > 0 else np.nan,
             "mkt5": nn.iloc[-1] / nn.iloc[-6] - 1, "mkt_ma25": nn.iloc[-1] / nn.tail(25).mean() - 1,
             "sox1": float(soxr[soxr.index <= dt].iloc[-1]),
             "term": float(vix[vix.index <= dt].iloc[-1] / vix3[vix3.index <= dt].iloc[-1])}
        X = pd.DataFrame([f])[M["FE"]].astype(float).fillna(M["med"])
        p = float(M["model"].predict_proba(X)[:, 1][0])
        t["crash_p"] = round(p, 3); t["crash_thr"] = round(THR, 3); t["crash_out"] = p >= THR
        t["crash_why"] = f"5日騰落 {f['r5']*100:+.0f}% / 値幅(ATR) {f['atrp']*100:.1f}% / 25日線乖離 {f['ext']*100:+.0f}%"
