"""検証50：半期（120営業日）を期限に、今日の状態で『この半年どう持つか』を決めた場合の成績（前半/後半）。
毎日を起点に120営業日先までを評価（重なりあり）。選択肢：持ち続け／現金／防御方針C（新：維持20日＋社債0%は2007〜）／
半期ルール：起点の状態で半年間を決める（A 日経が200日線の上なら持つ、下なら現金 ／ B 高値から−10%以下なら現金 ／ C 200日線の上かつ高値から−10%以内なら持つ）。
評価：半年の騰落の平均・中央値・下位5%（悪い時）・マイナスになった割合。今の状態で各ルールが何を指すかも表示。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
G = {}; exec(open("scanner/compare28.py").read().split("hold = pd.Series(1.0, index=cal)")[0], G)
cal, sc0, run, mid, nk = G["cal"], np.asarray(G["score"]), G["run"], G["mid"], G["nk"]
x = yf.download(["HYG", "IEF"], start="2007-01-01", auto_adjust=True, progress=False)["Close"].dropna(); x.index = pd.to_datetime(x.index).tz_localize(None)
q = (x["HYG"] / x["IEF"]).pct_change(20); idx = cal.searchsorted(q.index, side="right"); m = idx < len(cal)
q = pd.Series(q.values[m], index=cal[idx[m]]); q = q[~q.index.duplicated(keep="last")].reindex(cal).ffill(); cc = (q <= -0.02).fillna(False).values
e = np.ones(len(sc0))
for i in range(len(sc0)):
    sh = sc0[max(0, i - 19):i + 1].max(); e[i] = 0 if cc[i] else 1.0 if sh == 0 else .5 if sh == 1 else .25 if sh == 2 else 0
polC = pd.Series(e, index=cal)
nkc = nk.reindex(cal).ffill(); r = nkc.pct_change().fillna(0)
rC = run(polC)   # 方針Cの日次リターン（翌日適用・手数料込み）
ma200 = nkc.rolling(200).mean(); dd = nkc / nkc.rolling(250, min_periods=60).max() - 1
H = 120
def fwd(rr):
    lr = np.log1p(rr).values; cs = np.concatenate([[0], np.cumsum(lr)])
    out = np.full(len(rr), np.nan)
    for i in range(len(rr) - H): out[i] = np.expm1(cs[i + 1 + H] - cs[i + 1])
    return pd.Series(out, index=rr.index)
F = {"持ち続け": fwd(r), "現金": pd.Series(0.0, index=cal).where(fwd(r).notna()), "防御方針C": fwd(rC)}
above = (nkc > ma200); deep = dd <= -0.10
F["A：200日線の上なら持つ"] = F["持ち続け"].where(above, 0.0).where(F["持ち続け"].notna())
F["B：高値から−10%以下なら現金"] = F["持ち続け"].where(~deep, 0.0).where(F["持ち続け"].notna())
F["C：Aかつ高値−10%以内"] = F["持ち続け"].where(above & ~deep, 0.0).where(F["持ち続け"].notna())
F["D：方針C、ただし200日線の下なら現金"] = F["防御方針C"].where(above, 0.0).where(F["持ち続け"].notna())
for nm, mm in (("前半(〜2011)", cal < mid), ("後半(2012〜)", cal >= mid)):
    print(f"\n=== {nm}：半年（120営業日）の騰落 ===")
    for k, s in F.items():
        v = s[mm].dropna() * 100
        print(f"{k} | 平均{v.mean():+.1f}% 中央値{v.median():+.1f}% 悪い時(下位5%){v.quantile(.05):+.1f}% マイナスの割合{(v<0).mean()*100:.0f}%")
print("\n=== 今と同じ状態（200日線の下 or 高値から−10%以下）から始めた半年 ===")
st = (~above) | deep
for nm, mm in (("前半", cal < mid), ("後半", cal >= mid)):
    v = F["持ち続け"][mm & st].dropna() * 100; c = F["防御方針C"][mm & st].dropna() * 100
    print(f"{nm}: 該当{len(v)}日 持ち続け 平均{v.mean():+.1f}% 下位5%{v.quantile(.05):+.1f}% マイナス{(v<0).mean()*100:.0f}% ／ 方針C 平均{c.mean():+.1f}% 下位5%{c.quantile(.05):+.1f}% マイナス{(c<0).mean()*100:.0f}%")
print(f"\n今 {cal[-1].date()}：日経 {nkc.iloc[-1]:,.0f} 200日線比 {(nkc.iloc[-1]/ma200.iloc[-1]-1)*100:+.1f}% 高値比 {dd.iloc[-1]*100:.1f}% 方針Cの目安 {polC.iloc[-1]*100:.0f}%")
