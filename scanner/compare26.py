"""検証26：「漏れないか」の総点検（暴落の見逃し・遅れのバックテスト）。
過去の日経の急落（10営業日内に-8%以上）を全部リストし、各ルールが ①事前に鳴ったか ②下げの途中で鳴った場合、鳴った時点でまだ何%下げが残っていたか ③誤報は年に何回か を測る。
ルールは今のTool（金融機関株価・SOX・日経・銀行群）と他AIの価格警報型。前半（〜2011）と後半（2012〜）で分けて表示。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare21.py").read().split('y = Y["C_10日内-7%"]')[0])
R = [("EU","d1",-6),("EU","d5",-15),("US","d1",-5),("US","d5",-10),("JP","d1",-5),("JP","d5",-10),("JP","dd",-25)]
hit = pd.DataFrame({f"{g}.{c}": (F[g][c] <= th).fillna(False) for g, c, th in R})
base = hit.any(axis=1)
ngrp = pd.concat([hit[[f"{g}.{c}" for g2,c,t in R if g2==g]].any(axis=1) for g in ("EU","US","JP")], axis=1).sum(axis=1)
sox_prev = (sox.pct_change() * 100).shift(1); nk_d1 = nk.pct_change() * 100
jp1, jp5 = F["JP"]["d1"], F["JP"]["d5"]
RULES = {
 "金融機関 基準(どれか)": base,
 "金融機関 2群同時": ngrp >= 2,
 "強警戒型:邦銀1日≤-5%かつSOX前夜≤-4%": (jp1 <= -5) & (sox_prev <= -4),
 "銀行群1日≤-4%": jp1 <= -4,
 "他AI型:銀行群≤-4%かつSOX前夜≤-4%": (jp1 <= -4) & (sox_prev <= -4),
 "日経1日≤-2%": nk_d1 <= -2,
 "日経1日≤-3%": nk_d1 <= -3,
 "SOX前夜≤-4%": sox_prev <= -4,
 "日経5日≤-5%": (nk.pct_change(5) * 100) <= -5,
 "いずれか(上記すべての和)": None,
}
RULES["いずれか(上記すべての和)"] = pd.concat([v.fillna(False) for k, v in RULES.items() if v is not None], axis=1).any(axis=1)
n = len(cal); c = nk.values
fm = np.full(n, np.nan)
for i in range(n - 10):
    fm[i] = c[i + 1:i + 11].min() / c[i] - 1
ev_day = pd.Series(fm <= -0.08, index=cal)
# エピソード化
eps, i = [], 0
days = np.where(ev_day.values)[0]
for d in days:
    if eps and d - eps[-1][1] <= 10: eps[-1][1] = d
    else: eps.append([d, d])
E = []
for a, b in eps:
    end = min(n - 1, b + 10); trough = int(a + np.argmin(c[a:end + 1]))
    E.append((a, end, trough, float(c[trough] / c[a] - 1)))
print(f"急落エピソード（10営業日内に-8%以上）: {len(E)}件。前半{sum(1 for e in E if cal[e[0]] < mid)}件 後半{sum(1 for e in E if cal[e[0]] >= mid)}件")
for a, end, tr, dd in E:
    if dd <= -0.12 or cal[a] >= pd.Timestamp("2024-01-01"): print(f"  {cal[a].date()} 〜 谷{cal[tr].date()} 下落{dd*100:.0f}%")
yrs = (cal[-1] - cal[0]).days / 365.25
for nm, s in RULES.items():
    s = s.fillna(False)
    pre = caught = 0; rem = []; tot = []; late = 0
    for a, end, tr, dd in E:
        w_pre = s.iloc[max(0, a - 5):a].any()
        w_in = s.iloc[a:tr + 1]
        if w_pre: pre += 1
        if w_pre or w_in.any(): caught += 1
        if not w_pre and w_in.any():
            f = a + int(np.argmax(w_in.values)); rem.append(float(c[tr] / c[f] - 1)); tot.append(dd)
    # 誤報：信号日のうち、10営業日内に-8%が来なかった日の割合
    sd = s & pd.Series(~np.isnan(fm), index=cal); ok = sd & ev_day
    prec = float(ok.sum() / sd.sum()) if sd.sum() else 0
    for lab, a0, a1 in (("全期間", cal[0], cal[-1]), ("前半", cal[0], mid), ("後半", mid, cal[-1])):
        pass
    print(f"\n■ {nm}\n  見逃さず捕捉 {caught}/{len(E)}件（うち事前に鳴った {pre}件）／ 下げの途中で鳴った場合、鳴った時点で残っていた下げ: 中央値{(np.median(rem)*100 if rem else 0):.1f}%（その急落の全体は中央値{(np.median(tot)*100 if tot else 0):.1f}%）／ 信号日{int(sd.sum())}日（年{sd.sum()/yrs:.1f}日）、そのうち実際に急落が来た割合{prec*100:.0f}%")
    h = [(a, end, tr, dd) for a, end, tr, dd in E if cal[a] >= mid]
    c2 = sum(1 for a, end, tr, dd in h if s.iloc[max(0, a - 5):end + 1].any()); p2 = sum(1 for a, end, tr, dd in h if s.iloc[max(0, a - 5):a].any())
    print(f"  後半のみ: 捕捉 {c2}/{len(h)}件（事前 {p2}件）")
