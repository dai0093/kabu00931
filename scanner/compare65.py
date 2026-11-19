# 検証65：今と同じ状態（S&P500が200日線の下、社債20日が−0.5〜+0.5%）から、
# ①社債(HYG÷IEF)20日≤−2% ②銀行ETF(1615)1日≤−4% に何営業日で届いたか。前半(〜2011)・後半(2012〜)
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
hy,ie,sp,bk=g("HYG"),g("IEF"),g("^GSPC"),g("1615.T")
r=(hy/ie).dropna();c20=(r/r.shift(20)-1)*100
below=(sp<sp.rolling(200).mean()).reindex(c20.index).fillna(False)
st=(c20.between(-0.5,0.5))&below
b1=(bk.pct_change()*100).reindex(c20.index,method=None)
hitC=(c20<=-2);hitB=(b1<=-4).fillna(False)
def wait(h,i,n=60):
    w=h.iloc[i+1:i+1+n];idx=np.where(w.values)[0];return idx[0]+1 if len(idx) else None
for per,s,e in [("前半","2007","2011"),("後半","2012","2026-09-30")]:
    days=[i for i,d in enumerate(c20.index) if st.iloc[i] and s<=str(d.year)<=e[:4]]
    for nm,h in [("社債20日≤−2%",hitC),("銀行1日≤−4%",hitB)]:
        w=[wait(h,i) for i in days];hit=[x for x in w if x];n=len(w)
        print(per,nm,"n",n,"20日以内",round(sum(1 for x in hit if x<=20)/n*100,1) if n else '-',"%","60日以内",round(len(hit)/n*100,1) if n else '-',"%","届いた時の中央値",int(np.median(hit)) if hit else '-',"日")
