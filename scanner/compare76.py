# 検証76：線（日経の1年高値からの下落率）を変えたときの感度。今日の形・潮目の変化・その両方で、250日以内に届いた割合
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");nq=g("^IXIC").reindex(sp.index).ffill();sx=g("^SOX").reindex(sp.index).ffill();vx=g("^VIX").reindex(sp.index).ffill();nk=g("^N225").reindex(sp.index).ffill()
a=nk.values;H=250;mn=np.full(len(a),np.nan)
for i in range(250,len(a)-H): mn[i]=a[i:i+H].min()/a[i-250:i+1].max()-1
mn=pd.Series(mn,index=nk.index);nkdd=nk/nk.rolling(250).max()-1
pk=lambda s:s.rolling(250,min_periods=120).apply(lambda w:len(w)-1-np.argmax(w),raw=True)
turn=(pk(sp)<=70)&(pk(nq)<=70)&(sp<sp.rolling(200).mean())&(nq<nq.rolling(200).mean())
A=(sx/sx.shift(5)-1<=-0.15)&(vx>=30)
NOW=nkdd.between(-0.25,-0.15)   # 日経がすでに高値から−15〜−25%（今と同じ位置）
def ep(m):
    d=m[m.fillna(False)].index;out=[];prev=None
    for x in d:
        if prev is None or (x-prev).days>90: out.append(x)
        prev=x
    return out
for k,m in {"今日の形":A,"潮目の変化":turn,"潮目＋今日の形":turn&A,"日経が高値から−15〜−25%にいる日（今と同じ位置）":NOW,"ふだん":nk.notna()}.items():
    e=[x for x in ep(m) if not np.isnan(mn.get(x,np.nan))] if k!="ふだん" else None
    line=f"{k}: "
    for th in [-0.30,-0.35,-0.40,-0.50]:
        if e is None: v=(mn.dropna()<=th).mean()*100;line+=f" {int(th*100)}%:{v:.0f}%"
        else: hits=[x for x in e if mn[x]<=th];line+=f" {int(th*100)}%:{len(hits)}/{len(e)}"
    print(line)
    if e: print("   −30%に届いた局面:",[str(x.date()) for x in e if mn[x]<=-0.30])
