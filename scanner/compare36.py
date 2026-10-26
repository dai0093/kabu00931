"""検証36：ROBOPRO動画の主張「米10年金利が1か月で+0.5pt上昇すると、株・債券・金・REITが同時に下がる」を前半/後半で確認。
A 米10年(^TNX)が21営業日で+0.5pt以上上がった日 → 20営業日後の日経・S&P500・金・米国債ETF(TLT)の平均と、−5%以下の割合
B 日経が21日で下がった日のうち、金も下がった割合（同時下落）
前半(〜2011)後半(2012〜)で同じ向きなら『予測出来た』。"""
import warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
def dl(t, s="1996-01-01"):
    x = yf.download(t, start=s, auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225"); sp = dl("^GSPC"); tnx = dl("^TNX"); gc = dl("GC=F", "2000-01-01"); tlt = dl("TLT", "2002-08-01")
cal = nk.index; mid = pd.Timestamp("2012-01-01")
def al(x): return x.reindex(cal).ffill()
T = al(tnx); rise = T - T.shift(21)
A = {"日経": al(nk), "S&P500": al(sp), "金": al(gc), "米国債TLT": al(tlt)}
fw = {k: v.shift(-20) / v - 1 for k, v in A.items()}
for th in (0.5, 0.4):
    print(f"\n=== 米10年が21日で+{th}pt以上 ===")
    for nm, m in (("前半", cal < mid), ("後半", cal >= mid)):
        on = (rise >= th) & m
        # 連続日を1回にまとめる（10日以上あいたら新規）
        idx = cal[on]; ev = []
        for d in idx:
            if not ev or (d - ev[-1]).days > 30: ev.append(d)
        print(f"{nm}: 該当{int(on.sum())}日 / 独立{len(ev)}回")
        for k in A:
            f = fw[k][m].dropna(); fo = fw[k][on].dropna()
            if len(fo) < 5: print(f"   {k}: データ不足"); continue
            print(f"   {k}: 20日後 平均{fo.mean()*100:+.2f}%（全日{f.mean()*100:+.2f}%） −5%以下 {(fo<=-.05).mean()*100:.0f}%（全日{(f<=-.05).mean()*100:.0f}%）")
print("\n=== B 同時下落：日経が21日で−5%以下の日に、金・TLTも21日で下がっていた割合 ===")
for nm, m in (("前半", cal < mid), ("後半", cal >= mid)):
    r = {k: v / v.shift(21) - 1 for k, v in A.items()}
    d = (r["日経"] <= -0.05) & m
    for k in ("金", "米国債TLT", "S&P500"):
        ok = r[k][d].dropna()
        if len(ok): print(f"{nm} 日経−5%以下の日{int(d.sum())}日のうち {k}も下落: {(ok<0).mean()*100:.0f}%")
# 直近
print("\n直近 米10年 21日変化:", f"{rise.iloc[-1]:+.2f}pt", " 水準", f"{T.iloc[-1]:.2f}%", cal[-1].date())
