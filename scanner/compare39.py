"""検証39：社債ETF÷米国債（HYG/IEF・LQD/IEF）の20日変化が大きく下がった後、日経は60日以内に−20%以下になったか。
HYGは2007年〜のため前半は2007-2011（リーマン1回分）。あわせてリーマン前の推移と、今の水準が過去のどの位置か。"""
import warnings; import pandas as pd, numpy as np, yfinance as yf
warnings.filterwarnings("ignore")
x=yf.download(["HYG","LQD","IEF","^N225"],start="2007-04-01",auto_adjust=True,progress=False)["Close"].ffill().dropna()
nk=x["^N225"]; mdd=pd.Series([(nk.iloc[i:i+61].min()/nk.iloc[i]-1) if i+61<=len(nk) else np.nan for i in range(len(nk))],index=nk.index)
mid=pd.Timestamp("2012-01-01")
for k in ("HYG","LQD"):
    q=x[k]/x["IEF"]; d20=(q/q.shift(20)-1)*100
    print(f"\n=== {k}÷IEF 20日変化 ===  今 {d20.iloc[-1]:+.2f}%（{x.index[-1].date()}）  過去での低さの順位 {(d20<=d20.iloc[-1]).mean()*100:.1f}%点")
    for th in (-2,-3,-5):
        for nm,m in (("前半07-11",d20.index<mid),("後半12-",d20.index>=mid)):
            on=(d20<=th)&m; e=mdd[on].dropna(); b=mdd[m].dropna()
            if len(e): print(f"  ≤{th}% {nm}: {int(on.sum())}日 → 60日内 日経−20%以下 {(e<=-.2).mean()*100:.0f}%（全日{(b<=-.2).mean()*100:.0f}%）−10%以下 {(e<=-.1).mean()*100:.0f}%（全日{(b<=-.1).mean()*100:.0f}%）")
    print("  リーマン前後:", {str(dd.date()):round(float(d20[dd]),1) for dd in d20["2008-06-30":"2008-10-31"].index[::10]})
