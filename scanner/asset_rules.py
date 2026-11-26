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
# 検証97：住宅・不動産（参考表示。判定には使わない）
try:
    def _g(t):
        d=yf.download(t,period="2y",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
    _dd=lambda s:round(float(s.iloc[-1]/s.tail(252).max()-1)*100,1)
    itb,xhb,j1343,nk_=_g("ITB"),_g("XHB"),_g("1343.T"),_g("^N225")
    j3=pd.concat([_g(t) for t in ("8801.T","8802.T","8830.T")],axis=1).dropna();j3=(j3/j3.iloc[0]).mean(axis=1)
    rel=lambda a,b:round(float(((a/b.reindex(a.index).ffill()).iloc[-1]/(a/b.reindex(a.index).ffill()).iloc[-61]-1)*100),1)
    H={"itb_dd":_dd(itb),"xhb_dd":_dd(xhb),"jp3_dd":_dd(j3),"jp3_rel60":rel(j3,nk_),"jreit_dd":_dd(j1343)}
    try:
        _r=requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DRSFRMACBS",timeout=30).text
        _t=pd.read_csv(io.StringIO(_r));_t.index=pd.to_datetime(_t.iloc[:,0]);_q=pd.to_numeric(_t.iloc[:,1],errors="coerce").dropna()
        H.update({"dq":float(_q.iloc[-1]),"dq_yoy":round(float(_q.iloc[-1]-_q.iloc[-5]),2),"dq_date":str(_q.index[-1].date())})
    except Exception as e: H["dq_err"]=str(e)
    out["housing"]=H;json.dump(out,open("data/asset_rules.json","w"),ensure_ascii=False,indent=1);print("housing",H)
except Exception as e: print("housing失敗",e)
