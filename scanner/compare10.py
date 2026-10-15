"""検証10：前日のうちに逆指値（前日終値 −X%で売り）を入れておき、当日の大引けで買い戻す
予測は使わない。安値が逆指値に届いた日だけ売れる（寄りで既に下なら寄りで約定）。
学習 2005-2016 で X を選び、試験 2017- で確かめる。対象：日経平均（1321の代わり）"""
import pandas as pd, yfinance as yf
x = yf.download("^N225", start="2004-01-01", auto_adjust=False, progress=False)
x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
x.index = pd.to_datetime(x.index).tz_localize(None)
x = x[(x.Open > 0) & (x.Low > 0)].dropna()
pc = x.Close.shift(1)
SLIP, FEE = 0.001, 0.0005
def run(X, a, b, cond=None):
    g = x[(x.index >= a) & (x.index < b)]; p = pc[g.index]
    ret = g.Close / p - 1
    stop = p * (1 - X)
    trig = g.Low <= stop
    if cond is not None: trig &= cond[g.index]
    exitp = pd.concat([g.Open, stop], axis=1).min(axis=1) * (1 - SLIP)
    day = ret.where(~trig, exitp / p - 1 - 2 * FEE)
    eq, eqb = (1 + day).cumprod(), (1 + ret).cumprod()
    crash = ret <= -0.03
    return {"n": int(trig.sum()), "crash": int(crash.sum()), "saved": int((trig & crash).sum()),
            "whip": int((trig & (ret > -X)).sum()), "st": eq.iloc[-1] - 1, "bh": eqb.iloc[-1] - 1,
            "mdd": float((eq / eq.cummax() - 1).min()), "mddb": float((eqb / eqb.cummax() - 1).min()),
            "crashavg": float(day[crash].mean()), "crashbh": float(ret[crash].mean())}
TR, TE, END = pd.Timestamp("2005-01-01"), pd.Timestamp("2017-01-01"), x.index[-1] + pd.Timedelta(days=1)
L, res = ["逆指値：前日終値 −X% で売り → 当日大引けで買い戻し（すべり0.1%・手数料0.05%×2）", ""], []
for X in (0.015, 0.02, 0.025, 0.03, 0.04):
    a, b = run(X, TR, TE), run(X, TE, END); res.append((X, a, b))
    for lab, r in (("学習", a), ("試験", b)):
        L.append(f"−{X*100:.1f}% {lab}：発動{r['n']}日（うち暴落日{r['saved']}／暴落{r['crash']}日、売った後に戻した日{r['whip']}）"
                 f"／暴落日の平均 {r['crashbh']*100:.2f}% → {r['crashavg']*100:.2f}%"
                 f"／ETFのみ {r['bh']*100:+.1f}% → 逆指値あり {r['st']*100:+.1f}%（差 {(r['st']-r['bh'])*100:+.1f}pt）"
                 f"／最大落ち込み {r['mddb']*100:.1f}% → {r['mdd']*100:.1f}%")
best = max(res, key=lambda t: t[1]["st"] - t[1]["bh"])
L.append(f"\n学習で一番良かった：−{best[0]*100:.1f}% → 試験の差 {(best[2]['st']-best[2]['bh'])*100:+.1f}pt → "
         + ("予測出来た" if best[2]["st"] > best[2]["bh"] else "予測出来なかった"))
L.append("\n## 2026年の暴落日")
for dt in x.index[(x.Close / pc - 1 <= -0.03) & (x.index.year == 2026)]:
    r, p = x.loc[dt], pc[dt]
    L.append(f"{dt.date()} 終値{(r.Close/p-1)*100:+.1f}% 寄り{(r.Open/p-1)*100:+.1f}% 安値{(r.Low/p-1)*100:+.1f}%"
             + "".join(f" / −{X*100:.1f}%逆指値なら {((min(r.Open, p*(1-X))*(1-SLIP))/p-1-2*FEE)*100:+.1f}%" if r.Low <= p*(1-X) else f" / −{X*100:.1f}%:不発" for X in (0.02, 0.03)))
open("data/compare10.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
