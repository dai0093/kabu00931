"""画面の自動点検：実際に描画し、表示とデータを突き合わせる。食い違いは data/uicheck.json と通知へ"""
import asyncio,json,os,re,subprocess,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from playwright.async_api import async_playwright
JST=timezone(timedelta(hours=9))
def L(f):
    try: return json.load(open(f))
    except Exception: return None
srv=subprocess.Popen(["python3","-m","http.server","8765"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1)
P=[]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(**({"executable_path":os.environ["CHROME"],"args":["--no-sandbox"]} if os.environ.get("CHROME") else {}));pg=await b.new_page(viewport={"width":400,"height":900})
        errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
        await pg.goto("http://localhost:8765/signals.html");await pg.wait_for_timeout(8000)
        body=await pg.inner_text("body")
        sig=await pg.evaluate("()=>{const e=document.getElementById('sigdate');return e?e.innerText:''}")
        reb=await pg.evaluate("()=>{const e=document.getElementById('reb');return e?e.innerText:''}")
        etf=await pg.evaluate("()=>{const e=document.getElementById('etfguard');return e?e.innerText:''}")
        hdate=await pg.evaluate("()=>{const e=document.getElementById('hdate');return e?e.innerText:''}")
        await b.close()
    for e in errs: P.append("画面のエラー: "+e[:120])
    for w in ("undefined","NaN","[object Object]","Invalid Date"):
        if w in body: P.append(f"表示に「{w}」が出ている")
    # 1 防御の信号：新しい方のデータと一致するか
    DF,DI=L("data/defense.json"),L("data/defense_intraday.json")
    D=DI if (DI and DF and DI.get("updatedAt","")>DF.get("updatedAt","")) else (DF or DI)
    fl=((D or {}).get("today") or {}).get("flags") or {}
    lines=sig.split("\n")
    for k,v in fl.items():
        if k in lines:
            got=lines[lines.index(k)+1].strip() if lines.index(k)+1<len(lines) else ""
            if got!=("点灯" if v else "未点灯"): P.append(f"防御の信号「{k}」：データ={'点灯' if v else '未点灯'} 画面={got}")
        else: P.append(f"防御の信号「{k}」が画面に無い")
    n=sum(bool(v) for v in fl.values())
    if fl and f"今日 {n}本点灯" not in sig: P.append(f"点灯本数の表示がデータ（{n}本）と違う")
    # 2 事前登録の社債値
    S=L("data/sectors.json") or {};cr=S.get("credit") or {}
    if cr.get("hy20") is not None and f"{cr['hy20']:.2f}%" not in sig: P.append(f"社債20日 {cr['hy20']:.2f}% が②に出ていない")
    # 3 REIT・国債の判定（①とETF欄）
    A=L("data/asset_rules.json") or {}
    for x in A.get("items",[]):
        if x.get("err"): continue
        want="持ってよい" if x["ok"] else "持たない"
        for nm,txt in (("①",reb.split("資産ごとの判定")[-1]),("ETF欄",etf)):
            m=re.search(re.escape(x["name"])+r"[^\n]*\n(?:[^\n]*\n)?([^\n]*)",txt)
            seg=txt[txt.find(x["name"]):txt.find(x["name"])+200] if x["name"] in txt else ""
            if not seg: P.append(f"{nm}に{x['name']}が無い");continue
            first=[s for s in seg.split("\n")[1:4] if s.startswith(("持ってよい","持たない","判定なし","取得待ち"))]
            if not first or not first[0].startswith(want): P.append(f"{nm}の{x['name']}：データ={want} 画面={first[0] if first else '見つからず'}")
    if "判定なし" in reb or "判定なし" in etf: P.append("「判定なし」が残っている")
    # 4 日付
    t=datetime.now(JST);want=f"{t.month}月{t.day}日"
    if hdate.strip()!=want: P.append(f"見出しの日付 {hdate.strip()}（今日は{want}）")
    # 5 急落検知の重複
    J=L("data/jumps.json") or {};cs=[h["code"] for h in J.get("hits",[])]
    if len(cs)!=len(set(cs)): P.append("急落検知に同じ銘柄が重複")
    # 6 データの古さ（平日）
    if t.weekday()<5:
        for f,k,hrs in (("data/defense.json","updatedAt",30),("data/sectors.json","updatedAt",30),("data/asset_rules.json","updatedAt",30)):
            o=L(f) or {};u=o.get(k)
            try:
                ut=datetime.fromisoformat(u.replace("Z","+00:00"))
                if (t-ut).total_seconds()>hrs*3600: P.append(f"{f} が{hrs}時間以上更新されていない（{u}）")
            except Exception: P.append(f"{f} の更新日が読めない")
asyncio.run(main());srv.terminate()
out={"at":datetime.now(JST).isoformat(timespec="minutes"),"ok":not P,"problems":P}
old=L("data/uicheck.json") or {}
json.dump(out,open("data/uicheck.json","w"),ensure_ascii=False,indent=1);print(json.dumps(out,ensure_ascii=False,indent=1))
T=os.environ.get("NTFY_TOPIC")
if T and P and P!=old.get("problems"):
    q=urllib.parse.urlencode({"title":"【Tool点検】表示とデータの食い違い","priority":"4","click":"https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{T}?{q}",data="\n".join(P).encode(),method="POST"),timeout=30)
