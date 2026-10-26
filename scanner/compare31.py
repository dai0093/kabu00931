"""検証31：SOX5日≥+5%の「戻りの合図」は、前半（〜2011）でも20日後の上昇を予測したか。
防御中（直近10営業日に信号あり・当日0本）の日だけで、合図あり／なしの20日後の日経（平均・中央値・−5%以下の確率）を前半・後半で比べる。
重複を避けるため、合図の連続日は最初の1日だけを数えた件数も出す。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
src = open("scanner/compare30.py").read().split('P = {"C（時間待ちのみ）"')[0]
exec(src)
u4 = U["U4 SOX5日≥+5%"]
f20 = (nk.shift(-20) / nk - 1).reindex(cal)
defence = pd.Series((pd.Series(sc, index=cal).rolling(10, min_periods=1).max() > 0).values & (sc == 0), index=cal)
def show(lbl, mask):
    s2 = mask & u4; s3 = mask & ~u4
    first = s2 & ~s2.shift(1, fill_value=False)
    f = lambda m: f"{int(m.sum())}日 平均{f20[m].mean()*100:+.2f}% 中央{f20[m].median()*100:+.2f}% −5%以下{(f20[m]<=-0.05).mean()*100:.0f}%"
    print(f"{lbl}\n  合図あり {f(s2)}（連続の初日だけ {f(first)}）\n  合図なし {f(s3)}")
mid_ = mid
show("前半（〜2011）", defence & (cal < mid_))
show("後半（2012〜）", defence & (cal >= mid_))
yrs = sorted(set(cal.year))
print("\n年代別（合図あり−合図なしの20日後平均の差）")
for a, b in ((1997, 2003), (2004, 2011), (2012, 2018), (2019, 2026)):
    m = defence & (cal.year >= a) & (cal.year <= b)
    s2 = m & u4; s3 = m & ~u4
    print(f"{a}-{b}: 合図あり{int(s2.sum())}日 {f20[s2].mean()*100:+.2f}% / なし{int(s3.sum())}日 {f20[s3].mean()*100:+.2f}%")
# 方針（前半・後半の累積）
base = pol(None); withU4 = pol(u4)
for nm, e in (("C", base), ("C＋SOX合図", withU4)):
    r = run(e); a1, d1 = st(r, None, mid_); a2, d2 = st(r, mid_, None); m, md, w = epi(r)
    print(f"{nm}: 前半 {a1:+.0f}%・{d1:.0f}% / 後半 {a2:+.0f}%・{d2:.0f}% / 急落 平均{m:.1f}% 最悪{w:.1f}%")
