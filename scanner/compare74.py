import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");nq=g("^IXIC").reindex(sp.index).ffill();sx=g("^SOX").reindex(sp.index).ffill();vx=g("^VIX").reindex(sp.index).ffill();nk=g("^N225").reindex(sp.index).ffill()
def fut(s,H=250):
    a=s.values;o=np.full(len(a),np.nan)
    for i in range(len(a)-H):o[i]=a[i:i+H].min()/a[max(0,i-250):i+1].max()-1
    return pd.Series(o,index=s.index)
leh=((fut(sp)<=-0.40)|(fut(nk)<=-0.50)).astype(float);leh[fut(sp).isna()]=np.nan
def since_peak(s):
    r=s.rolling(250,min_periods=120);pk=s.rolling(250,min_periods=120).apply(lambda w:len(w)-1-np.argmax(w),raw=True);return pk
spk=since_peak(sp);nqk=since_peak(nq)
turn=(spk<=70)&(nqk<=70)&(sp<sp.rolling(200).mean())&(nq<nq.rolling(200).mean())
A=(sx/sx.shift(5)-1<=-0.15)&(vx>=30)
def ep(m):
    d=m[m.fillna(False)].index;out=[];prev=None
    for x in d:
        if prev is None or (x-prev).days>90: out.append(x)
        prev=x
    return out
for k,m in {"潮目の変化だけ（高値70日以内に両指数が200日線割れ）":turn,"潮目の変化＋今日の形":turn&A}.items():
    e=ep(m);ey=[leh.get(x) for x in e if not np.isnan(leh.get(x,np.nan))];y=leh[m.fillna(False)].dropna()
    print(f"{k}: 局面{len(e)} → リーマン級 {int(sum(ey))}/{len(ey)}（{np.mean(ey)*100 if ey else float('nan'):.0f}%）・日数ベース{y.mean()*100 if len(y) else float('nan'):.0f}%")
    print("   ",[f"{x.date()}{'★' if leh.get(x)==1 else ''}" for x in e])
print("ふだん",round(leh.dropna().mean()*100,1),"%")
