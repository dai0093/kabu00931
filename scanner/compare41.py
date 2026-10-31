"""検証41：①行動心理（群集の買い過熱・投げ売り）の指標を加えると、先行きの確率予測は良くなるか（前半学習→後半、後半学習→前半の両方向）
②『5日以内に−5%の確率がふだんの2倍以上』を方針Cの信号1本として足すと、成績はどう変わるか。
群集心理の代理指標：買い過熱＝25日線乖離・RSI14・連騰日数・60日騰落・出来高急増（1321）／投げ売り＝連続下落日数・VIXの急騰（20日平均比）・大陰線と出来高急増の同時発生（セリングクライマックス）・250日高値からの下落"""
import sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
sys.argv = ["x", "--test"]
src = open("scanner/outlook.py").read().split('res = {}')[0]
exec(src)
from sklearn.linear_model import LogisticRegression
v = yf.download("1321.T", start="1995-01-01", auto_adjust=False, progress=False); v.columns = [c[0] if isinstance(c, tuple) else c for c in v.columns]
v.index = pd.to_datetime(v.index).tz_localize(None); vol = (v["Volume"] * v["Close"]).reindex(cal)
d = C_f.diff(); up = d.clip(lower=0).rolling(14).mean(); dn = (-d.clip(upper=0)).rolling(14).mean(); rsi = 100 - 100 / (1 + up / dn)
def streak(s):
    o = np.zeros(len(s)); c = 0
    for i, x in enumerate(s.values):
        c = c + 1 if x else 0; o[i] = c
    return pd.Series(o, index=s.index)
vr = vol.rolling(5).mean() / vol.rolling(60).mean()
Bh = pd.DataFrame({"ov_ma25": C_f / C_f.rolling(25).mean() - 1, "ov_rsi": rsi, "ov_upstreak": streak(r1 > 0), "ov_r60": C_f.pct_change(60),
                   "ov_volspike": vr, "pn_dnstreak": streak(r1 < 0), "pn_vixspike": V / V.rolling(20).mean() - 1,
                   "pn_climax": ((r1 <= -0.03) & (vol / vol.rolling(60).mean() >= 2)).astype(float).rolling(5).max()}, index=cal)
FB = F.join(Bh)
def fit(X, y):
    mu, sd = X.mean(), X.std().replace(0, 1); return LogisticRegression(C=0.3, max_iter=3000).fit((X - mu) / sd, y), mu, sd
def pr(m, X): return m[0].predict_proba((X - m[1]) / m[2])[:, 1]
print("=== ①行動心理の指標を足した効果（Brierスキル：基準率比。＋が良い） ===")
print("項目 | 前半→後半：市場間のみ / ＋行動心理 | 後半→前半：市場間のみ / ＋行動心理")
OOS = {}
for k in ("5d_-5", "20d_-5", "20d_-10", "60d_-10", "60d_-20", "20d_up"):
    y = Y[k].rename("y"); row = []
    for nm, FF in (("市場間", F), ("＋行動", FB)):
        dd = FF.join(y).dropna(); sk = []
        for a, b in ((dd.index < mid, dd.index >= mid), (dd.index >= mid, dd.index < mid)):
            tr, te = dd[a], dd[b]; m = fit(tr.drop(columns="y"), tr.y); p = pr(m, te.drop(columns="y"))
            sk.append(1 - np.mean((p - te.y) ** 2) / np.mean((tr.y.mean() - te.y) ** 2))
            if k == "5d_-5": OOS.setdefault(nm, []).append(pd.Series(p, index=te.index))
        row.append(sk)
    print(f"{k} | {row[0][0]:+.3f} / {row[1][0]:+.3f} | {row[0][1]:+.3f} / {row[1][1]:+.3f}")
# 個別の行動指標：前半と後半で、上位20%の日の5日−5%発生率が同じ向きか
print("\n=== 行動心理の指標ひとつずつ（上位20%の日／下位20%の日の『5日以内に−5%』の発生率、前半・後半） ===")
y5 = Y["5d_-5"]
for c in Bh.columns:
    s = Bh[c]; out = []
    for m in (cal < mid, cal >= mid):
        x = s[m]; yy = y5[m]; ok = x.notna() & yy.notna(); x, yy = x[ok], yy[ok]
        if x.nunique() < 3: out.append("—"); continue
        hi, lo = yy[x >= x.quantile(.8)].mean(), yy[x <= x.quantile(.2)].mean(); out.append(f"{hi*100:.1f}%/{lo*100:.1f}%")
    print(f"{c}: 前半 {out[0]}  後半 {out[1]}")
# ② 方針Cに確率の信号を足す（両方向の未使用データでの予測確率を使う）
print("\n=== ②方針C＋『5日−5%の確率がふだんの2倍以上』を信号1本として加える ===")
src2 = open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0]
G = {}; exec(src2, G)
cal2, sc0, run, st, epi, mid2 = G["cal"], G["score"], G["run"], G["st"], G["epi"], G["mid"]
def pol(sc, hold=10):
    sc = np.asarray(sc); e = np.ones(len(sc))
    for i in range(len(sc)):
        sh = sc[max(0, i - hold + 1):i + 1].max(); e[i] = 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
    return pd.Series(e, index=cal2)
base = Y["5d_-5"].mean()
for nm in ("市場間", "＋行動"):
    p = pd.concat(OOS[nm]).sort_index(); p = p[~p.index.duplicated()].reindex(cal2).fillna(0)
    for mult in (2.0, 2.5, 3.0):
        add = (p >= mult * base).astype(int).values
        e = pol(np.asarray(sc0) + add); r = run(e); a1, d1 = st(r, None, mid2); a2, d2 = st(r, mid2, None); m, md, w = epi(r)
        print(f"C＋確率{mult}倍（{nm}） | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{m:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}% | 鳴った日 {add.mean()*100:.0f}%")
e = pol(sc0); r = run(e); a1, d1 = st(r, None, mid2); a2, d2 = st(r, mid2, None); m, md, w = epi(r)
print(f"C（今の方針） | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{m:.1f}% 最悪{w:.1f}% | 持ち高{e.mean()*100:.0f}%")
r = run(pd.Series(1.0, index=cal2)); a1, d1 = st(r, None, mid2); a2, d2 = st(r, mid2, None); m, md, w = epi(r)
print(f"持ちっぱなし | 前半 {a1:+.0f}%・{d1:.0f}% | 後半 {a2:+.0f}%・{d2:.0f}% | 急落40件 平均{m:.1f}% 最悪{w:.1f}%")
print("\n今日の行動心理の値:", {k: round(float(x), 3) for k, x in Bh.ffill().iloc[-1].items()})
