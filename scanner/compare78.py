# 検証78：今日の形（SOX5日≤−15%・VIX≥30）の過去11局面で、日経の「底までの日数」と「戻るまでの日数」
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");sx=g("^SOX").reindex(sp.index).ffill();vx=g("^VIX").reindex(sp.index).ffill();nk=g("^N225")
A=((sx/sx.shift(5)-1<=-0.15)&(vx>=30)).fillna(False)
ep=[];prev=None
for x in A[A].index:
    if prev is None or (x-prev).days>90: ep.append(x)
    prev=x
R=[]
for st in ep:
    s=nk[st:];
    if len(s)<30: print(st.date(),"（今回・結果なし）");continue
    s0=s.iloc[0];hi=nk[:st].iloc[-250:].max()
    w=s.iloc[:750];tr=w.idxmin();td=int(np.busday_count(st.date(),tr.date()));dd=(w.min()/s0-1)*100
    after=s[tr:];back0=after[after>=s0];back_hi=after[after>=hi]
    b0=int(np.busday_count(tr.date(),back0.index[0].date())) if len(back0) else None
    bh=int(np.busday_count(tr.date(),back_hi.index[0].date())) if len(back_hi) else None
    R.append((td,dd,b0,bh))
    print(f"{st.date()}: 底まで{td}営業日（さらに{dd:.1f}%）→ 起点の値に戻るまで底から{b0 if b0 is not None else '未'}営業日 → 1年高値に戻るまで底から{bh if bh is not None else '未'}営業日")
t=[r[0] for r in R];b=[r[2] for r in R if r[2] is not None];h=[r[3] for r in R if r[3] is not None]
print(f"底まで：中央値{int(np.median(t))}営業日（範囲{min(t)}〜{max(t)}）")
print(f"起点の値に戻るまで（底から）：中央値{int(np.median(b))}営業日（範囲{min(b)}〜{max(b)}、戻った{len(b)}/{len(R)}）")
print(f"1年高値に戻るまで（底から）：中央値{int(np.median(h))}営業日（範囲{min(h)}〜{max(h)}、戻った{len(h)}/{len(R)}）")
