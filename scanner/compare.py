"""改良案の比較検証（過去5年・同じ資金制約）。data/compare.md に書き出す。"""
import json
import yfinance as yf
from core import add_indicators, is_signal, plan, simulate, CAPITAL, MAX_POSITIONS
from data import load

prices = load("5y")
frames = {c: add_indicators(df) for c, df in prices.items()}
n225 = yf.download("^N225", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
n_sma75 = n225.rolling(75).mean()
n_ret60 = n225.pct_change(60)


def market_ok(date):
    """日経平均が75日線より上か（相場全体が上向きか）"""
    if date not in n225.index or n_sma75.isna()[date]:
        return False
    return bool(n225[date] > n_sma75[date])


def strong(d, i):
    """直近60日で日経平均より強い銘柄か"""
    date = d.index[i]
    if i < 60 or date not in n_ret60.index:
        return False
    r = d.Close.iloc[i] / d.Close.iloc[i - 60] - 1
    return bool(r > n_ret60[date])


SCENARIOS = {
    "A 現行": dict(mkt=False, rs=False, tgt=3.0),
    "B 相場フィルタ": dict(mkt=True, rs=False, tgt=3.0),
    "C 相対強度": dict(mkt=False, rs=True, tgt=3.0),
    "D 相場+相対強度": dict(mkt=True, rs=True, tgt=3.0),
    "E D+利確5ATR": dict(mkt=True, rs=True, tgt=5.0),
    "F B+利確5ATR": dict(mkt=True, rs=False, tgt=5.0),
}


def run(cfg):
    cands = []
    for code, d in frames.items():
        for i in range(len(d)):
            if not is_signal(d, i):
                continue
            if cfg["mkt"] and not market_ok(d.index[i]):
                continue
            if cfg["rs"] and not strong(d, i):
                continue
            p = plan(d.Close.iloc[i], d.atr.iloc[i], cfg["tgt"])
            if not p:
                continue
            r = simulate(d, i, p)
            if r["status"] == "closed":
                cands.append({"date": str(d.index[i].date()), "code": code,
                              "vr": d.Volume.iloc[i] / d.vol20.iloc[i], **p, **r})
    cands.sort(key=lambda t: (t["date"], -t["vr"]))
    open_pos, trades = [], []
    for t in cands:
        open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        if (len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL
                or any(o["code"] == t["code"] for o in open_pos)):
            continue
        open_pos.append(t)
        trades.append(t)
    wins = [t for t in trades if t["hit"]]
    gp = sum(t["pnl"] for t in wins)
    gl = -sum(t["pnl"] for t in trades if not t["hit"])
    eq = peak = mdd = 0
    for t in sorted(trades, key=lambda t: t["exit_date"]):
        eq += t["pnl"]; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    years = {}
    for t in trades:
        years[t["date"][:4]] = years.get(t["date"][:4], 0) + t["pnl"]
    return {"n": len(trades), "hit": len(wins), "miss": len(trades) - len(wins),
            "gp": round(gp), "gl": round(gl), "pnl": round(gp - gl),
            "pf": round(gp / gl, 2) if gl else None, "mdd": round(mdd),
            "years": {y: round(v) for y, v in sorted(years.items())}}


bench = float(n225.iloc[-1]) / float(n225.iloc[0]) - 1
res = {k: run(v) for k, v in SCENARIOS.items()}
json.dump({"bench_pct": round(bench * 100, 1), "scenarios": res},
          open("data/compare.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = [f"日経平均5年: +{bench*100:.1f}% → 700万円なら +{CAPITAL*bench:,.0f}円", ""]
for k, r in res.items():
    lines.append(f"## {k}\n- 取引{r['n']} 出来た{r['hit']} 出来なかった{r['miss']}"
                 f"\n- 総利益{r['gp']:,} 総損失{r['gl']:,} 差引{r['pnl']:,} PF{r['pf']}"
                 f"\n- 最大DD{r['mdd']:,}\n- 年別{r['years']}\n")
open("data/compare.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
