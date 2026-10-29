"""検証37：米大型株が時間外で急落（翌日の寄り付きが前日終値比−5%以下）した日、東京（その日）の半導体株・日経はどう動いたか。前半(〜2011)/後半(2012〜)。"""
import warnings; import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
US = ["GOOGL","NVDA","MSFT","AAPL","AMZN","META","INTC","AMD","AVGO","QCOM","MU","TXN","AMAT","LRCX","KLAC","ORCL","CSCO","IBM"]
JP = {"東京エレクトロン":"8035.T","アドバンテスト":"6857.T","日経":"^N225"}
def d(t): x=yf.download(t,start="2000-01-01",auto_adjust=False,progress=False); x.columns=[c[0] if isinstance(c,tuple) else c for c in x.columns]; x.index=pd.to_datetime(x.index).tz_localize(None); return x
jp={k:d(v)["Close"] for k,v in JP.items()}
jr={k:v.pct_change() for k,v in jp.items()}
ev=[]
for t in US:
    x=d(t)
    if len(x)<100: continue
    gap=x["Open"]/x["Close"].shift(1)-1
    for day,g in gap[gap<=-0.05].items(): ev.append((day,t,g))
ev=pd.DataFrame(ev,columns=["day","t","gap"]).sort_values("day")
mid=pd.Timestamp("2012-01-01")
for nm,m in (("前半",ev.day<mid),("後半",ev.day>=mid)):
    e=ev[m]; print(f"\n{nm}: 急落 {len(e)}件")
    for k,r in jr.items():
        v=[]
        for day in e.day.unique():
            # 東京の同じ日付（米国の寄り付きより前に東京が取引）
            if day in r.index and pd.notna(r[day]): v.append(r[day])
        v=pd.Series(v); allr=r[(r.index<mid) if nm=="前半" else (r.index>=mid)].dropna()
        print(f"  {k}: 平均{v.mean()*100:+.2f}%（全日{allr.mean()*100:+.2f}%） 下落の割合{(v<0).mean()*100:.0f}%（全日{(allr<0).mean()*100:.0f}%） −3%以下 {(v<=-.03).mean()*100:.0f}%（全日{(allr<=-.03).mean()*100:.0f}%） n={len(v)}")
print("\n直近10件:"); print(ev.tail(10).to_string())
