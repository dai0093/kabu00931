"""検証33：前半（〜2011）と後半（2012〜）で、なぜ結果が変わるのか。季節性と関連性を比べる。
A 基本の性質：年率リターン・ボラ・自己相関（1日／5日→次5日）・大きな下落日の翌日・新高値後20日
B 季節性：月別の平均月次リターン（前半・後半・符号一致）、急落40件の開始月、順位相関
C 関連性：日経とSOX前夜／ドル円／VIXの相関と、SOX前夜≤-4%の翌日の日経
結論は『前半・後半で同じ向きが出るか』で判断する（片方だけなら予測出来なかった）。"""
import warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
src = open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0]
exec(src)
nk_ = nk.reindex(cal).ffill(); r1 = nk_.pct_change()
H = {"前半": cal < mid, "後半": cal >= mid}
def dl(t):
    x = yf.download(t, start="1996-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return x
print("=== A 基本の性質 ===")
for k, m in H.items():
    r = r1[m].dropna(); n = len(r)
    ac1 = r.autocorr(1)
    r5 = nk_[m].pct_change(5); nx5 = nk_[m].pct_change(5).shift(-5)
    ac5 = pd.concat([r5, nx5], axis=1).dropna().corr().iloc[0, 1]
    big = r1[m] <= -0.02; nxt = r1.shift(-1)[m]
    f20 = (nk_.shift(-20) / nk_ - 1)[m]; hi = (nk_ > nk_.rolling(60).max().shift(1))[m]
    print(f"{k}: 年率リターン {((1+r).prod()**(252/n)-1)*100:+.1f}% 年率ボラ {r.std()*np.sqrt(252)*100:.1f}% 日次自己相関 {ac1:+.3f} 5日→次5日の相関 {ac5:+.3f}")
    print(f"   −2%以下の日 {int(big.sum())}日（年{big.sum()/(n/252):.1f}日）翌日 平均{nxt[big].mean()*100:+.2f}% 上昇の割合{(nxt[big]>0).mean()*100:.0f}% ／ 新高値の日 {int(hi.sum())}日 20日後 平均{f20[hi].mean()*100:+.2f}%（全日 {f20.mean()*100:+.2f}%）")
print("\n=== B 季節性 ===")
mo = nk_.resample("M").last().pct_change().dropna()
tab = {}
for k, lo, hi_ in (("前半", None, mid), ("後半", mid, None)):
    s = mo[lo:hi_] if lo else mo[:hi_]
    tab[k] = s.groupby(s.index.month).mean() * 100
    tab[k + "_正の年"] = s.groupby(s.index.month).apply(lambda x: (x > 0).mean() * 100)
T = pd.DataFrame(tab)
print("月 | 前半 平均%（上昇した年の割合） | 後半 平均%（上昇した年の割合） | 同じ向き")
for m_ in range(1, 13):
    a, b = T.loc[m_, "前半"], T.loc[m_, "後半"]
    print(f"{m_}月 | {a:+.2f}%（{T.loc[m_,'前半_正の年']:.0f}%）| {b:+.2f}%（{T.loc[m_,'後半_正の年']:.0f}%）| {'○' if a*b>0 else '×'}")
print(f"月別平均の順位相関（前半と後半） {T['前半'].rank().corr(T['後半'].rank()):+.2f}（12か月。0.58以上で有意の目安）  同じ向きの月 {int(((T['前半']*T['後半'])>0).sum())}/12")
ep_m = pd.Series([cal[a].month for a, tr in E]); ep_h = pd.Series([cal[a] < mid for a, tr in E])
print("急落40件の開始月  前半:", dict(ep_m[ep_h].value_counts().sort_index()), " 後半:", dict(ep_m[~ep_h].value_counts().sort_index()))
print("\n=== C 関連性 ===")
sx = sox.reindex(cal).ffill().pct_change().shift(1)
try:
    jp = dl("JPY=X").reindex(cal).ffill().pct_change(); vx = dl("^VIX").reindex(cal).ffill()
except Exception as e:
    jp = vx = None; print("ドル円・VIX取得失敗", e)
for k, m in H.items():
    d = pd.concat([r1, sx], axis=1).dropna()[m.reindex(pd.concat([r1, sx], axis=1).dropna().index, fill_value=False)] if False else pd.concat([r1[m], sx[m]], axis=1).dropna()
    line = f"{k}: 日経当日×SOX前夜 相関 {d.corr().iloc[0,1]:+.2f}"
    if jp is not None:
        d2 = pd.concat([r1[m], jp[m]], axis=1).dropna(); line += f" ／ 日経×ドル円(当日) {d2.corr().iloc[0,1]:+.2f}"
        d3 = pd.concat([r1[m], vx.diff().shift(1)[m]], axis=1).dropna(); line += f" ／ 日経×VIX前日変化 {d3.corr().iloc[0,1]:+.2f}"
        line += f" ／ VIX平均 {vx[m].mean():.1f}"
    print(line)
    b = sx[m] <= -0.04; nx = r1[m]
    print(f"   SOX前夜≤−4%の日 {int(b.sum())}日：日経の当日 平均{nx[b].mean()*100:+.2f}% 下落の割合{(nx[b]<0).mean()*100:.0f}% ／ 通常日 平均{nx[~b].mean()*100:+.2f}%")
