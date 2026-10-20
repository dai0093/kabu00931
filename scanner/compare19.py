"""検証19：前半だけで基準を決め、後半で試す（先読みなし）。
前半（〜2015-11）のデータだけで、compare16と同じ候補（群×指標×閾値）から「10営業日内に日経-7%」の発生率が前半平均の3倍以上（n≥20）になる条件を選び、
その「どれか」を点灯条件とする。選んだ条件を後半（2015-11〜）にそのまま当て、①発生率 ②現金化ルールの成績 を持ちっぱなしと比べる。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("out, rules, lines = [], [], []")[0])
y = Y["C_10日内-7%"]
h1 = valid & (nk.index <= mid); h2 = valid & (nk.index > mid)
b1, b2 = float(y[h1].mean()), float(y[h2].mean())
sel = []
for g, f in F.items():
    for c in ("d1", "d5", "dd"):
        s = f[c]
        for th in [-1, -1.5, -2, -3, -4, -5, -6, -8, -10, -15, -20, -25]:
            m = (s <= th) & h1 & s.notna(); n = int(m.sum())
            if n >= 20 and y[m].mean() / b1 >= 3.0: sel.append((g, c, th, n, float(y[m].mean()) / b1))
# 同じ群・指標は最も緩い閾値だけ残す
best = {}
for g, c, th, n, l in sel:
    if (g, c) not in best or th > best[(g, c)][0]: best[(g, c)] = (th, n, l)
print("前半だけで選んだ点灯条件（前半の発生率が前半平均の3倍以上）:")
for (g, c), (th, n, l) in best.items(): print(f"  {g}.{c} ≤{th}  前半n={n} ×{l:.1f}")
lit = pd.Series(False, index=cal)
for (g, c), (th, n, l) in best.items(): lit |= (F[g][c] <= th).fillna(False)
for lab, h, b in (("前半（学習）", h1, b1), ("後半（未見）", h2, b2)):
    m = lit & h; n = int(m.sum())
    print(f"{lab}: 点灯{n}日 発生{(y[m].mean()*100 if n else 0):.0f}%（平均{b*100:.1f}% の ×{(y[m].mean()/b if n else 0):.1f}）")
ret = nk.pct_change().fillna(0)
hold = pd.Series(1.0, index=cal); st = 1.0; quiet = 0
for k in range(len(cal)):
    hold.iloc[k] = st
    if lit.iloc[k]: st, quiet = 0.0, 0
    else:
        quiet += 1
        if quiet >= 5: st = 1.0
strat = hold.shift(1).fillna(1) * ret
def stats(r, a, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{((eq/eq.cummax()-1).min())*100:.0f}%"
print("\n後半（2015-11〜）の現金化ルール（前半で決めた条件）:", stats(strat, mid), "／ 持ちっぱなし:", stats(ret, mid), f"／ 現金の日数{(hold[mid:]==0).mean()*100:.0f}%")
for nm, a, b in (("コロナ 2020-01〜04", "2020-01-15", "2020-04-30"), ("2022年", "2022-01-01", "2022-12-31"),
                 ("2024-07〜09", "2024-07-01", "2024-09-30"), ("2025-03〜05", "2025-03-01", "2025-05-31")):
    print(f"  {nm}  ルール: {stats(strat, a, b)} ／ 持ちっぱなし: {stats(ret, a, b)}")
print("今日の点灯:", bool(lit.iloc[-1]))
