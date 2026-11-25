# 検証94：REIT・米国債・日本国債の売買ルール。持ち続け／200日線／1年モメンタム／月末10か月線。5年ごとの区間すべてで比較（傾向）
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
A={"米REIT(VNQ)":"VNQ","米不動産(IYR)":"IYR","J-REIT(1343)":"1343.T","米国債7-10年(IEF)":"IEF","米国債20年(TLT)":"TLT","日本国債(2510)":"2510.T"}
def stats(r):
    r=r.dropna();
    if len(r)<120: return None
    eq=(1+r).cumprod();yrs=len(r)/252;cagr=eq.iloc[-1]**(1/yrs)-1;dd=(eq/eq.cummax()-1).min()
    return cagr*100,dd*100,(cagr/abs(dd) if dd<0 else np.nan)
def rules(p):
    r=p.pct_change()
    ma=p.rolling(200).mean();s1=(p>ma).shift(1)
    mo=(p/p.shift(252)-1>0).shift(1)
    m=p.resample("ME").last();m10=m.rolling(10).mean();sig=(m>m10).reindex(p.index,method="ffill").shift(1)
    return {"持ち続け":r,"200日線":r.where(s1==True,0.0),"1年モメンタム":r.where(mo==True,0.0),"10か月線(月末)":r.where(sig==True,0.0)}
for nm,t in A.items():
    p=g(t);R=rules(p);st=p.index[260]
    print(f"== {nm}（{st.date()}〜{p.index[-1].date()}）")
    for k,r in R.items():
        s=stats(r[st:]);print(f"   {k}: 年率{s[0]:+.1f}% 最大下げ{s[1]:.1f}% 比{s[2]:.2f}")
    # 5年区間ごと
    yrs=list(range(st.year,p.index[-1].year+1,5));wins={k:0 for k in R if k!="持ち続け"};dds={k:0 for k in wins};n=0
    for y in yrs:
        a,b=f"{y}-01-01",f"{y+4}-12-31"
        base=stats(R["持ち続け"][a:b])
        if not base: continue
        n+=1;line=f"   {y}-{y+4}: 持ち続け 年率{base[0]:+.1f}/下げ{base[1]:.1f}"
        for k in wins:
            s=stats(R[k][a:b]);line+=f" | {k} {s[0]:+.1f}/{s[1]:.1f}"
            if s[2]>base[2] or (np.isnan(base[2])): wins[k]+=1
            if s[1]>base[1]: dds[k]+=1
        print(line)
    print("   区間数",n,"比(年率÷下げ)が良くなった区間:",wins,"最大下げが小さくなった区間:",dds)
