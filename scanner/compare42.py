"""検証42：金・銀・プラチナの現状（1年・高値からの下落・200日線）と、『200日線割れで売る』『高値から−20%で売る』が各金属で効いたか（前半〜2011/後半2012〜）。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
M = {"金": "GC=F", "銀": "SI=F", "プラチナ": "PL=F", "パラジウム": "PA=F"}
mid = pd.Timestamp("2012-01-01")
def dd(r): c = (1 + r).cumprod(); return float((c / c.cummax() - 1).min() * 100)
def cum(r): return float(((1 + r).prod() - 1) * 100)
for nm, t in M.items():
    x = yf.download(t, start="2000-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None)
    c = x.iloc[-1]; y1 = x[x.index >= x.index[-1] - pd.Timedelta(days=365)]
    ma = x.rolling(200).mean()
    print(f"\n=== {nm}（{t}）{x.index[-1].date()} 終値 {c:,.1f} ===")
    print(f"1年騰落 {(c/y1.iloc[0]-1)*100:+.1f}%  1年高値 {y1.max():,.1f}（{y1.idxmax().date()}）から {(c/y1.max()-1)*100:+.1f}%  20日 {(c/x.iloc[-21]-1)*100:+.1f}%  200日線比 {(c/ma.iloc[-1]-1)*100:+.1f}%")
    r = x.pct_change().fillna(0)
    rules = {"持ちっぱなし": pd.Series(1.0, index=x.index),
             "200日線割れで売る": (x > ma).astype(float).shift(1).fillna(1),
             "高値−20%で売り、200日線回復で買い戻す": None}
    hi = x.cummax(); s = np.ones(len(x)); on = 1
    for i in range(1, len(x)):
        if on and x.iloc[i - 1] <= hi.iloc[i - 1] * 0.8: on = 0
        elif not on and x.iloc[i - 1] > ma.iloc[i - 1]: on = 1; hi.iloc[i:] = x.iloc[i:].cummax()  # 高値を取り直す
        s[i] = on
    rules["高値−20%で売り、200日線回復で買い戻す"] = pd.Series(s, index=x.index)
    for k, e in rules.items():
        rr = r * e
        print(f"  {k}: 前半 {cum(rr[rr.index<mid]):+.0f}%・最大下落{dd(rr[rr.index<mid]):.0f}%  後半 {cum(rr[rr.index>=mid]):+.0f}%・最大下落{dd(rr[rr.index>=mid]):.0f}%")
