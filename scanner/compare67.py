# 検証67：今回（2026年の高値から）と、実際の過去の暴落（高値から）の日経の曲線を、高値からの営業日数でそろえて比べる
import yfinance as yf, pandas as pd, numpy as np, json
n=yf.download("^N225",period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();n.index=pd.to_datetime(n.index).tz_localize(None)
cur=n["2026-01-01":];p=cur.idxmax();c=(cur[p:]/cur[p]-1)*100;L=len(c)
print("今回の高値",p.date(),round(cur[p]),"営業日数",L,"今",round(c.iloc[-1],1))
cases={"ITバブル2000":"2000-04-12","リーマン2007":"2007-07-09","2015チャイナ":"2015-06-24","2018":"2018-10-02","コロナ2020":"2020-01-17","2024年8月":"2024-07-11","1990バブル":"1989-12-29"}
out={"cur":[round(x,2) for x in c]}
for k,d in cases.items():
    s=n[d:];s=(s/s.iloc[0]-1)*100
    a=s.iloc[:L].values;b=c.values[:len(a)]
    rmse=np.sqrt(np.mean((a-b)**2));corr=np.corrcoef(a,b)[0,1]
    out[k]=[round(x,2) for x in s.iloc[:L+60]]
    print(k,"同じ日数での位置",round(a[-1],1),"%","ずれ(RMSE)",round(rmse,1),"相関",round(corr,2),"その後60日の最安",round(s.iloc[L:L+60].min(),1),"％ 60日後",round(s.iloc[min(L+59,len(s)-1)],1))
json.dump(out,open("data/crash_overlay.json","w"),ensure_ascii=False)
