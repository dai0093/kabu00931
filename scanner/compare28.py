"""検証28：「確率が低くても暴落を避けたい」前提の防御方針のバックテスト。
広い信号（日経・SOX・銀行群・金融機関）の鳴った本数で、持ち高を段階的に落とし、一定日数たったら戻す。信号は当日引け後に判定し、翌営業日から反映（先読みなし）。コスト：持ち高の変更1.0あたり0.1%。
評価：①累積と最大下落（前半・後半）②急落40件（検証26）の始点から谷までの損失を、持ちっぱなしと比較 ③平均の持ち高。トレンド（200日線割れ）も比較。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare26.py").read().split("n = len(cal); c = nk.values")[0])
n = len(cal); c = nk.values
fm = np.full(n, np.nan)
for i in range(n - 10): fm[i] = c[i + 1:i + 11].min() / c[i] - 1
ev_day = pd.Series(fm <= -0.08, index=cal); eps, days = [], np.where(ev_day.values)[0]
for d in days:
    if eps and d - eps[-1][1] <= 10: eps[-1][1] = d
    else: eps.append([d, d])
E = []
for a, b in eps:
    end = min(n - 1, b + 10); tr = int(a + np.argmin(c[a:end + 1])); E.append((a, tr))
K = ["金融機関 基準(どれか)", "銀行群1日≤-4%", "日経1日≤-3%", "SOX前夜≤-4%", "日経5日≤-5%", "日経1日≤-2%"]
score = sum(RULES[k].fillna(False).astype(int) for k in K)
ma200 = nk.rolling(200).mean(); below = (nk < ma200).fillna(False)
ret = nk.pct_change().fillna(0)
def policy(l1, l2, l3, hold, ma=None):
    sh = score.rolling(hold, min_periods=1).max()
    e = pd.Series(1.0, index=cal)
    e[sh >= 1] = l1; e[sh >= 2] = min(l2, l1); e[sh >= 3] = min(l3, l2, l1)
    if ma is not None: e = np.minimum(e, np.where(below, ma, 1.0))
    return pd.Series(e, index=cal)
def run(e):
    ex = e.shift(1).fillna(1.0); return ex * ret - ex.diff().abs().fillna(0) * 0.001
def st(r, a=None, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return (eq.iloc[-1] - 1) * 100, ((eq / eq.cummax() - 1).min()) * 100
def epi(r):
    eq = (1 + r).cumprod().values; L = [eq[tr] / eq[a] - 1 for a, tr in E]; return np.mean(L) * 100, np.median(L) * 100, min(L) * 100
hold = pd.Series(1.0, index=cal)
P = {"持ちっぱなし": hold,
 "A: 1本→75% 2本→50% 3本→25% (5日)": policy(.75, .5, .25, 5),
 "B: 同上 (10日)": policy(.75, .5, .25, 10),
 "C: 1本→50% 2本→25% 3本→0% (10日)": policy(.5, .25, 0, 10),
 "D: 1本でも鳴れば全額現金 (5日)": policy(0, 0, 0, 5),
 "E: 200日線割れで50%": pd.Series(np.where(below, .5, 1.0), index=cal),
 "F: B＋200日線割れで50%": policy(.75, .5, .25, 10, ma=.5),
 "G: C＋200日線割れで50%": policy(.5, .25, 0, 10, ma=.5)}
print(f"信号の本数: 1本以上の日{int((score>=1).sum())}日({(score>=1).mean()*100:.0f}%) 2本以上{int((score>=2).sum())}日 3本以上{int((score>=3).sum())}日  / 急落{len(E)}件")
print("\n方針 | 前半 累積・最大下落 | 後半 累積・最大下落 | 急落40件の平均/中央値/最悪の損失 | 平均持ち高")
rows = {}
for nm, e in P.items():
    r = run(e); a1, d1 = st(r, None, mid); a2, d2 = st(r, mid, None); m, md, w = epi(r)
    rows[nm] = (a2, d2, m)
    print(f"{nm} | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落 平均{m:.1f}% 中央{md:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
print("\n主要局面（持ちっぱなし → 方針B／方針C）")
for nm_, a, b in (("リーマン", "2008-09-01", "2008-12-31"), ("コロナ", "2020-01-15", "2020-04-30"), ("2024夏", "2024-07-01", "2024-09-30"), ("2025春", "2025-03-01", "2025-05-31"), ("2026/10(今回)", "2026-10-01", "2026-10-23")):
    f = lambda e: st(run(e), a, b)
    print(f"{nm_}: 保有 {f(hold)[0]:+.0f}%(最大下落{f(hold)[1]:.0f}%) → B {f(P['B: 同上 (10日)'])[0]:+.0f}%({f(P['B: 同上 (10日)'])[1]:.0f}%) / C {f(P['C: 1本→50% 2本→25% 3本→0% (10日)'])[0]:+.0f}%({f(P['C: 1本→50% 2本→25% 3本→0% (10日)'])[1]:.0f}%)")
print("\n今日の本数:", int(score.iloc[-1]), "直近10日の最大:", int(score.iloc[-10:].max()), " 200日線:", "割れ" if bool(below.iloc[-1]) else "上")
