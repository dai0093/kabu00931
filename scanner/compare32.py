"""検証32：新高値ブレイクを「戻りの合図」に加えると良いか。
合図：N60 日経が直近60日の高値（当日除く）を終値で更新／N250 日経が直近250日の高値を更新／S60 SOXが直近60日の高値を更新／既存のU4（SOX5日≥+5%）。
防御中（直近10日に信号あり・当日0本）の日だけで、合図あり／なしの20日後の日経を前半・後半で比べ、さらに防御方針Cに足した成績を比べる。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
src = open("scanner/compare30.py").read().split('P = {"C（時間待ちのみ）"')[0]
exec(src)
brk = lambda s, n: (s > s.rolling(n).max().shift(1)).reindex(cal).fillna(False)
V = {"U4 SOX5日≥+5%": U["U4 SOX5日≥+5%"],
     "N60 日経が60日高値を更新": brk(nk, 60),
     "N250 日経が250日高値を更新": brk(nk, 250),
     "S60 SOXが60日高値を更新": brk(sox_s, 60)}
V["U4 または N60"] = V["U4 SOX5日≥+5%"] | V["N60 日経が60日高値を更新"]
V["U4 または S60"] = V["U4 SOX5日≥+5%"] | V["S60 SOXが60日高値を更新"]
f20 = (nk.shift(-20) / nk - 1).reindex(cal)
defence = pd.Series((pd.Series(sc, index=cal).rolling(10, min_periods=1).max() > 0).values & (sc == 0), index=cal)
def fs(m): return f"{int(m.sum())}日 平均{f20[m].mean()*100:+.2f}% 中央{f20[m].median()*100:+.2f}% −5%以下{(f20[m]<=-0.05).mean()*100:.0f}%"
for lbl, per in (("前半（〜2011）", cal < mid), ("後半（2012〜）", cal >= mid)):
    print("\n" + lbl, "防御中", int((defence & per).sum()), "日")
    for k, v in V.items():
        s2 = defence & per & v; s3 = defence & per & ~v; first = s2 & ~s2.shift(1, fill_value=False)
        print(f"{k}: あり {fs(s2)}（初日のみ {int(first.sum())}件 平均{f20[first].mean()*100:+.2f}%）／ なし {fs(s3)}")
print("\n方針（Cに足した場合）| 前半 | 後半 | 急落40件 平均/最悪 | 平均持ち高")
for nm, e in [("C", pol(None))] + [("C＋" + k, pol(v)) for k, v in V.items()]:
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); m, md, w = epi(r)
    print(f"{nm} | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 平均{m:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
