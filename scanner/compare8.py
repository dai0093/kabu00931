"""検証8（寄りで売る現実の計算）：暴落の事前警告（後出しなし）
前日までに分かる情報だけで「明日は日経を持たない（現金）」と判断できたか。
- 暴落日：日経平均の1日騰落 −3%以下
- 警告候補（東京の寄り付き前に分かるもの）：
  米SOX指数の前夜騰落、VIXの水準と前日比、米10年金利の5日変化、日経の25日線・5日騰落
- 学習 2005-2016 で条件を選び、試験 2017-2026 で確かめる
- 実際の使い方：日経ETFを持ち、警告の出た日だけ現金にする（売買0.05%×2）"""
import itertools, json
import pandas as pd, yfinance as yf

def get(s):
    x = yf.download(s, start="2003-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None)
    return x["Close"].dropna()

nk, sox, vix, tnx = get("^N225"), get("^SOX"), get("^VIX"), get("^TNX")
_o = yf.download("^N225", start="2003-01-01", auto_adjust=False, progress=False)
_o.columns = [c[0] if isinstance(c, tuple) else c for c in _o.columns]
_o.index = pd.to_datetime(_o.index).tz_localize(None)
nko = _o["Open"].reindex(nk.index)
if tnx.median() > 20: tnx = tnx / 10
# 東京の日 t の寄り付き前に分かる米国の値 = t より前の最後の米国終値
us = pd.DataFrame({"sox": sox, "vix": vix, "tnx": tnx}).ffill()
f = pd.DataFrame(index=nk.index)
f["ret"] = nk.pct_change()
f["gap"] = nko / nk.shift(1) - 1   # 寄り付きで売っても避けられない部分
prev = lambda s: s.reindex(f.index, method=None).pipe(lambda _: s)
def asof_before(s):
    idx = s.index.searchsorted(f.index, side="left") - 1
    return pd.Series([s.iloc[i] if i >= 0 else float("nan") for i in idx], index=f.index)
f["sox1"] = asof_before(us["sox"].pct_change())
f["sox5"] = asof_before(us["sox"].pct_change(5))
f["vix"] = asof_before(us["vix"])
f["vix1"] = asof_before(us["vix"].pct_change())
f["tnx5"] = asof_before(us["tnx"].diff(5))
f["nk_below"] = (nk < nk.rolling(25).mean()).shift(1)
f["nk5"] = nk.pct_change(5).shift(1)
f = f.dropna()

C = {
 "SOX前夜 −3%以下": lambda r: r.sox1 <= -0.03,
 "SOX前夜 −4%以下": lambda r: r.sox1 <= -0.04,
 "SOX前夜 −5%以下": lambda r: r.sox1 <= -0.05,
 "SOX5日 −8%以下": lambda r: r.sox5 <= -0.08,
 "SOX5日 −10%以下": lambda r: r.sox5 <= -0.10,
 "VIX 25以上": lambda r: r.vix >= 25,
 "VIX 30以上": lambda r: r.vix >= 30,
 "VIX前日比 +20%以上": lambda r: r.vix1 >= 0.20,
 "VIX前日比 +30%以上": lambda r: r.vix1 >= 0.30,
 "米10年 5日で+0.25%以上": lambda r: r.tnx5 >= 0.25,
 "日経25日線の下": lambda r: bool(r.nk_below),
 "日経5日 −4%以下": lambda r: r.nk5 <= -0.04,
}
for a, b in (("SOX前夜 −3%以下", "日経25日線の下"), ("SOX前夜 −3%以下", "VIX前日比 +20%以上"),
             ("VIX前日比 +20%以上", "日経25日線の下"), ("SOX5日 −8%以下", "日経25日線の下")):
    C[f"{a} かつ {b}"] = lambda r, a=a, b=b: C[a](r) and C[b](r)
for a, b in (("SOX前夜 −4%以下", "VIX前日比 +30%以上"), ("SOX前夜 −3%以下", "VIX 30以上")):
    C[f"{a} または {b}"] = lambda r, a=a, b=b: C[a](r) or C[b](r)

FEE = 0.0005
def evaluate(sig, a, b):
    g = f[(f.index >= a) & (f.index < b)]
    s = sig[(sig.index >= a) & (sig.index < b)]
    crash = g.ret <= -0.03
    hit = int((s & crash).sum()); nc = int(crash.sum())
    on = int(s.sum())
    # ETF保有、警告の日は現金。切替の度に手数料
    sw = s.astype(int).diff().abs().fillna(0)
    day = g.ret.where(~s, g.gap) - s.astype(int) * 2 * FEE   # 警告日：寄りで売り・大引けで買い戻し
    strat = (1 + day).prod()
    bh = (1 + g.ret).prod()
    # 最大落ち込み
    eq = (1 + day).cumprod(); mdd = float((eq / eq.cummax() - 1).min())
    eqb = (1 + g.ret).cumprod(); mddb = float((eqb / eqb.cummax() - 1).min())
    return {"crash": nc, "caught": hit, "alarms": on, "precision": hit / on if on else 0,
            "avoided": float((g.ret - g.gap)[s & crash].mean()) if hit else 0.0, "avoided_loss": float(g.ret[s & crash].sum()), "missed_gain": float(g.ret[s & (g.ret > 0)].sum()),
            "strat": strat - 1, "bh": bh - 1, "mdd": mdd, "mddb": mddb}

TR, TE, END = pd.Timestamp("2005-01-01"), pd.Timestamp("2017-01-01"), f.index[-1] + pd.Timedelta(days=1)
rows = []
for nm, fn in C.items():
    sig = f.apply(fn, axis=1).astype(bool)
    rows.append((nm, sig, evaluate(sig, TR, TE), evaluate(sig, TE, END)))
rows.sort(key=lambda x: -(x[2]["strat"] - x[2]["bh"]))
L = [f"学習 2005-2016 / 試験 2017-{f.index[-1].date()}　暴落日＝日経 −3%以下", ""]
for nm, sig, a, b in rows:
    L.append(f"### {nm}")
    for lab, r in (("学習", a), ("試験", b)):
        L.append(f"{lab}：暴落{r['crash']}日中 事前警告{r['caught']}日（{r['caught']/max(r['crash'],1)*100:.0f}%）"
                 f"／警告{r['alarms']}日のうち当たり{r['precision']*100:.0f}%"
                 f"／ETFのみ {r['bh']*100:+.1f}% → 警告で現金 {r['strat']*100:+.1f}%（差 {(r['strat']-r['bh'])*100:+.1f}pt）"
                 f"／暴落日に避けられた幅 平均{r['avoided']*100:.1f}%"
                 f"／最大落ち込み {r['mddb']*100:.1f}% → {r['mdd']*100:.1f}%")
best = rows[0]
L += ["", f"学習で一番良かった：{best[0]} → 試験の差 {(best[3]['strat']-best[3]['bh'])*100:+.1f}pt → "
      + ("予測出来た" if best[3]["strat"] > best[3]["bh"] else "予測出来なかった")]
# 直近の暴落日と今日
L.append("\n## 直近の大きな下落日に警告が出ていたか")
big = f[f.ret <= -0.03].tail(12)
for dt, r in big.iterrows():
    on = [nm for nm, sig, a, b in rows[:5] if sig.get(dt, False)]
    L.append(f"{dt.date()} 日経{r.ret*100:+.1f}%（寄り{r.gap*100:+.1f}%） SOX前夜{r.sox1*100:+.1f}% VIX{r.vix:.1f}（前日比{r.vix1*100:+.0f}%） 25日線{'下' if r.nk_below else '上'} → 上位5条件の警告：{'、'.join(on) or 'なし'}")
for dt in f.index[-4:]:
    r = f.loc[dt]
    L.append(f"{dt.date()} 日経{r.ret*100:+.1f}%（寄り{r.gap*100:+.1f}%） SOX前夜{r.sox1*100:+.1f}% VIX{r.vix:.1f}（前日比{r.vix1*100:+.0f}%） 米10年5日{r.tnx5:+.2f} 25日線{'下' if r.nk_below else '上'}")
open("data/compare8.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
