# 検証77：動画の主張の確認。高値から−20%を割った日（その高値を取り戻すまでは1回）から、さらにどこまで下げたか。S&P500とSOX、日経
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
def study(s,name,start="1980-01-01"):
    s=s[start:];pk=s.cummax();out=[];armed=True;i=0;v=s.values;P=pk.values;idx=s.index
    while i<len(v):
        if v[i]>=P[i]: armed=True
        if armed and v[i]<=P[i]*0.8:
            armed=False;j=i
            # 次に高値を取り戻すまでの最安
            k=i
            while k<len(v) and v[k]<P[i]: k+=1
            seg=v[i:k];m=seg.min();mi=i+int(np.argmin(seg))
            out.append((idx[i].date(),round((m/v[i]-1)*100,1),int(mi-i),"未回復" if k>=len(v) else ""))
        i+=1
    print(f"== {name}（高値から−20%を割った日 → その後の最安まで、高値を取り戻すまでで区切る）")
    for d,dd,n,f in out: print(f"   {d}: さらに{dd}%・{n}営業日後に底 {f}")
    vals=[x[1] for x in out if x[3]==""]
    if vals:
        a=sum(1 for x in vals if x>-10);b=sum(1 for x in vals if -34<x<=-10);c=sum(1 for x in vals if x<=-34)
        print(f"   区分（完了分{len(vals)}回）：さらに−10%以内 {a}回 ／ −10〜−34% {b}回 ／ −34%以上 {c}回")
study(g("^GSPC"),"S&P500");study(g("^N225"),"日経平均");study(g("^SOX"),"SOX",start="1994-01-01")
