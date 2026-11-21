# 検証80：時間の伸縮（倍率k=0.4〜2.5）で近似が向上するか。暴落7例と、比較用の「普通の期間」60個で同じ処理をし、暴落だけが特に合うかを確かめる
import yfinance as yf, pandas as pd, numpy as np, json
n=yf.download("^N225",period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();n.index=pd.to_datetime(n.index).tz_localize(None)
cur=n["2026-06-25":];c=(cur/cur.iloc[0]-1).values*100;L=len(c)
cases={"ITバブル2000":"2000-04-12","リーマン2007":"2007-07-09","2015チャイナ":"2015-06-24","2018":"2018-10-02","コロナ2020":"2020-01-17","2024年8月":"2024-07-11","1990バブル":"1989-12-29"}
K=np.round(np.arange(0.4,2.51,0.05),2)
def fit(d):
    s=n[d:];s=(s/s.iloc[0]-1).values*100;best=(9e9,None)
    for k in K:
        need=int(np.ceil(L*k))+1
        if need>len(s):continue
        x=np.arange(L)*k;y=np.interp(x,np.arange(len(s)),s)
        r=np.sqrt(np.mean((y-c)**2))
        if r<best[0]:best=(r,k)
    r1=np.sqrt(np.mean((s[:L]-c)**2)) if len(s)>=L else np.nan
    return r1,best[0],best[1],s
print(f"今回：高値6/25から{L}営業日、今{c[-1]:.1f}%")
out={}
for k,d in cases.items():
    r1,rb,kb,s=fit(d)
    nxt=None
    if kb:
        pos=L*kb;fut=s[int(pos):int(pos+60*kb)+1]
        nxt=(fut.min()-s[int(pos)]) if len(fut) else None
        out[k]={"k":float(kb),"curve":[round(float(np.interp(i*kb,np.arange(len(s)),s)),2) for i in range(int(min((len(s)-1)/kb,L+120)))]}
    print(f"{k}: 伸縮なし ずれ{r1:.1f} → 最良の倍率{kb}（{'遅く進む' if kb and kb<1 else '速く進む'}）で ずれ{rb:.1f}・その後60日分の最安（今の位置から）{nxt:+.1f}%" if nxt is not None else f"{k}: {r1:.1f} {rb:.1f} {kb}")
# 比較用：暴落ではない期間の開始日をランダムに60個
rng=np.random.default_rng(0);pool=n["1985":"2025-06"].index;ctrl=[]
crash_win=[("1989-06","1992-12"),("2000-01","2003-06"),("2007-06","2009-06"),("2015-05","2016-07"),("2018-09","2019-01"),("2020-01","2020-06"),("2024-06","2024-10")]
cand=[d for d in pool if not any(pd.Timestamp(a)<=d<=pd.Timestamp(b) for a,b in crash_win)]
for d in rng.choice(cand,60,replace=False):
    r1,rb,kb,_=fit(str(pd.Timestamp(d).date()));ctrl.append((r1,rb))
ctrl=np.array([x for x in ctrl if not np.isnan(x[0])])
print(f"比較用（普通の期間{len(ctrl)}個）：伸縮なし ずれ中央値{np.nanmedian(ctrl[:,0]):.1f}・最良{np.nanmin(ctrl[:,0]):.1f} ／ 伸縮あり 中央値{np.nanmedian(ctrl[:,1]):.1f}・最良{np.nanmin(ctrl[:,1]):.1f}")
print("伸縮ありで、普通の期間のうち暴落の最良例より合ったものの数：",{k:int((ctrl[:,1]<=fit(d)[1]).sum()) for k,d in cases.items()})
json.dump(out,open("data/crash_warp.json","w"),ensure_ascii=False)
