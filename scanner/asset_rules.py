# 検証94で選んだルールの今日の状態：J-REIT/米REIT/日本国債=月末10か月線、米国債=1年モメンタム
import yfinance as yf, pandas as pd, json, datetime as dt
def g(t):
    d=yf.download(t,period="3y",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
out={"updatedAt":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),"items":[]}
for name,t,rule in [("J-REIT","1343.T","m10"),("米REIT","IYR","m10"),("米国債","IEF","mom"),("日本国債","2510.T","m10")]:
    try:
        p=g(t);last=float(p.iloc[-1])
        if rule=="m10":
            m=p.resample("ME").last();today=p.index[-1]
            mc=m[m.index<=today]  # 確定した月末だけ
            m10=float(mc.iloc[-10:].mean());me=float(mc.iloc[-1])
            ok=me>m10;gap=(me/m10-1)*100;cur=(last/float(m.iloc[-10:].mean())-1)*100
            out["items"].append({"name":name,"ticker":t,"rule":"10か月線(月末)","ok":ok,"me_date":str(mc.index[-1].date()),"me":me,"m10":m10,"gap":round(gap,2),"now_gap":round(cur,2)})
        else:
            r=(last/float(p.iloc[-253])-1)*100
            out["items"].append({"name":name,"ticker":t,"rule":"1年モメンタム","ok":r>0,"r252":round(r,2)})
    except Exception as e: out["items"].append({"name":name,"ticker":t,"err":str(e)})
json.dump(out,open("data/asset_rules.json","w"),ensure_ascii=False,indent=1);print(json.dumps(out,ensure_ascii=False))
# 検証95：信用評価損益率（週次）
try:
    import requests,io
    h=requests.get("https://www.traders.co.jp/margin_derivatives/margin_transition",timeout=30,headers={"User-Agent":"Mozilla/5.0"}).text
    t=[x for x in pd.read_html(io.StringIO(h)) if any("損益率" in str(c) for c in x.columns.to_flat_index())][0]
    t.columns=[" ".join(map(str,c)) if isinstance(c,tuple) else str(c) for c in t.columns]
    dc=[c for c in t.columns if "申込日" in c][0];ec=[c for c in t.columns if "損益率" in c][0]
    s=pd.DataFrame({"d":pd.to_datetime(t[dc],errors="coerce"),"e":pd.to_numeric(t[ec],errors="coerce")}).dropna().sort_values("d")
    out["margin"]={"date":str(s.d.iloc[-1].date()),"er":float(s.e.iloc[-1]),"hist":[[str(a.date()),float(b)] for a,b in zip(s.d.iloc[-12:],s.e.iloc[-12:])]}
    json.dump(out,open("data/asset_rules.json","w"),ensure_ascii=False,indent=1);print("margin",out["margin"]["er"])
except Exception as e: print("margin失敗",e)
