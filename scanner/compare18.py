"""検証18：リーマン型の暴落を避けられたか。過去の大きな下落局面で、金融機関株価の判定が「いつ」点灯し、その時点から底までどれだけ下げが残っていたか。
局面＝日経の高値から-20%以上下げた局面（高値日〜底の日）。各局面で、高値後の最初の「接近」「点灯」日と、その日の日経→底の下落率を出す。
あわせて、点灯が出たら日経を売り（現金化）、点灯が解除されたら買い戻す単純ルールの成績（全期間・各局面）を、持ちっぱなしと比べる。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("out, rules, lines = [], [], []")[0])
def anyr(R):
    m = pd.Series(False, index=cal)
    for g, c, th in R: m |= (F[g][c] <= th).fillna(False)
    return m
LITR = [("EU", "d5", -15), ("US", "d1", -5), ("US", "d5", -10), ("JP", "d5", -10)]
NEARR = [("PC", "d5", -8), ("EU", "d1", -3), ("EU", "d5", -8), ("US", "d5", -5), ("JP", "d5", -6)]
lit = anyr(LITR); near = anyr(NEARR) | lit
# 局面の検出：高値から-20%に達した局面
eps, peak, pd_, i = [], nk.iloc[0], nk.index[0], 0
state = "up"; tr, trd = None, None
for d, v in nk.items():
    if state == "up":
        if v > peak: peak, pd_ = v, d
        elif v / peak - 1 <= -0.20: state = "down"; tr, trd = v, d
    else:
        if v < tr: tr, trd = v, d
        if v / tr - 1 >= 0.15:
            eps.append((pd_, peak, trd, tr)); state, peak, pd_ = "up", v, d
if state == "down": eps.append((pd_, peak, trd, tr))
print("## 日経が高値から-20%以上下げた局面と、判定が点灯した時期")
for pdv, pk, td, tv in eps:
    seg = nk.index[(nk.index >= pdv) & (nk.index <= td)]
    f = lambda s: next((d for d in seg if s.get(d, False)), None)
    fn, fl = f(near), f(lit)
    o = f"{pdv.date()} 高値{pk:,.0f} → {td.date()} 底{tv:,.0f}（{(tv/pk-1)*100:.0f}%）"
    for nm, d in (("最初の接近", fn), ("最初の点灯", fl)):
        o += f"\n   {nm}: " + (f"{d.date()} 日経{nk[d]:,.0f}（高値から{(nk[d]/pk-1)*100:.0f}%）→ 底まであと{(tv/nk[d]-1)*100:.0f}%" if d is not None else "なし")
    print(o)
# 単純ルール：前日に点灯なら翌日は現金（日経を持たない）。点灯が5日連続で出ない状態で復帰
ret = nk.pct_change().fillna(0)
sig = lit.copy()
hold = pd.Series(1.0, index=cal); st = 1.0; quiet = 0
for k, d in enumerate(cal):
    hold.iloc[k] = st
    if sig.iloc[k]: st, quiet = 0.0, 0
    else:
        quiet += 1
        if quiet >= 5: st = 1.0
strat = (hold.shift(1).fillna(1) * ret)
def stats(r, a=None, b=None):
    r = r[a:b] if a is not None else r
    eq = (1 + r).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{dd*100:.0f}%"
print("\n## 単純ルール（金融機関株価の点灯→日経を持たない、点灯なし5日で復帰）。持ちっぱなしと比較（日経現物、コスト無視）")
print("全期間   ルール:", stats(strat), "／ 持ちっぱなし:", stats(ret), f"／ 現金の日数{(hold==0).mean()*100:.0f}%")
for nm, a, b in (("リーマン 2007-07〜2009-03", "2007-07-01", "2009-03-31"), ("コロナ 2020-01〜2020-04", "2020-01-15", "2020-04-30"),
                 ("2022年", "2022-01-01", "2022-12-31"), ("2024-07〜09", "2024-07-01", "2024-09-30"), ("2025-03〜05", "2025-03-01", "2025-05-31"),
                 ("2026-09〜10", "2026-09-01", "2026-10-20")):
    print(f"{nm}  ルール:", stats(strat, a, b), "／ 持ちっぱなし:", stats(ret, a, b))
