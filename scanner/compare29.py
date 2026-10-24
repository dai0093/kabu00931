"""検証29：7資産それぞれで「下がったら売る」ルールは有効だったか。
代用（長い履歴のため）：日本株^N225／米国株^GSPC／米国債IEF／日本国債（2510.Tは短いので^TNXの利回り上昇でなく債券ETF 2510.T、無ければ欠損）／金GLD／REIT VNQ／先進国EFA。
ルール（引け後判定→翌営業日反映、先読みなし、コスト0.1%/売買）：
 R1 直近5日≤-4%で売り、20営業日後に戻す  R2 60日高値から≤-8%で売り、高値-4%以内に戻ったら買い戻し  R3 200日線割れで売り
評価：累積・最大下落（前半/後半）、売りが鳴った後21日の平均騰落（無条件と比較）。"""
import warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
A = [("日本株", "^N225"), ("米国株", "^GSPC"), ("米国債", "IEF"), ("日本国債", "2510.T"), ("金", "GLD"), ("REIT", "VNQ"), ("先進国株", "EFA")]
def stats(r):
    cum = (1 + r).cumprod(); mdd = (cum / cum.cummax() - 1).min()
    return cum.iloc[-1] - 1, mdd
for nm, t in A:
    try: p = yf.Ticker(t).history(period="max")["Close"].dropna()
    except Exception as e: print(nm, "取得失敗", e); continue
    if len(p) < 800: print(nm, t, "履歴短い", len(p)); continue
    p.index = p.index.tz_localize(None) if p.index.tz is not None else p.index
    r = p.pct_change().fillna(0); n = len(p)
    r5 = p.pct_change(5); dd = p / p.rolling(60).max() - 1; ma = p.rolling(200).mean()
    # R1
    idx = np.where((r5 <= -0.04).values)[0]; ev = []; last = -99
    s1 = pd.Series(0, index=p.index)
    for i in idx:
        if i - last > 20: ev.append(i)
        last = i if i - last > 20 else last
    for i in ev: s1.iloc[i:min(n, i + 20)] = 1
    # R2
    s2 = pd.Series(0, index=p.index); st = 0
    for i in range(n):
        if st == 0 and dd.iloc[i] <= -0.08: st = 1
        elif st == 1 and dd.iloc[i] > -0.04: st = 0
        s2.iloc[i] = st
    s3 = (p < ma).astype(int).fillna(0)
    half = p.index[n // 2]
    print(f"\n=== {nm} ({t}) {p.index[0].date()}〜 n={n} ===")
    f21 = p.shift(-21) / p - 1
    print(f"無条件 21日後 平均 {f21.mean()*100:+.2f}% 下落(≤-5%)率 {(f21<=-0.05).mean()*100:.1f}%")
    for lab, s in [("R1 5日≤-4%で20日売り", s1), ("R2 高値-8%で売り(-4%で戻す)", s2), ("R3 200日線割れで売り", s3)]:
        e = 1 - s.shift(1).fillna(0); cost = e.diff().abs().fillna(0) * 0.001; rr = r * e - cost
        out = []
        for nmh, sl in [("全期間", slice(None)), ("前半", slice(None, half)), ("後半", slice(half, None))]:
            c0, m0 = stats(r[sl]); c1, m1 = stats(rr[sl]); out.append(f"{nmh} 持ち続け {c0*100:+.0f}%/最大{m0*100:.0f}% → ルール {c1*100:+.0f}%/最大{m1*100:.0f}%")
        fire = s.diff().fillna(0) > 0; fa = f21[fire.shift(0).fillna(False)]
        print(lab, "発動", int(fire.sum()), "回 / 発動後21日 平均", f"{fa.mean()*100:+.2f}%", "下落≤-5%率", f"{(fa<=-0.05).mean()*100:.0f}%" if len(fa) else "-", "平均持ち高", f"{e.mean()*100:.0f}%")
        for o in out: print("   ", o)
