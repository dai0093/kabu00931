# 検証71：SOXが1年高値から−30%を割った日（起点）にそろえ、その後の波及（日経・銀行・金融・社債・守りの業種）の追加下落と、底までの日数を事例ごとに並べる
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sox=g("^SOX");A={"日経":"^N225","S&P500":"^GSPC","米金融XLF":"XLF","米地銀KRE":"KRE","社債HYG÷IEF":None,"米不動産IYR":"IYR","生活必需品XLP":"XLP","公益XLU":"XLU"}
S={k:g(v) for k,v in A.items() if v};hy=g("HYG")/g("IEF").reindex(g("HYG").index).ffill();S["社債HYG÷IEF"]=hy.dropna()
dd=sox/sox.rolling(250,min_periods=120).max()-1
ev=[];last=None
for d,v in dd.items():
    if v<=-0.30 and (last is None or (d-last).days>365):
        ev.append(d);last=d
    if v<=-0.30: last=d if last is None else last
starts=[];prev=pd.Timestamp("1900-01-01")
for d in dd[dd<=-0.30].index:
    if (d-prev).days>400: starts.append(d)
    prev=d
peakd=lambda d:sox[:d][-250:].idxmax()
print("事例（SOX−30%到達日）",[str(d.date()) for d in starts])
H=180
rows=[]
for st in starts:
    pk=peakd(st);r={"起点":str(st.date()),"SOX高値":str(pk.date()),"高値→起点日数":int(np.busday_count(pk.date(),st.date()))}
    for k,s in S.items():
        if st<s.index[0]+pd.Timedelta(days=30): r[k]=None;continue
        s0=s[:st].iloc[-1];w=s[st:][:H];
        if len(w)<20: r[k]=None;continue
        tr=w.idxmin();r[k]=(round((w.min()/s0-1)*100,1),int(np.busday_count(st.date(),tr.date())))
    sw=sox[st:][:H];r["SOX"]=(round((sw.min()/sox[:st].iloc[-1]-1)*100,1),int(np.busday_count(st.date(),sw.idxmin().date())))
    rows.append(r)
for r in rows:
    print("---",r["起点"],"（SOX高値",r["SOX高値"],"から",r["高値→起点日数"],"営業日）")
    for k in ["SOX"]+list(S):
        v=r.get(k);print(f"   {k}: " + ("データなし" if v is None else f"起点からさらに最安{v[0]}%・底まで{v[1]}営業日"))
print("=== 中央値（データのある事例）")
for k in ["SOX"]+list(S):
    vs=[r[k] for r in rows if r.get(k)]
    if vs: print(f"   {k}: さらに最安 中央値{np.median([v[0] for v in vs]):.1f}%（範囲{min(v[0] for v in vs)}〜{max(v[0] for v in vs)}）・底まで中央値{int(np.median([v[1] for v in vs]))}営業日（範囲{min(v[1] for v in vs)}〜{max(v[1] for v in vs)}） n={len(vs)}")
cur=[d for d in starts if d.year==2026];print("今回の起点",cur)
if cur:
    st=cur[-1];print("今回 起点から今日まで営業日",int(np.busday_count(st.date(),sox.index[-1].date())))
    for k,s in S.items():
        s0=s[:st].iloc[-1];print(f"   今回 {k}: 起点から今まで{(s.iloc[-1]/s0-1)*100:+.1f}%・その間の最安{(s[st:].min()/s0-1)*100:+.1f}%")
