# 検証64：銀行ETF(1615)が1年高値から−10%以下になった日の後、日経が60日以内に−20%（その日の値から）下げる確率。前半(〜2011)・後半(2012〜)
import yfinance as yf
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=d.index.tz_localize(None);return d
b=g("1615.T");n=g("^N225").reindex(b.index).ffill()
dd=b/b.rolling(250,min_periods=120).max()-1
fut=n[::-1].rolling(60,min_periods=1).min()[::-1].shift(-1)/n-1
for lab,m in [("ふだん",dd.notna()),("銀行−10%以下",dd<=-0.10),("銀行−10%を初めて割った日(20日内初)",(dd<=-0.10)&(dd.shift(1)>-0.10))]:
  for per,s,e in [("前半","2008","2011"),("後半","2012","2026-09-30")]:
    x=fut[m][s:e].dropna()
    print(lab,per,"n",len(x),"60日内に−20%",round((x<=-0.2).mean()*100,1),"%","−10%",round((x<=-0.1).mean()*100,1),"%")
