import yfinance as yf
def get(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();return d
d=get("1615.T");nk=get("^N225")
r=d.pct_change();n=r.shift(-1);n5=d.shift(-5)/d-1
dd=d/d.rolling(60).max()
print("range",d.index[0].date(),d.index[-1].date(),round(float(d.iloc[-1]),1),"last r",round(float(r.iloc[-1])*100,2),"dd60",round(float(dd.iloc[-1])*100,1))
nr=nk.pct_change().reindex(d.index)
nk200=(nk<nk.rolling(200).mean()).reindex(d.index)
conds={"all":r.notna(),"up2":r>=0.02,"up2_dd5":(r>=0.02)&(dd<0.95),"up2_dd5_nk<200":(r>=0.02)&(dd<0.95)&(nk200==True)}
for lab,m in conds.items():
  for per,s,e in [("~2011","2000","2011"),("2012~","2012","2026-11-10")]:
    x=n[m][s:e].dropna();y=n5[m][s:e].dropna()
    if len(x)==0: print(lab,per,0);continue
    print(lab,per,"n",len(x),"next1 up%",round((x>0).mean()*100,1),"avg%",round(x.mean()*100,2),"| next5 up%",round((y>0).mean()*100,1),"avg%",round(y.mean()*100,2))
