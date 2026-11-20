# 検証70：信用の数字だけで「似た局面」を探す類似予測のウォークフォワード検証（検証69の株価版との比較）
import yfinance as yf, pandas as pd, numpy as np, json
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
nk=g("^N225");S={t:g(t) for t in ["HYG","IEF","LQD","KRE","XLF","BX","1615.T","^GSPC","^SOX"]}
D=pd.DataFrame({k:v for k,v in S.items()}).reindex(nk.index).ffill();D["nk"]=nk;D=D.dropna()
hy=D.HYG/D.IEF;ig=D.LQD/D.IEF
C=pd.DataFrame(index=D.index)
C["hy20"]=hy/hy.shift(20)-1;C["hy60"]=hy/hy.shift(60)-1;C["ig20"]=ig/ig.shift(20)-1
C["kre_dd"]=D.KRE/D.KRE.rolling(250).max()-1;C["kre20"]=D.KRE/D.KRE.shift(20)-1
C["xlf20"]=D.XLF/D.XLF.shift(20)-1;C["bx_dd"]=D.BX/D.BX.rolling(250).max()-1;C["bx5"]=D.BX/D.BX.shift(5)-1
C["jbk_dd"]=D["1615.T"]/D["1615.T"].rolling(250).max()-1;C["jbk20"]=D["1615.T"]/D["1615.T"].shift(20)-1
P=pd.DataFrame(index=D.index)
P["dd"]=D.nk/D.nk.rolling(250).max()-1;P["r20"]=D.nk/D.nk.shift(20)-1;P["ma"]=D.nk/D.nk.rolling(200).mean()-1
P["spma"]=D["^GSPC"]/D["^GSPC"].rolling(200).mean()-1;P["sxdd"]=D["^SOX"]/D["^SOX"].rolling(250).max()-1
fut=(D.nk[::-1].rolling(60,min_periods=60).min()[::-1].shift(-1)/D.nk-1)
def run(F,name,K=30):
    F=F.dropna();Y=(fut.reindex(F.index)<=-0.10).astype(float);Y[fut.reindex(F.index).isna()]=np.nan
    X=((F-F.mean())/F.std()).values;idx=F.index;p=[];b=[];y=[];dt=[]
    for i in range(0,len(idx),3):
        if np.isnan(Y.iloc[i]):continue
        c=np.arange(0,i-60);c=c[~np.isnan(Y.values[c])]
        if len(c)<400:continue
        d=np.sqrt(((X[c]-X[i])**2).sum(1));nn=c[np.argsort(d)[:K]]
        p.append(Y.values[nn].mean());b.append(Y.values[c].mean());y.append(Y.values[i]);dt.append(idx[i])
    p,b,y=map(np.array,(p,b,y));bs=lambda q:np.mean((q-y)**2);q=np.quantile(p,0.9)
    print(f"[{name}] 期間{dt[0].date()}〜 日数{len(y)} 起きた割合{y.mean()*100:.1f}% Brier改善{(1-bs(p)/bs(b))*100:.1f}% 上位10%日の発生率{y[p>=q].mean()*100:.1f}% 下位50%日{y[p<=np.median(p)].mean()*100:.1f}%")
    T=pd.DataFrame({"p":p,"y":y,"b":b},index=dt)
    for a,z in [("2010","2014"),("2015","2019"),("2020","2026")]:
        s=T[a:z]
        if len(s):print(f"   {a}〜{z} Brier改善{(1-np.mean((s.p-s.y)**2)/np.mean((s.b-s.y)**2))*100:.1f}% 上位10%日の発生率{(s.y[s.p>=q].mean()*100 if (s.p>=q).sum() else float('nan')):.1f}%（{int((s.p>=q).sum())}日） ふだん{s.y.mean()*100:.1f}%")
    i=len(idx)-1;c=np.arange(0,i-60);c=c[~np.isnan(Y.values[c])];d=np.sqrt(((X[c]-X[i])**2).sum(1));nn=c[np.argsort(d)[:K]]
    print(f"   今日{idx[i].date()} 予測{Y.values[nn].mean()*100:.1f}%（上位10%の線{q*100:.1f}%） 似た日",sorted({str(idx[j].date())[:7] for j in nn}))
    return Y.values[nn].mean()
run(C,"信用だけ");run(pd.concat([C,P],axis=1),"信用＋株価");run(P,"株価だけ（同じ期間）")
