# 検証92：個別株の下げの見積もり。SOXの過去11局面（今日の形）のその後250日の最安の分布 × 各銘柄のSOXへの感応度（直近120日、日次、時差を考え前日SOXと当日の銘柄）
import yfinance as yf, pandas as pd, numpy as np
def g(t,per="max"):
    d=yf.download(t,period=per,progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");sx=g("^SOX");vx=g("^VIX").reindex(sp.index).ffill();sxa=sx.reindex(sp.index).ffill()
A=((sxa/sxa.shift(5)-1<=-0.15)&(vx>=30)).fillna(False);ep=[];prev=None
for x in A[A].index:
    if prev is None or (x-prev).days>90: ep.append(x)
    prev=x
ep=[e for e in ep if e<pd.Timestamp("2026-01-01")]
mins=[];tdays=[]
for e in ep:
    w=sx[e:].iloc[:251];r=w/w.iloc[0]-1;mins.append(r.min());tdays.append(int(r.values.argmin()))
mins=np.array(mins);q25,q50,q75=np.percentile(mins,[25,50,75])
print(f"SOX 過去{len(ep)}局面のその後250日の最安（起点から）：中央値{q50*100:.1f}% 25%{q25*100:.1f}% 75%{q75*100:.1f}%  最安までの日数 中央値{int(np.median(tdays))}")
print("   各局面:",[f"{e.date()}:{m*100:.0f}%" for e,m in zip(ep,mins)])
sxd=np.log(sx).diff()
S={"285A.T":"キオクシア","4062.T":"イビデン","6857.T":"アドバンテスト","8035.T":"東京エレクトロン","6920.T":"レーザーテック","5803.T":"フジクラ","9984.T":"ソフトバンクG","200A.T":"日経半導体ETF","6146.T":"ディスコ","6526.T":"ソシオネクスト"}
print("銘柄｜今（日付）｜1年高値からの下落｜SOXへの感応度β｜見積もり：中央値／厳しめ(25%)／軽め(75%)")
for t,n in S.items():
    try:
        p=g(t,"2y");r=np.log(p).diff()
        x=sxd.shift(1).reindex(r.index)  # 米国の前夜→日本の当日
        df=pd.concat([r,x],axis=1).dropna().iloc[-120:];b=np.cov(df.iloc[:,0],df.iloc[:,1])[0,1]/np.var(df.iloc[:,1])
        last=p.iloc[-1];hi=p[-250:].max()
        est=lambda m:last*np.exp(b*np.log(1+m))
        print(f"{n}｜{last:,.0f}（{p.index[-1].date()}）｜{(last/hi-1)*100:.1f}%（高値{hi:,.0f}）｜β={b:.2f}｜{est(q50):,.0f}（{(est(q50)/last-1)*100:+.0f}%）／{est(q25):,.0f}（{(est(q25)/last-1)*100:+.0f}%）／{est(q75):,.0f}（{(est(q75)/last-1)*100:+.0f}%）")
    except Exception as e: print(n,"取得失敗",e)
