"""先行きの確率予測（検証40）：日経が今後 5/20/60営業日のうちに、今日の終値から −5%/−10%/−20% に一度でも達する確率と、20日後に上がっている確率。
特徴量は前半・後半で関係が安定していた市場間の連動（SOX・VIX・米銀・ドル円）と日経自身の下落幅・変動率。
1) 前半(〜2011)で学習→後半(2012〜)で答え合わせ（基準率よりBrierが良いか・較正）  2) 全期間で学習し今日の確率を data/outlook.json へ
3) 毎日の予測を data/outlook_log.json に残し、期限が来たものを採点（修正の材料）。 引数 --test で検証のみ"""
import json, sys, warnings
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd, yfinance as yf
from sklearn.linear_model import LogisticRegression
warnings.filterwarnings("ignore"); JST = timezone(timedelta(hours=9))
def dl(t):
    x = yf.download(t, start="1995-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]; x.index = pd.to_datetime(x.index).tz_localize(None); return x
N = dl("^N225"); C = N["Close"].dropna()
try:  # Yahooの日経が最新日を欠く時は 1321 の騰落で補う
    _e = dl("1321.T")["Close"].dropna()
    for _d in _e.index[_e.index > C.index[-1]]:
        _p = _e.index[_e.index < _d][-1]
        if _p in C.index: C.loc[_d] = float(C[_p]) * float(_e[_d] / _e[_p])
    C = C.sort_index()
except Exception as _x: print("1321補完失敗", _x)
NEXT = C.index[-1] + pd.offsets.BDay(1)   # 次の東京の取引日（前夜の米国を織り込んだ予測を出すため）
cal = C.index.append(pd.DatetimeIndex([NEXT])); C = C.reindex(cal)
def al(t): return dl(t)["Close"].dropna()
sox, vix, bkx, jpy = al("^SOX"), al("^VIX"), al("^BKX"), al("JPY=X")
# 米国の値は東京の前日以前（前夜）までしか使わない
def prev(s):
    s = s.copy(); idx = cal.searchsorted(s.index, side="right")  # 米国日 d → 東京で d より後の最初の営業日に使える
    m = idx < len(cal); out = pd.Series(s.values[m], index=cal[idx[m]]); return out[~out.index.duplicated(keep="last")].reindex(cal).ffill()
S, V, B, J = prev(sox), prev(vix), prev(bkx), prev(jpy)
C_f = C.ffill(); r1 = C_f.pct_change()
F = pd.DataFrame({
    "nk_dd60": C_f / C_f.rolling(60).max() - 1, "nk_dd250": C_f / C_f.rolling(250).max() - 1,
    "nk_r5": C_f.pct_change(5), "nk_r20": C_f.pct_change(20), "nk_vol20": r1.rolling(20).std() * np.sqrt(252),
    "nk_ma200": C_f / C_f.rolling(200).mean() - 1,
    "sox_r1": S.pct_change(), "sox_r5": S.pct_change(5), "sox_r20": S.pct_change(20), "sox_dd60": S / S.rolling(60).max() - 1,
    "vix": V, "vix_r5": V / V.shift(5) - 1,
    "bk_r5": B.pct_change(5), "bk_dd60": B / B.rolling(60).max() - 1,
    "jpy_r20": J.pct_change(20),
}, index=cal)
H = {5: None, 20: None, 60: None}; TH = (0.05, 0.10, 0.20)
def fut_min(h):  # 今日の終値から h 日以内の最安値（終値ベース）
    a = C.values; o = np.full(len(a), np.nan)
    for i in range(len(a) - h): o[i] = a[i + 1:i + 1 + h].min() / a[i] - 1
    return pd.Series(o, index=cal)
Y = {}
for h in (5, 20, 60):
    m = fut_min(h)
    for th in TH:
        if h == 5 and th == 0.20: continue
        Y[f"{h}d_-{int(th*100)}"] = (m <= -th).astype(float).where(m.notna())
up20 = (C.shift(-20) / C - 1); Y["20d_up"] = (up20 > 0).astype(float).where(up20.notna())
D = F.dropna(); mid = pd.Timestamp("2012-01-01")
def fit(X, y):
    mu, sd = X.mean(), X.std().replace(0, 1)
    m = LogisticRegression(C=0.3, max_iter=2000).fit((X - mu) / sd, y); return m, mu, sd
def pr(mdl, X): m, mu, sd = mdl; return m.predict_proba((X - mu) / sd)[:, 1]
res = {}
if "--test" in sys.argv or True:
    print("=== 検証40：前半で学習→後半で答え合わせ ===")
    for k, y in Y.items():
        d = D.join(y.rename("y")).dropna(); tr, te = d[d.index < mid], d[d.index >= mid]
        if tr.y.nunique() < 2 or len(te) < 100: continue
        mdl = fit(tr.drop(columns="y"), tr.y); p = pr(mdl, te.drop(columns="y"))
        base = tr.y.mean(); bs = np.mean((p - te.y) ** 2); bb = np.mean((base - te.y) ** 2); bb2 = np.mean((te.y.mean() - te.y) ** 2)
        skill = 1 - bs / bb
        # 上位10%の予測確率の日に実際どうなったか
        q = np.quantile(p, 0.9); hi = te.y[p >= q].mean(); lo = te.y[p < np.quantile(p, 0.5)].mean()
        ok = skill > 0.01 and hi >= 1.5 * te.y.mean() if not k.endswith("up") else (skill > 0.01 and hi > te.y.mean() + 0.05)
        res[k] = {"skill": round(float(skill), 3), "base_train": round(float(base), 3), "rate_test": round(float(te.y.mean()), 3),
                  "top10": round(float(hi), 3), "bottom50": round(float(lo), 3), "ok": bool(ok)}
        print(f"{k}: 後半の実際の発生率 {te.y.mean()*100:.1f}%  予測上位10%の日 {hi*100:.1f}%  予測下位50%の日 {lo*100:.1f}%  Brierスキル {skill:+.3f}（基準率比）→ {'予測出来た' if ok else '予測出来なかった'}")
        # 較正（5分位）
        cb = pd.qcut(pd.Series(p, index=te.index), 5, labels=False, duplicates="drop")
        print("   較正 予測平均→実際:", " / ".join(f"{pd.Series(p,index=te.index)[cb==b].mean()*100:.0f}%→{te.y[cb==b].mean()*100:.0f}%" for b in sorted(cb.unique())))
if "--test" in sys.argv: sys.exit(0)
# 全期間で学習 → 今日
today = F.iloc[[-1]].ffill(); asof = str(cal[-2].date()); P = {}; nxt = str(NEXT.date())
for k, y in Y.items():
    d = D.join(y.rename("y")).dropna()
    mdl = fit(d.drop(columns="y"), d.y); P[k] = round(float(pr(mdl, today)[0]), 3)
base = {k: round(float(y.dropna().mean()), 3) for k, y in Y.items()}
out = {"asOf": asof, "for": nxt, "close": round(float(C.iloc[-2]), 0), "prob": P, "base": base, "valid": res,
       "updatedAt": datetime.now(JST).isoformat(timespec="minutes"),
       "features": {k: round(float(v), 4) for k, v in today.iloc[0].items()},
       "rule": "今日の終値から、その期間内に一度でもその下落幅に達する確率。前半で学習し後半で当たったもの（ok）だけを判定に使う"}
json.dump(out, open("data/outlook.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 記録と採点
try: LG = json.load(open("data/outlook_log.json", encoding="utf-8"))
except Exception: LG = []
if not LG or LG[-1]["asOf"] != asof: LG.append({"asOf": asof, "close": out["close"], "prob": P})
cpos = {str(d.date()): i for i, d in enumerate(cal)}
for e in LG:
    i = cpos.get(e["asOf"]); e.setdefault("result", {})
    if i is None: continue
    for k in P:
        h = int(k.split("d")[0])
        if k in e["result"] or i + h >= len(C) - 1: continue
        if k == "20d_up": e["result"][k] = bool(C.iloc[i + 20] > C.iloc[i])
        else: e["result"][k] = bool(C.iloc[i + 1:i + 1 + h].min() / C.iloc[i] - 1 <= -int(k.split("-")[1]) / 100)
json.dump(LG[-400:], open("data/outlook_log.json", "w", encoding="utf-8"), ensure_ascii=False)
print(out["asOf"], P)
