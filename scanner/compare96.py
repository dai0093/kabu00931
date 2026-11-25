# 検証96：事前登録5条件を基準日からの累計で測る（6/25・10/2）＋リーマン時の同じ経過日数と比較
import yfinance as yf,pandas as pd,numpy as np
T=["HYG","IEF","LQD","KRE","^VIX","^N225","^SOX","1615.T","^GSPC"]
d=yf.download(T,start="2007-01-01",progress=False,auto_adjust=True)["Close"];d.index=d.index.tz_localize(None);d=d.ffill()
hy=d.HYG/d.IEF;ig=d.LQD/d.IEF
def at(s,a,b):
    s=s.dropna();a=s.index[s.index.get_indexer([pd.Timestamp(a)],method="bfill")[0]];return a,(s[:b].iloc[-1]/s[a]-1)*100,(s[a:b].min()/s[a]-1)*100
def show(lab,a,b):
    print(f"\n== {lab}：{a} → {b}")
    for n,s in [("社債 HYG÷IEF",hy),("投資適格 LQD÷IEF",ig),("米地銀 KRE",d.KRE),("日本の銀行 1615",d["1615.T"]),("日経平均",d["^N225"]),("SOX",d["^SOX"]),("S&P500",d["^GSPC"])]:
        try:
            a0,now,mn=at(s,a,b);print(f"  {n}: 今 {now:+.1f}% ／ 期間中の最悪 {mn:+.1f}%")
        except Exception as e: print(" ",n,e)
    v=d["^VIX"][a:b];print(f"  VIX: 今 {v.iloc[-1]:.1f} ／ 期間中の最高 {v.max():.1f}")
today=d.index[-1]
show("6/25基準","2026-06-25",today)
show("10/2基準","2026-10-02",today)
n1=len(d["2026-06-25":today]);n2=len(d["2026-10-02":today])
# リーマン：株の高値 2007-10-09 から同じ営業日数
i0=d.index.get_indexer([pd.Timestamp("2007-10-09")],method="bfill")[0]
show(f"リーマン 2007-10-09基準・同じ{n1}営業日後",d.index[i0].date(),d.index[i0+n1-1])
show("参考 リーマン 2007-10-09基準・2008-09-12（破綻直前）",d.index[i0].date(),"2008-09-12")
show("参考 リーマン 2007-10-09基準・2008-11-20（底近く）",d.index[i0].date(),"2008-11-20")
