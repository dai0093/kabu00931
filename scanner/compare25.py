"""検証25：米国の証拠金債務（FINRA）の水準・伸び・減少は、その後の株の大きな下落を予測したか。
条件は前半（〜2011）だけで選び、後半（2012〜）にそのまま適用。公表遅れを考慮し、月末のデータは翌月末から使う。
目的：S&P500が、その後6か月以内に高値から-15%以上下落（最大下落）／3か月・6か月リターン。"""
import io, warnings, requests
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
r = requests.get("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx", timeout=60, headers={"User-Agent": "Mozilla/5.0"}); r.raise_for_status()
raw = pd.read_excel(io.BytesIO(r.content), header=None)
hr = next(i for i in range(len(raw)) if raw.iloc[i].astype(str).str.contains("Debit", case=False).any())
df = raw.iloc[hr + 1:, :2].copy(); df.columns = ["m", "debit"]
df["m"] = pd.to_datetime(df["m"], format="%b-%y", errors="coerce").fillna(pd.to_datetime(df["m"], errors="coerce"))
df = df.dropna().set_index("m")["debit"].astype(float).sort_index(); df.index = df.index + pd.offsets.MonthEnd(0)
print("margin debt", df.index[0].date(), "→", df.index[-1].date(), "n", len(df), "latest", df.iloc[-1])
sp = yf.download("^GSPC", start="1996-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
me = sp.resample("ME").last()
X = pd.DataFrame({"debit": df}).join(me.rename("sp"), how="left")
X["yoy"] = X["debit"].pct_change(12) * 100; X["mom"] = X["debit"].pct_change() * 100
X["at12hi"] = X["debit"] >= X["debit"].rolling(12).max() * 0.999
X["off_peak"] = (X["debit"] / X["debit"].rolling(12).max() - 1) * 100
# 公表遅れ：判定は翌月末から
for c in ("yoy", "mom", "at12hi", "off_peak"): X[c + "_av"] = X[c].shift(1)
def fwd_dd(i, h):
    w = me.iloc[i + 1:i + 1 + h]; base = me.iloc[i]
    return float((w.min() / base - 1) * 100) if len(w) == h else np.nan
idx = {d: k for k, d in enumerate(me.index)}
X["ret3"] = [(me.iloc[idx[d] + 3] / me.iloc[idx[d]] - 1) * 100 if d in idx and idx[d] + 3 < len(me) else np.nan for d in X.index]
X["ret6"] = [(me.iloc[idx[d] + 6] / me.iloc[idx[d]] - 1) * 100 if d in idx and idx[d] + 6 < len(me) else np.nan for d in X.index]
X["dd6"] = [fwd_dd(idx[d], 6) if d in idx else np.nan for d in X.index]
# 判定は「利用可能になった月」の月末基準（翌月末）で、その後6か月を見る → シフト
for c in ("ret3", "ret6", "dd6"): X[c + "_s"] = X[c].shift(-1)
X = X.dropna(subset=["yoy_av", "dd6_s"])
X["ev"] = X["dd6_s"] <= -15
mid = pd.Timestamp("2012-01-01"); h1 = X.index < mid; h2 = ~h1
b1, b2 = X.loc[h1, "ev"].mean(), X.loc[h2, "ev"].mean()
print(f"基準：6か月内に-15%以上の下落が起きた割合 前半{b1*100:.0f}%(n={h1.sum()}) 後半{b2*100:.0f}%(n={h2.sum()})")
def rep(nm, s):
    s = s.fillna(False); o = []
    for lab, h, b in (("前半", h1, b1), ("後半", h2, b2)):
        m = s & h; n = int(m.sum())
        o.append(f"{lab} {n}か月 下落発生{(X.loc[m,'ev'].mean()*100 if n else 0):.0f}%(×{(X.loc[m,'ev'].mean()/b if n and b else 0):.1f}) 6か月後平均{(X.loc[m,'ret6_s'].mean() if n else 0):+.1f}%")
    print(f"{nm}: " + " / ".join(o))
S = {"伸び率(前年比)≥+30%": X["yoy_av"] >= 30, "伸び率≥+40%": X["yoy_av"] >= 40, "伸び率≥+25%かつ12か月高値圏": (X["yoy_av"] >= 25) & X["at12hi_av"],
     "前月比≤-3%（減少）": X["mom_av"] <= -3, "前月比≤-5%（急減）": X["mom_av"] <= -5, "高値から-8%以上減少": X["off_peak_av"] <= -8,
     "伸び率≥+30%かつ前月比がマイナス": (X["yoy_av"] >= 30) & (X["mom_av"] < 0)}
for k, v in S.items(): rep(k, v)
print("\n直近（利用可能な最新）:", X.index[-1].date() if False else df.index[-1].date(), "前年比", round(float(df.pct_change(12).iloc[-1]*100),1), "前月比", round(float(df.pct_change().iloc[-1]*100),2), "12か月高値比", round(float((df.iloc[-1]/df.rolling(12).max().iloc[-1]-1)*100),1))
print("直近12か月:", ", ".join(f"{d.strftime('%y-%m')}:{v/1e6:.2f}兆" for d, v in df.tail(12).items()))
