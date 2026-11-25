# 検証95：信用評価損益率（週次・約25年）は暴落の深さ・底を予測出来るか
import requests,re,pandas as pd,numpy as np,yfinance as yf,io,time
rows=[]
for n in range(1,15):
    u="https://www.traders.co.jp/margin_derivatives/margin_transition"+("" if n==1 else f"/{n}")
    try:
        h=requests.get(u,timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
        for t in pd.read_html(io.StringIO(h)):
            if any("損益率" in str(c) for c in t.columns.to_flat_index()): rows.append(t)
    except Exception as e: print("page",n,e)
    time.sleep(1)
df=pd.concat(rows);df.columns=[" ".join(map(str,c)) if isinstance(c,tuple) else str(c) for c in df.columns]
dc=[c for c in df.columns if "申込日" in c][0];ec=[c for c in df.columns if "損益率" in c][0]
m=pd.DataFrame({"date":pd.to_datetime(df[dc],errors="coerce"),"er":pd.to_numeric(df[ec],errors="coerce")}).dropna().drop_duplicates("date").sort_values("date").set_index("date")["er"]
m.to_csv("data/margin_weekly.csv");print("週数",len(m),m.index[0].date(),"〜",m.index[-1].date(),"最新",m.iloc[-1])
nk=yf.download("^N225",period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();nk.index=nk.index.tz_localize(None)
w=nk.resample("W-FRI").last().reindex(m.index,method="ffill")
hi=nk.cummax().resample("W-FRI").last().reindex(m.index,method="ffill");dd=(w/hi-1)*100
def fwd(i,k): return (w.iloc[i+k]/w.iloc[i]-1)*100 if i+k<len(w) else np.nan
def further(i,k=26):
    seg=w.iloc[i:i+k+1];return (seg.min()/w.iloc[i]-1)*100
print("\n全週の基準：4週後中央値 %+.1f%% 13週後 %+.1f%% 26週後 %+.1f%%"%tuple(np.nanmedian([fwd(i,k) for i in range(len(w))]) for k in (4,13,26)))
sel=[i for i in range(len(w)) if dd.iloc[i]<=-15]
print("日経が高値−15%%以下の週（比較用・%d週）：13週後中央値 %+.1f%% 26週内の追加下げ中央値 %.1f%%"%(len(sel),np.nanmedian([fwd(i,13) for i in sel]),np.nanmedian([further(i) for i in sel])))
for X in (-15,-20,-25):
    ev=[i for i in range(13,len(m)) if m.iloc[i]<=X and (m.iloc[i-13:i]>X).all()]
    print(f"\n== 評価損益率が {X}% 以下に初めて入った週（{len(ev)}回）")
    for i in ev:
        print(f"  {m.index[i].date()} 率{m.iloc[i]:.1f} 日経高値から{dd.iloc[i]:.1f}% → 4週{fwd(i,4):+.1f} 13週{fwd(i,13):+.1f} 26週{fwd(i,26):+.1f} ／26週内の追加下げ{further(i):.1f}% 率の最悪{m.iloc[i:i+27].min():.1f}")
    f13=[fwd(i,13) for i in ev];fu=[further(i) for i in ev]
    print(f"  13週後プラス {sum(x>0 for x in f13 if x==x)}/{sum(x==x for x in f13)} 中央値{np.nanmedian(f13):+.1f}% ／追加下げ−10%超 {sum(x<=-10 for x in fu)}/{len(fu)} 中央値{np.nanmedian(fu):.1f}%")
