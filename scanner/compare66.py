# 検証66：今と同じ状態（日経が1年高値から−15〜−22%、200日線の下、S&P500も200日線の下）から27営業日後（年末）の日経
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
n=g("^N225");sp=g("^GSPC").reindex(n.index).ffill()
dd=n/n.rolling(250).max()-1
st=dd.between(-0.22,-0.15)&(n<n.rolling(200).mean())&(sp<sp.rolling(200).mean())
f=n.shift(-27)/n-1;mn=n[::-1].rolling(27,min_periods=1).min()[::-1].shift(-1)/n-1
for per,s,e in [("前半","1990","2011"),("後半","2012","2026-09-30")]:
  for lab,m in [("今と同じ状態",st),("ふだん",dd.notna())]:
    x=f[m][s:e].dropna();y=mn[m][s:e].dropna()
    print(per,lab,"n",len(x),"年末に上",round((x>0).mean()*100),"%","中央値",round(x.median()*100,1),"%","途中で−10%以上",round((y<=-0.1).mean()*100),"%","−20%以上",round((y<=-0.2).mean()*100),"%")
