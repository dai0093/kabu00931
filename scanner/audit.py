# データ監査：Toolの主な数字を、元データから別計算＋別の取得元(Stooq)で照合
import json,io,requests,pandas as pd,numpy as np,yfinance as yf
P=[];OKS=[]
def L(f): return json.load(open(f))
def y(t,per="2y",adj=False):
    d=yf.download(t,period=per,progress=False,auto_adjust=adj)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
def stq(s):
    try:
        r=requests.get(f"https://stooq.com/q/d/l/?s={s}&i=d",timeout=30).text;d=pd.read_csv(io.StringIO(r),parse_dates=["Date"]).set_index("Date")["Close"];return d
    except Exception as e: return None
def chk(name,tool,true,tol):
    if tool is None or true is None or (isinstance(true,float) and np.isnan(true)): P.append(f"{name}: 比較不能 tool={tool} 再計算={true}");return
    (OKS if abs(tool-true)<=tol else P).append(f"{name}: Tool={tool} 再計算={round(true,2)}")
nkd=L("data/nk_daily.json");last=max(nkd);nk=y("^N225","5y")
print("日経 Toolの最終日",last,nkd[last],"Yahoo",nk.index[-1].date(),round(nk.iloc[-1],2))
s=stq("^nkx")
if s is not None and len(s):
    print("Stooq",s.index[-1].date(),s.iloc[-1]);
    if pd.Timestamp(last) in s.index: chk(f"日経終値{last}（Stooq）",nkd[last],float(s.loc[pd.Timestamp(last)]),1.0)
for k in sorted(nkd)[-8:]:
    if pd.Timestamp(k) in nk.index: chk(f"日経終値{k}（Yahoo）",nkd[k],float(nk.loc[pd.Timestamp(k)]),1.0)
D=L("data/defense.json");fl=D["history"]
# 防御の信号の再計算
c=pd.Series(nkd).sort_index();c.index=pd.to_datetime(c.index)
r1=(c.iloc[-1]/c.iloc[-2]-1)*100;r5=(c.iloc[-1]/c.iloc[-6]-1)*100
sox=y("^SOX","3mo");sox=sox[sox.index<c.index[-1]];sp=(sox.iloc[-1]/sox.iloc[-2]-1)*100  # 東京の前夜
print(f"再計算：日経1日 {r1:.2f}% 5日 {r5:.2f}% SOX前夜 {sp:.2f}%（{sox.index[-1].date()}）")
fl_now=(L("data/defense.json")["today"] or {}).get("flags",{})
for k,v in {"日経1日≤-2%":r1<=-2,"日経1日≤-3%":r1<=-3,"日経5日≤-5%":r5<=-5,"SOX前夜≤-4%":sp<=-4}.items():
    (OKS if fl_now.get(k)==v else P).append(f"信号「{k}」 Tool={fl_now.get(k)} 再計算={v}")
# 底打ち欄
b=D.get("bottom",{})
_u=pd.Timestamp(D["updatedAt"]).tz_convert("Asia/Tokyo") if pd.Timestamp(D["updatedAt"]).tzinfo else pd.Timestamp(D["updatedAt"])
if _u.weekday()<5 and 9<=_u.hour and (_u.hour*60+_u.minute)<15*60+40: OKS.append("底打ち欄：取引時間中の値のため照合しない（"+str(_u)[:16]+"）")
else: chk("底打ち欄の日経(最新終値のはず)",b.get("close"),float(c.iloc[-1]),1.0)
# 高値
chk("終値の高値",float(c.max()),float(nk.max()),1.0)
# 社債など
S=L("data/sectors.json")["credit"]
hyg,ief,lqd,kre,vix=[y(t,"1y",True) for t in ("HYG","IEF","LQD","KRE","^VIX")]
def r20(a,b):
    x=(a/b).dropna();return (x.iloc[-1]/x.iloc[-21]-1)*100
chk("社債HYG÷IEF 20日",S["hy20"],r20(hyg,ief),0.15)
chk("LQD÷IEF 20日",S["ig20"],r20(lqd,ief),0.15)
chk("KRE 高値から",S["kre_dd"],(kre.iloc[-1]/kre.max()-1)*100,0.5)
chk("VIX",S["vix"],float(vix.iloc[-1]),0.3)
# 資産（1日・200日線）
for it in L("data/assets.json")["items"]:
    try:
        z=y(it["ticker"],"2y",True);dt=pd.Timestamp(it["date"])
        i=z.index.get_loc(dt) if dt in z.index else None
        if i is None: P.append(f"資産 {it['name']}: 日付{it['date']}がデータに無い");continue
        chk(f"資産 {it['name']} 1日({it['date']})",it["d1"],(z.iloc[i]/z.iloc[i-1]-1)*100,0.15)
        chk(f"資産 {it['name']} 200日線",it["ma200"],(z.iloc[i]/z.iloc[i-199:i+1].mean()-1)*100,0.3)
    except Exception as e: P.append(f"資産 {it.get('name')}: {e}")
# REIT・国債ルール
for it in L("data/asset_rules.json")["items"]:
    try:
        z=y(it["ticker"],"3y",True)
        if it["rule"].startswith("1年"):chk(f"ルール {it['name']} 1年騰落",it["r252"],(z.iloc[-1]/z.iloc[-253]-1)*100,0.5)
        else:
            m=z.resample("ME").last();m=m[m.index<=z.index[-1]]
            if m.index[-1].month==z.index[-1].month and z.index[-1]<m.index[-1]+pd.offsets.MonthEnd(0): m=m.iloc[:-1]
            m=m[m.index<pd.Timestamp(z.index[-1].year,z.index[-1].month,1)]
            chk(f"ルール {it['name']} 月末と10か月平均の差",it["gap"],(m.iloc[-1]/m.iloc[-10:].mean()-1)*100,0.3)
    except Exception as e: P.append(f"ルール {it.get('name')}: {e}")
# 個別株（idx_daily）
ix=L("data/idx_daily.json")
for n,t in (("キオクシア","285A.T"),("イビデン","4062.T"),("アドバンテスト","6857.T"),("SOX","^SOX"),("S&P500","^GSPC"),("銀行ETF","1615.T")):
    z=y(t,"3mo");d=ix.get(n,{})
    for k in sorted(d)[-3:]:
        if pd.Timestamp(k) in z.index: chk(f"{n} {k}",d[k],float(z.loc[pd.Timestamp(k)]),max(1,abs(d[k])*0.002))
        else: P.append(f"{n} {k}: Yahooに無い日付")
# セクター（各銘柄の高値から）
for sec in L("data/sectors.json")["sectors"][:9]:
    for m in sec.get("members",[])[:2]:
        try:
            z=y(m["t"],"2y");chk(f"セクター {sec['name']} {m['t']} 高値から",m["dd"],(z.iloc[-1]/z.max()-1)*100,1.0)
        except Exception as e: P.append(f"セクター {m.get('t')}: {e}")
print("\n=== 不一致",len(P));[print("✗",x) for x in P]
print("\n=== 一致",len(OKS));[print("○",x) for x in OKS]
import os,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
_o={"at":datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="minutes"),"ok":not P,"problems":P,"n_ok":len(OKS)}
try: _old=json.load(open("data/audit.json"))
except Exception: _old={}
json.dump(_o,open("data/audit.json","w"),ensure_ascii=False,indent=1)
_T=os.environ.get("NTFY_TOPIC")
if _T and P and P!=_old.get("problems"):
    q=urllib.parse.urlencode({"title":"【Tool監査】数字の食い違い","priority":"4","click":"https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{_T}?{q}",data="\n".join(P).encode(),method="POST"),timeout=30)
