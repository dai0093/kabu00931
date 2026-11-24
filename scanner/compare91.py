# 検証91：予測の幅（ファンチャート）。今日の形（SOX5日≤−15%・VIX≥30）の過去11局面の、その後250営業日の値動きを今の値に当てはめる
import yfinance as yf, pandas as pd, numpy as np, json
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");sx=g("^SOX").reindex(sp.index).ffill();vx=g("^VIX").reindex(sp.index).ffill()
A=((sx/sx.shift(5)-1<=-0.15)&(vx>=30)).fillna(False)
ep=[];prev=None
for x in A[A].index:
    if prev is None or (x-prev).days>90: ep.append(x)
    prev=x
ep=[e for e in ep if e<pd.Timestamp("2026-01-01")]
H=250;out={"episodes":[str(e.date()) for e in ep],"idx":{}}
for t,nm in [("^N225","日経平均"),("^GSPC","S&P500"),("^IXIC","NASDAQ")]:
    s=g(t);P=[];T=[]
    for e in ep:
        w=s[e:].iloc[:H+1]
        if len(w)<H+1: continue
        r=(w.values/w.values[0]-1)*100;P.append(r);T.append(int(np.argmin(r)))
    P=np.array(P);q=np.percentile(P,[10,25,50,75,90],axis=0)
    last=float(s.iloc[-1]);d0=str(s.index[-1].date())
    hi=float(s[-260:].max())
    days=pd.bdate_range(s.index[-1]+pd.Timedelta(days=1),periods=H)
    out["idx"][nm]={"last":last,"date":d0,"hi":hi,"dates":[d0]+[str(d.date()) for d in days],
       "q":{k:[round(last*(1+v/100)) for v in q[i]] for i,k in enumerate(["p10","p25","p50","p75","p90"])},
       "trough_days":T,"n":len(P),"lehman":[round(last*(1+v/100)) for v in P[[i for i,e in enumerate(ep) if str(e.date())=="2008-10-07"][0]]] if any(str(e.date())=="2008-10-07" for e in ep) else None}
    tq=np.percentile(T,[25,50,75]);mins=P.min(axis=1)
    print(f"== {nm} 今{last:,.0f}（{d0}）・1年高値{hi:,.0f}から{(last/hi-1)*100:.1f}%・事例{len(P)}")
    for k in [20,60,120,250]:
        print(f"  {k}営業日後（{days[k-1].date()}）: 中央値{last*(1+q[2][k]/100):,.0f}（{q[2][k]:+.1f}%） 幅25-75% {last*(1+q[1][k]/100):,.0f}〜{last*(1+q[3][k]/100):,.0f}  10-90% {last*(1+q[0][k]/100):,.0f}〜{last*(1+q[4][k]/100):,.0f}")
    print(f"  最安値までの日数 中央値{int(tq[1])}（25-75%:{int(tq[0])}〜{int(tq[2])}）→ {days[int(tq[1])-1].date() if tq[1]>0 else d0}（{days[max(0,int(tq[0])-1)].date()}〜{days[int(tq[2])-1].date()}）")
    print(f"  250日の間の最安 中央値{np.median(mins):+.1f}%（{last*(1+np.median(mins)/100):,.0f}）・25%{np.percentile(mins,25):+.1f}%・75%{np.percentile(mins,75):+.1f}%")
json.dump(out,open("data/forecast_fan.json","w"),ensure_ascii=False)
