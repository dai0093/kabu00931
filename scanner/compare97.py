# 検証97：住宅・不動産の悪化は暴落の前に出たか（米国・日本）。5年区間ごとに傾向を確認
import yfinance as yf,pandas as pd,numpy as np,requests,io
def g(t,start="1995-01-01"):
    d=yf.download(t,start=start,progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp,nk=g("^GSPC"),g("^N225");hyg,ief=g("HYG"),g("IEF")
itb=g("ITB");xhb=g("XHB")
jre=pd.concat([g(t) for t in ("8801.T","8802.T","8830.T")],axis=1).dropna();jre=(jre/jre.iloc[0]).mean(axis=1)
jreit=g("1343.T")
try:
    r=requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DRSFRMACBS",timeout=30).text
    t=pd.read_csv(io.StringIO(r));t.index=pd.to_datetime(t.iloc[:,0]);dq=pd.to_numeric(t.iloc[:,1],errors="coerce").dropna()
    print("延滞率",dq.index[0].date(),"〜",dq.index[-1].date(),"最新",dq.iloc[-1])
except Exception as e: dq=None;print("延滞率 取得失敗",e)
H_=250
def crash(idx,day,h=None,th=-20):
    h=h or H_
    s=idx[idx.index>=day]
    if len(s)<h: return np.nan
    return float((s.iloc[:h+1].min()/s.iloc[0]-1)*100<=th)
def events(sig,gap=60):
    sig=sig.fillna(False);ev=[];last=None
    for d,v in sig.items():
        if v and (last is None or (d-last).days>gap*1.4): ev.append(d)
        if v: last=d
    return ev
def test(name,sig,idx,lab):
    ev=events(sig);base=[crash(idx,d) for d in idx.index[::5]];base=np.nanmean(base)*100
    rs=[crash(idx,d) for d in ev];hit=np.nanmean(rs)*100 if ev else np.nan
    print(f"\n== {name} → {lab}{H_}日以内−20%：合図{len(ev)}回 的中{np.nansum(rs):.0f}/{np.sum(~np.isnan(rs))} = {hit:.0f}%（ふだん{base:.1f}%）")
    yrs=range(1995,2027,5);good=0;n=0
    for y in yrs:
        e=[d for d in ev if y<=d.year<y+5]
        b=[crash(idx,d) for d in idx[str(y):str(y+4)].index[::5]];bb=np.nanmean(b)*100 if b else np.nan
        if not e: print(f"   {y}-{y+4}: 合図なし（ふだん{bb:.1f}%）");continue
        r=[crash(idx,d) for d in e];hh=np.nanmean(r)*100;n+=1;good+=hh>bb
        print(f"   {y}-{y+4}: 合図{len(e)}回 {hh:.0f}%（ふだん{bb:.1f}%） 日付:{','.join(str(d.date()) for d in e[:6])}")
    print(f"   合図があった区間で、ふだんより高かった区間 {good}/{n}")
def dd52(s): return s/s.rolling(252).max()-1
def rel(a,b,k=60): x=(a/b.reindex(a.index).ffill());return x/x.shift(k)-1
H=(hyg/ief).dropna();hy=H/H.shift(20)-1
S={
 "米 住宅建設株ITB 高値から−25%以下":dd52(itb)<=-0.25,
 "米 住宅建設株ITB 対S&P 60日−15%以下":rel(itb,sp)<=-0.15,
 "米 XHB 高値から−25%以下":dd52(xhb)<=-0.25,
 "日 不動産株3社 高値から−25%以下":dd52(jre)<=-0.25,
 "日 不動産株3社 対日経 60日−10%以下":rel(jre,nk)<=-0.10,
 "日 J-REIT 高値から−20%以下":dd52(jreit)<=-0.20,
}
for k,v in S.items():
    for idx,lab in ((sp,"S&P"),(nk,"日経")): test(k,v,idx,lab)
if dq is not None:
    up=(dq-dq.shift(4))>=0.5;dsig=up.reindex(sp.index,method="ffill")
    for idx,lab in ((sp,"S&P"),(nk,"日経")): test("米 住宅ローン延滞率 1年で+0.5pt以上",dsig,idx,lab)
# 社債より先に出たか
print("\n== 社債（HYG÷IEF 20日≤−2%）より何日先に出たか（初回同士）")
hev=events(hy<=-0.02)
for k,v in S.items():
    ev=events(v);leads=[]
    for h in hev:
        pr=[e for e in ev if 0<=(h-e).days<=365]
        leads.append((h-pr[-1]).days if pr else None)
    got=[x for x in leads if x is not None]
    print(f"  {k}: 社債の合図{len(hev)}回のうち、1年以内に先行 {len(got)}回 中央値{np.median(got) if got else '—'}日")
# 今の状態
print("\n== 今")
print(f"  ITB 高値から {dd52(itb).iloc[-1]*100:.1f}% ／対S&P60日 {rel(itb,sp).iloc[-1]*100:.1f}%")
print(f"  XHB 高値から {dd52(xhb).iloc[-1]*100:.1f}%")
print(f"  日本不動産3社 高値から {dd52(jre).iloc[-1]*100:.1f}% ／対日経60日 {rel(jre,nk).iloc[-1]*100:.1f}%")
print(f"  J-REIT 高値から {dd52(jreit).iloc[-1]*100:.1f}%")
if dq is not None: print(f"  延滞率 {dq.iloc[-1]}（1年前差 {dq.iloc[-1]-dq.iloc[-5]:+.2f}pt）{dq.index[-1].date()}")
