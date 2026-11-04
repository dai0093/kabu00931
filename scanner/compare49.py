"""検証49（経路の段の移り方）。元：検証47：暴落への想定経路の進行度は、暴落の前に上がっていたか。履歴のない手入力項目（地政学・AI債務・AI→銀行）は除き、
履歴の取れる代替で各項目の点灯(1)/接近(0.5)を作る。進行度＝平均。米国の値は東京の翌営業日に使う。
前半(〜2011。HYGがあるのは2007〜)／後半(2012〜)で、進行度が高い日の『60日以内に日経−10%/−20%』『20日以内に−5%』を全日と比較。
主要な暴落の前（20・10・5営業日前）の進行度も表示。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, adj=False, s="1995-01-01"):
    x = yf.download(t, start=s, auto_adjust=adj, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225"); cal = nk.index; mid = pd.Timestamp("2012-01-01")
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
def lv(x, lit, near, up=False):
    return pd.Series(np.where((x >= lit) if up else (x <= lit), 1.0, np.where((x >= near) if up else (x <= near), 0.5, 0.0)), index=x.index).where(x.notna())
pc = prev(pd.concat([dl(t).pct_change(5) for t in ("BX", "APO", "KKR", "ARES")], axis=1).median(axis=1)) * 100
hy = prev((dl("HYG", True) / dl("IEF", True)).pct_change(20)) * 100
bk = prev(dl("^BKX").pct_change(5)) * 100
lf = prev(pd.concat([dl(t).pct_change(5) for t in ("MET", "PRU")], axis=1).median(axis=1)) * 100
vix = prev(dl("^VIX")); vix3 = (vix >= 25).astype(int).rolling(3).sum()
z = lambda s: (s - s.rolling(500, min_periods=250).mean()) / s.rolling(500, min_periods=250).std()
fs = (z(vix) + z(-hy) + z(-bk)) / 3
sx = prev(dl("^SOX")); sdd = (sx / sx.rolling(250).max() - 1) * 100
r1 = nk.pct_change() * 100
tnx = prev(dl("^TNX")); t20 = tnx - tnx.shift(20)
oil = prev(dl("CL=F")); o250 = oil.pct_change(250) * 100
N = {"私募信用": lv(pc, -8, -5), "HY OAS": lv(hy, -2, -1), "金融機関株価": lv(bk, -10, -5), "生保": lv(lf, -10, -6),
     "NFCI": lv(fs, 1.5, 1.0, True), "VIX": pd.Series(np.where(vix3 >= 3, 1.0, np.where(vix >= 25, .5, 0.0)), index=cal).where(vix.notna()),
     "SOX下落": lv(sdd, -20, -10), "日経先物": lv(r1, -2.5, -1.5), "日米金利": lv(t20, 0.4, 0.25, True), "原油": lv(o250, 50, 30, True)}
P = {"2008型（信用の伝播）": ["私募信用", "HY OAS", "金融機関株価", "生保", "NFCI", "VIX"],
     "鉄道型（AI）※代替できる項目のみ": ["SOX下落", "HY OAS", "金融機関株価"],
     "1987型（金利ショック）": ["日米金利", "VIX", "日経先物"],
     "地政学・エネルギー※原油以降": ["原油", "日米金利", "VIX"]}

import json
mn = pd.Series([(nk.iloc[i+1:i+61].min()/nk.iloc[i]-1) if i+61 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
OUT = {}
for nm, ns in P.items():
    sc = pd.concat([N[n] for n in ns], axis=1)
    ok = sc.notna().all(axis=1); stg = np.floor(sc.sum(axis=1)).where(ok)
    res = []
    for k in range(1, len(ns)):
        up = (stg >= k) & (stg.shift(1) < k); ev = []
        for d in cal[up.fillna(False).values]:
            if not ev or (d - ev[-1]).days > 30: ev.append(d)
        dts, rch, mns = [], 0, []
        for d in ev:
            i = cal.get_loc(d); fut = stg.iloc[i+1:i+121]
            hit = fut[fut >= k + 1]
            if len(hit): dts.append(int(cal.get_indexer([hit.index[0]])[0] - i))
            if len(hit) and dts[-1] <= 60: rch += 1
            if pd.notna(mn.iloc[i]): mns.append(mn.iloc[i])
        if not ev: continue
        res.append({"from": k, "to": k + 1, "n": len(ev), "days_med": int(np.median(dts)) if dts else None,
                    "p60": round(rch / len(ev) * 100), "nk_min_med": round(float(np.median(mns)) * 100, 1) if mns else None,
                    "nk10": round(float(np.mean([m <= -0.10 for m in mns])) * 100) if mns else None})
        print(f"{nm} 段{k}→{k+1}: {len(ev)}回 次の段まで中央値{res[-1]['days_med']}日 60日以内に進んだ{res[-1]['p60']}% その後60日の日経最安 中央値{res[-1]['nk_min_med']}% −10%以下{res[-1]['nk10']}%")
    cur = stg.iloc[-1]
    OUT[nm.split("（")[0] if "※" not in nm else nm.split("※")[0]] = {"nodes": ns, "stage_now": None if pd.isna(cur) else int(cur), "trans": res}
json.dump({"since": "2008", "paths": OUT, "rule": "点灯=1・接近=0.5の合計（切り捨て）を段とする。段が上がった日から、次の段に上がるまでの営業日数（120日以内に上がった回のみ）と、その後60営業日の日経の最安値"}, open("data/path_hist.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(OUT, ensure_ascii=False)[:400])
