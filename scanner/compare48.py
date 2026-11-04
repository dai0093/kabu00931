"""検証48：今と同じ『高値から−14〜−18%、25日線の下、20日騰落マイナス』の日のあと、日経はさらに下げ続けたか（前半/後半）。
今後60営業日の：さらに−10%以下に達した割合／−20%以下（高値から約−33%＝大暴落）／60日後の騰落の中央値／高値から−10%以内まで戻した割合。比較＝全日。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
x = yf.download("^N225", start="1970-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None)
cal = x.index; mid = pd.Timestamp("2012-01-01"); hi = x.rolling(250, min_periods=60).max(); dd = x / hi - 1
f60 = x.shift(-60) / x - 1
mn = pd.Series([(x.iloc[i+1:i+61].min()/x.iloc[i]-1) if i+61 <= len(x) else np.nan for i in range(len(x))], index=cal)
rec = pd.Series([((x.iloc[i+1:i+61] / hi.iloc[i] - 1) >= -0.10).any() if i+61 <= len(x) else np.nan for i in range(len(x))], index=cal)
cond = (dd <= -0.14) & (dd >= -0.18) & (x < x.rolling(25).mean()) & (x.pct_change(20) < 0)
H = {"前半(〜2011)": cal < mid, "後半(2012〜)": cal >= mid}
for k, m in H.items():
    a, s = m & cond, m
    ev = []
    for d in cal[a]:
        if not ev or (d - ev[-1]).days > 60: ev.append(d)
    def st(z): return f"さらに−10% {(mn[z].dropna()<=-.1).mean()*100:.0f}%／さらに−20% {(mn[z].dropna()<=-.2).mean()*100:.0f}%／60日後 中央値{f60[z].median()*100:+.1f}%・下落の割合{(f60[z].dropna()<0).mean()*100:.0f}%／高値−10%以内に戻す {rec[z].dropna().mean()*100:.0f}%"
    print(f"{k}: 該当{int(a.sum())}日（独立{len(ev)}回）\n   今と同じ形: {st(a)}\n   全日      : {st(s)}")
print("\n独立した局面（後半）と60日以内の最安:")
ev = []
for d in cal[cond & (cal >= mid)]:
    if not ev or (d - ev[-1]).days > 60: ev.append(d)
for d in ev: print(f"  {d.date()} 高値比{dd[d]*100:.0f}% → 60日内の最安 {mn[d]*100:+.0f}%  60日後 {f60[d]*100:+.0f}%")
print("今:", cal[-1].date(), f"高値比 {dd.iloc[-1]*100:.1f}%", "条件", bool(cond.iloc[-1]))
