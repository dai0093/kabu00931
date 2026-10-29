"""検証38：米大型株の時間外急落（翌寄り−5%以下）は、その後60営業日の日経の大暴落（最大下落−20%以下）の予兆か。前半/後半。
あわせて『同じ日に銀行株も崩れていたか』で分ける（リーマン型＝信用経路）。"""
import warnings; import pandas as pd, numpy as np, yfinance as yf
warnings.filterwarnings("ignore")
US=["GOOGL","NVDA","MSFT","AAPL","AMZN","META","INTC","AMD","AVGO","QCOM","MU","TXN","AMAT","LRCX","KLAC","ORCL","CSCO","IBM"]
def d(t): x=yf.download(t,start="2000-01-01",auto_adjust=False,progress=False); x.columns=[c[0] if isinstance(c,tuple) else c for c in x.columns]; x.index=pd.to_datetime(x.index).tz_localize(None); return x
nk=d("^N225")["Close"]; kbw=d("^BKX")["Close"]; c=nk.index
# 60営業日先までの最大下落
mdd=pd.Series([ (nk.iloc[i:i+61].min()/nk.iloc[i]-1) if i+61<=len(nk) else np.nan for i in range(len(nk))],index=c)
bk1=kbw.pct_change().reindex(c,method="ffill")
days=set()
for t in US:
    x=d(t); g=x["Open"]/x["Close"].shift(1)-1
    days|=set(g[g<=-0.05].index)
days=sorted(x for x in days if x in c)
mid=pd.Timestamp("2012-01-01")
for nm,m in (("前半",c<mid),("後半",c>=mid)):
    base=mdd[m].dropna(); ev=pd.Series([mdd[x] for x in days if (x<mid)==(nm=="前半")]).dropna()
    print(f"\n{nm}: 急落のあった日 {len(ev)}日")
    print(f"  60日以内に日経−20%以下: {(ev<=-.2).mean()*100:.1f}%（全日 {(base<=-.2).mean()*100:.1f}%）  −10%以下: {(ev<=-.1).mean()*100:.0f}%（全日 {(base<=-.1).mean()*100:.0f}%）")
    for lab,cond in (("銀行株(米KBW)も前日−3%以下",lambda x: bk1.get(x,0)<=-.03),("銀行株は崩れていない",lambda x: bk1.get(x,0)>-.03)):
        e=pd.Series([mdd[x] for x in days if (x<mid)==(nm=="前半") and cond(x)]).dropna()
        if len(e): print(f"  {lab}: {len(e)}日 → −20%以下 {(e<=-.2).mean()*100:.1f}% −10%以下 {(e<=-.1).mean()*100:.0f}%")
print("\n2008年9月(リーマン)の前3か月の急落日:", [str(x.date()) for x in days if pd.Timestamp('2008-06-15')<=x<=pd.Timestamp('2008-09-15')])
print("10/29の米KBW銀行株 1日:", f"{kbw.pct_change().iloc[-1]*100:+.2f}%", kbw.index[-1].date())
