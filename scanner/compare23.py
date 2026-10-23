"""検証23：他AIの「価格警報」（異なる2業種が同時に-4%以下／日経-2%）を日次データで先読みなしに近い形で検証する。
日次で近似：銀行＝日本の金融群（JP）の1日中央値、半導体＝SOXの前夜1日変化。目的変数は検証16と同じ（10営業日内に日経-7%）。
前半・後半に分け、後半は前半の結果を見ずに同じ条件をそのまま適用。"""
import warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("out, rules, lines = [], [], []")[0])
def yf1(t):
    x = yf.download(t, start="2005-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None); return x["Close"].dropna()
al = lambda s: s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
sox = al(yf1("^SOX")); sox_d1_prev = (sox.pct_change() * 100).shift(1)   # 前夜の米国セッション
nk_d1 = nk.pct_change() * 100
jp1, us1, eu1 = F["JP"]["d1"], F["US"]["d1"], F["EU"]["d1"]
y = Y["C_10日内-7%"].astype(float)
h1 = valid & (nk.index <= mid); h2 = valid & (nk.index > mid)
b1, b2 = float(y[h1].mean()), float(y[h2].mean())
def rep(nm, s):
    s = s.fillna(False); o = []
    for lab, h, b in (("前半", h1, b1), ("後半", h2, b2)):
        m = s & h; n = int(m.sum()); o.append(f"{lab} {n}日 発生{(y[m].mean()*100 if n else 0):.0f}%(×{(y[m].mean()/b if n else 0):.1f})")
    print(f"{nm}: " + " / ".join(o))
print(f"基準の発生率 前半{b1*100:.0f}% 後半{b2*100:.0f}%")
S = {
 "日経1日≤-2%": nk_d1 <= -2,
 "日経1日≤-3%": nk_d1 <= -3,
 "銀行群1日≤-4%": jp1 <= -4,
 "銀行群1日≤-3%": jp1 <= -3,
 "銀行群1日≤-5%": jp1 <= -5,
 "SOX前夜≤-4%": sox_d1_prev <= -4,
 "SOX前夜≤-6%": sox_d1_prev <= -6,
 "他AI型：銀行群≤-4% かつ SOX前夜≤-4%": (jp1 <= -4) & (sox_d1_prev <= -4),
 "他AI型：日経≤-2% かつ 銀行群≤-4%": (nk_d1 <= -2) & (jp1 <= -4),
 "私の強警戒型：銀行群≤-5% かつ SOX前夜≤-4%": (jp1 <= -5) & (sox_d1_prev <= -4),
 "今朝型：銀行群≤-3% かつ SOX前夜≤-6%": (jp1 <= -3) & (sox_d1_prev <= -6),
}
for k, v in S.items(): rep(k, v)
ret = nk.pct_change().fillna(0)
def hyst(s, quiet_n, lvl):
    e = pd.Series(1.0, index=cal); st = 1.0; q = 0
    for k in range(len(cal)):
        e.iloc[k] = st
        if bool(s.iloc[k]): st, q = lvl, 0
        else:
            q += 1
            if q >= quiet_n: st = 1.0
    return e
def run(e): return e.shift(1).fillna(1.0) * ret - e.shift(1).fillna(1.0).diff().abs().fillna(0) * 0.001
def stats(r, a, b=None):
    r = r[a:b]; eq = (1 + r).cumprod(); return f"累積{(eq.iloc[-1]-1)*100:+.0f}% 最大下落{((eq/eq.cummax()-1).min())*100:.0f}%"
print("\n## 後半の成績（日経225、コスト込み、信号後10日は50%に縮小／5日は全額現金）")
print("持ちっぱなし:", stats(ret, mid))
for k in ["日経1日≤-2%", "他AI型：銀行群≤-4% かつ SOX前夜≤-4%", "私の強警戒型：銀行群≤-5% かつ SOX前夜≤-4%"]:
    s = S[k].fillna(False)
    for nm, q, l in (("50%縮小10日", 10, .5), ("全額現金5日", 5, 0.)):
        e = hyst(s, q, l); print(f"{k}→{nm}: {stats(run(e), mid)} 縮小日{(e[mid:]<1).mean()*100:.0f}%")
print("\n## 主要局面（持ちっぱなし → 他AI型50%縮小10日）")
s = S["他AI型：銀行群≤-4% かつ SOX前夜≤-4%"].fillna(False); e = hyst(s, 10, .5)
for nm, a, b in (("リーマン","2008-09-01","2008-12-31"),("コロナ","2020-01-15","2020-04-30"),("2022","2022-01-01","2022-12-31"),("24夏","2024-07-01","2024-09-30"),("25春","2025-03-01","2025-05-31")):
    print(f"{nm}: 保有 {stats(ret,a,b)} → 縮小 {stats(run(e),a,b)}")
print("\n今日型の直近発生日:", [str(d.date()) for d in S["他AI型：銀行群≤-4% かつ SOX前夜≤-4%"].fillna(False)[lambda x: x].index[-8:]])
