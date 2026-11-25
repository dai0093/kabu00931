# AI関連の分野ごとの波及（毎日）。分野の中央値で、高値からの下落・20日・5日・1日を出し、状態と向きを判定。履歴を残す。
import yfinance as yf, pandas as pd, numpy as np, json, os
from datetime import datetime, timezone, timedelta
JST=timezone(timedelta(hours=9))
SEC=[
 ("半導体（AI計算）",{"NVDA":"エヌビディア","6857.T":"アドバンテスト","285A.T":"キオクシア","SNDK":"サンディスク","4062.T":"イビデン","MU":"マイクロン","TSM":"TSMC","AVGO":"ブロードコム"}),
 ("AIクラウド",{"CRWV":"CoreWeave","NBIS":"Nebius","ORCL":"オラクル"}),
 ("巨大IT",{"MSFT":"マイクロソフト","GOOGL":"アルファベット","AMZN":"アマゾン","META":"メタ"}),
 ("電力",{"VST":"ビストラ","CEG":"コンステレーション","NRG":"NRG","9501.T":"東京電力","9503.T":"関西電力"}),
 ("建設・電気工事",{"PWR":"クアンタ","EME":"エムコー","1942.T":"関電工","1944.T":"きんでん","1803.T":"清水建設"}),
 ("不動産・データセンター",{"EQIX":"エクイニクス","DLR":"デジタル・リアルティ","8801.T":"三井不動産","8802.T":"三菱地所","1343.T":"J-REIT"}),
 ("プライベートクレジット",{"BX":"ブラックストーン","APO":"アポロ","KKR":"KKR","ARES":"アレス","OWL":"ブルー・アウル","ARCC":"エイリス(BDC)"}),
 ("投資会社・証券",{"9984.T":"ソフトバンクG","8473.T":"SBI HD","GS":"ゴールドマン","MS":"モルガン・スタンレー"}),
 ("銀行",{"KRE":"米地方銀行","JPM":"JPモルガン","8306.T":"三菱UFJ","1615.T":"銀行ETF"}),
]
tick=[t for _,d in SEC for t in d]+["HYG","IEF","LQD"]
raw=yf.download(tick,period="14mo",progress=False,auto_adjust=True,group_by="ticker",threads=True)
def ser(t):
    try: s=raw[t]["Close"].dropna()
    except Exception: return None
    return s if len(s)>30 else None
def met(s):
    v=s.values;return {"last":float(v[-1]),"date":str(s.index[-1].date()),"d1":(v[-1]/v[-2]-1)*100,"d5":(v[-1]/v[-6]-1)*100,"p5":(v[-6]/v[-11]-1)*100,"d20":(v[-1]/v[-21]-1)*100,"dd":(v[-1]/s[-250:].max()-1)*100}
out={"updatedAt":datetime.now(JST).strftime("%Y-%m-%dT%H:%M+09:00"),"sectors":[]}
for nm,d in SEC:
    rows=[]
    for t,n in d.items():
        s=ser(t)
        if s is None: continue
        m=met(s);m.update({"t":t,"n":n});rows.append(m)
    if not rows: continue
    med=lambda k:float(np.median([r[k] for r in rows]))
    dd,d20,d5,p5,d1=med("dd"),med("d20"),med("d5"),med("p5"),med("d1")
    st="lit" if (dd<=-25 or d20<=-12) else "near" if (dd<=-12 or d20<=-6) else "ok"
    tr="改善" if d5>=3 else "悪化中" if d5<=-3 else "横ばい"
    out["sectors"].append({"name":nm,"state":st,"trend":tr,"dd":round(dd,1),"d20":round(d20,1),"d5":round(d5,1),"p5":round(p5,1),"d1":round(d1,1),
        "items":[{k:(round(r[k],1) if isinstance(r[k],float) and k!="last" else r[k]) for k in ("n","t","last","date","d1","d5","d20","dd")} for r in rows]})
# 信用（事前登録の条件用）
try:
    c={}
    for a,b,k in [("HYG","IEF","hy20"),("LQD","IEF","ig20")]:
        x=(ser(a)/ser(b)).dropna();c[k]=round((x.iloc[-1]/x.iloc[-21]-1)*100,2)
    v=yf.download("^VIX",period="1mo",progress=False,auto_adjust=True)["Close"].squeeze().dropna();c["vix"]=round(float(v.iloc[-1]),1);c["vix_prev"]=round(float(v.iloc[-2]),1)
    k=ser("KRE");c["kre_dd"]=round((k.iloc[-1]/k[-250:].max()-1)*100,1)
    out["credit"]=c
except Exception as e: print("credit失敗",e)
# 履歴
hp="data/sectors_hist.json";H=json.load(open(hp)) if os.path.exists(hp) else {}
day=datetime.now(JST).strftime("%Y-%m-%d");H[day]={s["name"]:{"state":s["state"],"dd":s["dd"],"d20":s["d20"]} for s in out["sectors"]}
H=dict(sorted(H.items())[-120:]);json.dump(H,open(hp,"w"),ensure_ascii=False)
json.dump(out,open("data/sectors.json","w"),ensure_ascii=False)
print("\n".join(f"{s['name']}: {s['state']} {s['trend']} 高値から{s['dd']}% 20日{s['d20']}% 5日{s['d5']}%" for s in out["sectors"]))
