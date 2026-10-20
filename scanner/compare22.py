"""検証22：他AIの仕様v3「経路B：原因が分からなくても市場から防衛」の閾値（指数が1営業日-3%以上、または5営業日-7%以上下落）を、日経で検証する。
急落「後」の経路なので、問う点は「その日の終値で縮小した場合、その後の下落を避けられたか（反発で損をしないか）」。
信号日dの終値で縮小→翌営業日以降のリターンを見る。前半/後半に分ける。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("out, rules, lines = [], [], []")[0])
r1, r5 = nk.pct_change(), nk.pct_change(5)
f10 = nk.shift(-10) / nk - 1                      # 信号日の終値からの10営業日リターン
fmin = pd.concat([nk.shift(-k) / nk - 1 for k in range(1, 11)], axis=1).min(axis=1)
tests = {"1日≤-3%": r1 <= -0.03, "5日≤-7%": r5 <= -0.07, "どちらか(v3経路B)": (r1 <= -0.03) | (r5 <= -0.07),
         "1日≤-5%": r1 <= -0.05, "5日≤-10%": r5 <= -0.10}
for nm, sig in tests.items():
    print(f"\n## {nm}")
    for lab, h in (("前半", nk.index <= mid), ("後半", nk.index > mid)):
        m = sig & h & f10.notna(); n = int(m.sum())
        if n == 0: print(f"  {lab}: 0日"); continue
        print(f"  {lab}: {n}日  その後10日の平均リターン {f10[m].mean()*100:+.1f}%  10日内に更に-7%以下になる割合 {(fmin[m] <= -0.07).mean()*100:.0f}%  10日後にプラスの割合 {(f10[m] > 0).mean()*100:.0f}%  （全期間平均 {f10[h&f10.notna()].mean()*100:+.1f}%）")
# 信号日の翌日から50%縮小→10営業日保有で戻す。コスト0.1%
ret = nk.pct_change().fillna(0)
def sim(sig, lvl=0.5, hold=10):
    e = pd.Series(1.0, index=cal); left = 0
    for k in range(len(cal)):
        e.iloc[k] = lvl if left > 0 else 1.0
        if sig.iloc[k]: left = hold
        elif left > 0: left -= 1
    x = e.shift(1).fillna(1.0); return x * ret - x.diff().abs().fillna(0) * 0.001
def stats(r, a=None, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{((eq/eq.cummax()-1).min())*100:.0f}%"
sig = tests["どちらか(v3経路B)"]
print("\n## v3経路B→50%縮小(10日)の成績")
print("後半 ルール:", stats(sim(sig), mid), "／ 持ちっぱなし:", stats(ret, mid))
print("リーマン期 ルール:", stats(sim(sig), "2007-07-01", "2009-03-31"), "／ 持ちっぱなし:", stats(ret, "2007-07-01", "2009-03-31"))
for nm, a, b in (("コロナ", "2020-01-15", "2020-04-30"), ("2022", "2022-01-01", "2022-12-31"), ("2024-07〜09", "2024-07-01", "2024-09-30"), ("2025-03〜05", "2025-03-01", "2025-05-31")):
    print(f"{nm}: ルール {stats(sim(sig), a, b)} ／ 持ちっぱなし {stats(ret, a, b)}")
