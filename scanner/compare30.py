"""検証30：上昇（戻り）を検知して買い戻す方針は、時間待ち（最後の信号から10営業日）より良いか。
基本は防御方針C（1本→50% 2本→25% 3本以上→0%、10営業日維持）。これに「上昇の合図」が出た日（かつ当日の危険信号が0本）に、信号の記録を消して100%へ戻す、を足す。
上昇の合図：U1 日経が25日線の上／U2 日経5日≥+3%／U3 直近10日の安値から+5%／U4 SOX5日≥+5%／U5 日経が50日線の上。
評価：①戻りの合図の後20営業日の日経の平均（防御中の無条件と比較）②後半の累積・最大下落 ③急落40件の平均・最悪 ④主要局面。信号は引け後に判定、翌営業日反映、コスト0.1%。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
src = open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0]
exec(src)
sox_s = sox.reindex(cal).ffill()
U = {"U1 日経が25日線の上": nk > nk.rolling(25).mean(),
     "U2 日経5日≥+3%": nk.pct_change(5) >= 0.03,
     "U3 直近10日安値から+5%": nk >= nk.rolling(10).min() * 1.05,
     "U4 SOX5日≥+5%": sox_s.pct_change(5) >= 0.05,
     "U5 日経が50日線の上": nk > nk.rolling(50).mean()}
U = {k: v.reindex(cal).fillna(False) for k, v in U.items()}
sc = score.values
def pol(up, levels=(.5, .25, 0), hold=10, restore=1.0):
    n = len(cal); e = np.ones(n); lc = -1
    for i in range(n):
        lo = max(lc + 1, i - hold + 1); sh = sc[lo:i + 1].max() if i >= lo else 0
        if up is not None and up.iloc[i] and sc[i] == 0 and sh > 0: lc = i; sh = 0
        e[i] = 1.0 if sh == 0 else levels[0] if sh == 1 else levels[1] if sh == 2 else levels[2]
    return pd.Series(e, index=cal)
base = pol(None)
P = {"C（時間待ちのみ）": base}
for k, v in U.items(): P["C＋" + k] = pol(v)
P["C＋U1かつU2"] = pol(U["U1 日経が25日線の上"] & U["U2 日経5日≥+3%"])
P["C＋U3かつU4"] = pol(U["U3 直近10日安値から+5%"] & U["U4 SOX5日≥+5%"])
P["持ちっぱなし"] = pd.Series(1.0, index=cal)
print("方針 | 前半 累積・最大下落 | 後半 累積・最大下落 | 急落40件 平均/最悪 | 平均持ち高 | 売買の回数/年")
for nm, e in P.items():
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); m, md, w = epi(r)
    print(f"{nm} | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落 平均{m:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}% | {(e.diff().abs()>0).sum()/(len(e)/252):.1f}回")
print("\n主要局面（持ちっぱなし／C／C＋最良の戻り合図）")
best = max([k for k in P if k.startswith("C＋")], key=lambda k: st(run(P[k]), mid, None)[0])
print("後半の累積が最大の合図:", best)
for nm_, a, b in (("リーマン", "2008-09-01", "2008-12-31"), ("コロナ", "2020-01-15", "2020-04-30"), ("2024夏", "2024-07-01", "2024-09-30"), ("2025春", "2025-03-01", "2025-05-31"), ("2026/10(今回)", "2026-10-01", "2026-10-23")):
    f = lambda e: st(run(e), a, b)
    print(f"{nm_}: 保有 {f(P['持ちっぱなし'])[0]:+.0f}%({f(P['持ちっぱなし'])[1]:.0f}%) / C {f(base)[0]:+.0f}%({f(base)[1]:.0f}%) / {best} {f(P[best])[0]:+.0f}%({f(P[best])[1]:.0f}%)")
print("\n戻りの合図は、その後の上昇を予測したか（防御中＝直近10日に信号あり・当日0本の日だけ。後半2012〜）")
defence = pd.Series((pd.Series(sc, index=cal).rolling(10, min_periods=1).max() > 0).values & (sc == 0), index=cal)
f20 = nk.shift(-20) / nk - 1; f20 = f20.reindex(cal)
sel = defence & (cal >= mid)
print(f"防御中の日 {int(sel.sum())}日  20日後の日経 平均 {f20[sel].mean()*100:+.2f}%  −5%以下の確率 {(f20[sel]<=-0.05).mean()*100:.0f}%")
for k, v in U.items():
    s2 = sel & v; s3 = sel & ~v
    print(f"{k}: 合図あり {int(s2.sum())}日 平均 {f20[s2].mean()*100:+.2f}% −5%以下 {(f20[s2]<=-0.05).mean()*100:.0f}% ／ 合図なし {int(s3.sum())}日 平均 {f20[s3].mean()*100:+.2f}% −5%以下 {(f20[s3]<=-0.05).mean()*100:.0f}%")
