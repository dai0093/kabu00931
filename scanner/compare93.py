# 検証93：個別株の予測の幅（起点2026-11-25に固定）。SOXの過去11局面の経路×各銘柄のβ。セリングクライマックス（最安）の日と値も
import yfinance as yf, pandas as pd, numpy as np, json
def g(t,per="max"):
    d=yf.download(t,period=per,progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");sx=g("^SOX");vx=g("^VIX").reindex(sp.index).ffill();sxa=sx.reindex(sp.index).ffill()
A=((sxa/sxa.shift(5)-1<=-0.15)&(vx>=30)).fillna(False);ep=[];prev=None
for x in A[A].index:
    if prev is None or (x-prev).days>90: ep.append(x)
    prev=x
ep=[e for e in ep if e<pd.Timestamp("2026-01-01")];H=250
P=np.array([np.log((sx[e:].iloc[:H+1]/sx[e:].iloc[0]).values) for e in ep])  # log相対
T=[int(p.argmin()) for p in P];M=[p.min() for p in P]
sxd=np.log(sx).diff();ANC="2026-11-25"
out={"anchor":ANC,"episodes":[str(e.date()) for e in ep],"stocks":{}}
for t,n in {"285A.T":"キオクシア","4062.T":"イビデン","6857.T":"アドバンテスト"}.items():
    p=g(t,"2y");r=np.log(p).diff();x=sxd.shift(1).reindex(r.index)
    df=pd.concat([r,x],axis=1).dropna().iloc[-120:];b=float(np.cov(df.iloc[:,0],df.iloc[:,1])[0,1]/np.var(df.iloc[:,1]))
    p0=float(p[:ANC].iloc[-1]);paths=p0*np.exp(b*P)
    q={k:[round(float(v)) for v in np.percentile(paths,pc,axis=0)] for k,pc in [("p10",10),("p25",25),("p50",50),("p75",75),("p90",90)]}
    tq=[int(v) for v in np.percentile(T,[25,50,75])];mq=[round(p0*np.exp(b*v)) for v in np.percentile(M,[25,50,75])]
    out["stocks"][n]={"t":t,"beta":round(b,2),"p0":round(p0),"hi":round(float(p[-250:].max())),"q":q,"trough_day":tq,"trough_px":mq}
    print(n,"β",round(b,2),"起点",round(p0),"底の日(25/50/75)",tq,"底値(厳/中/軽)",mq)
json.dump(out,open("data/stock_fan.json","w"),ensure_ascii=False)
