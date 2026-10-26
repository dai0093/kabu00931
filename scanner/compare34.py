"""検証34：「1年で右肩上がり」かつ「新高値ブレイク直前」の銘柄抽出は、その後の上昇を予測したか。
対象：東証の流動性のある873銘柄（data/universe_all.json）、5年分の日足（配当調整あり）。前半＝〜2023-12、後半＝2024-01〜。
右肩上がり：終値>200日線、200日線が20日前より上、250日リターン≥+20%、25日線>75日線。
ブレイク直前：終値が直近250日高値（当日除く）の−3%以内で、まだ更新していない。直近20日の値幅が終値の15%以内（値幅が縮んでいる）。20日平均売買代金30億円以上。
評価（信号日の翌営業日の始値で買う想定、0.2%のずれ込み）：20営業日後の騰落／250日高値を20日以内に更新した割合／同じ日の全銘柄平均との差／日経との差。
比較：①右肩上がりだが高値から−10%以上離れた銘柄 ②全銘柄 ③既存の「60日高値更新」の日。最後に、今日の該当銘柄を data/prebreak.json に書く。"""
import json, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, "scanner")
from data import load, universe
U = json.load(open("data/universe_all.json", encoding="utf-8")); NAMES = universe()
raw = load("5y", codes=list(U), size=50, wait=10)
MID = pd.Timestamp("2024-01-01")
rows, cur = [], []
allret = {}
for c, df in raw.items():
    d = df.copy(); d.index = pd.to_datetime(d.index).tz_localize(None); d = d[~d.index.duplicated()]
    if len(d) < 300: continue
    C, H, L, V, O = d.Close, d.High, d.Low, d.Volume, d.Open
    s25, s75, s200 = C.rolling(25).mean(), C.rolling(75).mean(), C.rolling(200).mean()
    hi250 = H.rolling(250).max().shift(1); hi60 = H.rolling(60).max().shift(1)
    rng20 = (H.rolling(20).max() - L.rolling(20).min()) / C
    to20 = (C * V).rolling(20).mean()
    up = (C > s200) & (s200 > s200.shift(20)) & (C / C.shift(250) - 1 >= 0.20) & (s25 > s75)
    near = (C >= hi250 * 0.97) & (C < hi250)
    pre = up & near & (rng20 <= 0.15) & (to20 >= 3e9)
    far = up & (C <= hi250 * 0.90) & (to20 >= 3e9)
    brk60 = (C > hi60) & (s25 > s75) & (C > s25) & (V > 1.5 * V.rolling(20).mean()) & (to20 >= 3e9)
    nxt_open = O.shift(-1) * 1.002
    f20 = C.shift(-20) / nxt_open - 1
    hitnh = pd.Series([H.iloc[i + 1:i + 21].max() > hi250.iloc[i] if i + 21 <= len(H) and not np.isnan(hi250.iloc[i]) else np.nan for i in range(len(H))], index=d.index)
    allret[c] = f20
    rows.append(pd.DataFrame({"c": c, "pre": pre, "far": far, "brk": brk60, "f20": f20, "hit": hitnh}, index=d.index))
    if pre.iloc[-1]:
        cur.append({"code": c, "name": NAMES.get(c, c), "close": round(float(C.iloc[-1]), 1), "toHigh": round(float((hi250.iloc[-1] / C.iloc[-1] - 1) * 100), 1),
                    "ret250": round(float((C.iloc[-1] / C.iloc[-251] - 1) * 100), 1), "rng20": round(float(rng20.iloc[-1] * 100), 1), "to20": round(float(to20.iloc[-1] / 1e8), 1)})
D = pd.concat(rows); D = D[D.index >= D.index.min() + pd.Timedelta(days=370)]
mkt = D.groupby(level=0)["f20"].mean()
D["ex"] = D["f20"] - mkt.reindex(D.index).values
print(f"銘柄 {D['c'].nunique()}  期間 {D.index.min().date()}〜{D.index.max().date()}")
def rep(lbl, m, per):
    x = D[m & per].dropna(subset=["f20"]); 
    first = x[~(x.groupby("c").cumcount().eq(0) == False)]
    # 連続日を1件にまとめる（同じ銘柄で5営業日以内は同じ件）
    n_ep = 0; last = {}
    for dt, r in x.iterrows():
        if r["c"] not in last or (dt - last[r["c"]]).days > 8: n_ep += 1
        last[r["c"]] = dt
    print(f"  {lbl}: 信号日 {len(x)}（独立の件 約{n_ep}）20日後 平均{x['f20'].mean()*100:+.2f}% 中央{x['f20'].median()*100:+.2f}% 上昇{(x['f20']>0).mean()*100:.0f}% 全銘柄平均との差 {x['ex'].mean()*100:+.2f}% 20日以内に高値更新 {x['hit'].astype(float).mean()*100:.0f}% −10%以下{(x['f20']<=-0.10).mean()*100:.0f}%")
for lbl, per in (("前半（〜2023）", D.index < MID), ("後半（2024〜）", D.index >= MID)):
    print(lbl)
    rep("右肩上がり＋ブレイク直前", D["pre"], per)
    rep("右肩上がりだが高値から−10%以上", D["far"], per)
    rep("既存の60日高値更新", D["brk"], per)
    rep("全銘柄・全日", D["f20"].notna(), per)
cur.sort(key=lambda x: x["toHigh"])
json.dump({"asOf": str(D.index.max().date()), "rule": "1年右肩上がり＋250日高値の−3%以内（未更新）＋20日値幅15%以内", "items": cur[:40]}, open("data/prebreak.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n今日の該当", len(cur), "銘柄（高値に近い順）")
for x in cur[:25]: print(f"{x['code']} {x['name']} 終値{x['close']:,} 高値まで+{x['toHigh']}% 250日{x['ret250']:+.0f}% 20日値幅{x['rng20']}% 売買代金{x['to20']}億")
