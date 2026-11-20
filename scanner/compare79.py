# 検証79：2008年10月・2020年3月・今回の「追証の投げ売り」局面で、各指標を同じ物差しで比べる
import yfinance as yf, pandas as pd, numpy as np
T={"^VIX":"VIX","^GSPC":"S&P500","^N225":"日経","HYG":"ハイイールド社債","LQD":"投資適格社債","IEF":"米国債7-10年","TLT":"米国債20年","KRE":"米地銀","XLF":"米金融","GLD":"金","DX-Y.NYB":"ドル指数","JPY=X":"ドル円","^TNX":"米10年金利","^IRX":"米3か月金利","BKLN":"ローン(レバレッジドローン)","EMB":"新興国債","SLV":"銀","CL=F":"原油"}
D={}
for t,n in T.items():
    try:
        s=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();s.index=pd.to_datetime(s.index).tz_localize(None);D[n]=s
    except Exception as e: print(n,"取得失敗")
W={"2008年10月（リーマン後）":("2008-09-12","2008-10-10","2008-11-20"),"2020年3月（コロナ）":("2020-02-21","2020-03-16","2020-03-23"),"今回":("2026-10-16","2026-11-20","2026-11-20")}
print("各局面：A=開始前の基準日、B=追証の投げ売りの日、C=その局面の最悪の日。数値はAからの変化（金利・VIXは水準）")
for n,s in D.items():
    row=f"{n:14s}"
    for k,(a,b,c) in W.items():
        try:
            va=s[:a].iloc[-1];vb=s[:b].iloc[-1];vc=s[a:c].min() if n not in ("VIX","米10年金利","米3か月金利","ドル指数","米国債7-10年","米国債20年") else s[a:c].max()
            if n in ("VIX","米10年金利","米3か月金利"): row+=f" | {k[:7]} {va:.2f}→{vb:.2f}（極{vc:.2f}）"
            else: row+=f" | {k[:7]} {(vb/va-1)*100:+.1f}%（極{(vc/va-1)*100:+.1f}%）"
        except Exception: row+=f" | {k[:7]} —"
    print(row)
# 社債÷国債（信用の物差し）
for k,(a,b,c) in W.items():
    try:
        hy=(D["ハイイールド社債"]/D["米国債7-10年"]).dropna();ig=(D["投資適格社債"]/D["米国債7-10年"]).dropna()
        print(f"{k}: HY÷国債 {(hy[:b].iloc[-1]/hy[:a].iloc[-1]-1)*100:+.1f}%（最悪{(hy[a:c].min()/hy[:a].iloc[-1]-1)*100:+.1f}%）／IG÷国債 {(ig[:b].iloc[-1]/ig[:a].iloc[-1]-1)*100:+.1f}%（最悪{(ig[a:c].min()/ig[:a].iloc[-1]-1)*100:+.1f}%）")
    except Exception as e: print(k,e)
