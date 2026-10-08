"""過去5年の検証。結果を data/backtest.json と data/backtest.md に書き出す。"""
import json
import os
from collections import defaultdict
import yfinance as yf
from core import add_indicators, is_signal, plan, simulate, CAPITAL, MAX_POSITIONS
from data import load
from universe import STOCKS

os.makedirs("data", exist_ok=True)
prices = load("5y")

# 1) 全銘柄のシグナルを列挙し、それぞれ売買をシミュレーション
cands = []
for code, df in prices.items():
    d = add_indicators(df)
    for i in range(len(d)):
        if not is_signal(d, i):
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p:
            continue
        res = simulate(d, i, p)
        if res["status"] != "closed":
            continue
        cands.append({"date": str(d.index[i].date()), "code": code,
                      "name": STOCKS[code],
                      "vol_ratio": float(d.Volume.iloc[i] / d.vol20.iloc[i]),
                      **p, **res})

# 2) 同時保有5銘柄・資金700万円の制約で、実際に取れた取引だけ残す
cands.sort(key=lambda t: (t["date"], -t["vol_ratio"]))
open_pos, trades = [], []
for t in cands:
    open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
    used = sum(o["buy"] * o["shares"] for o in open_pos)
    if len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL:
        continue
    if any(o["code"] == t["code"] for o in open_pos):
        continue
    open_pos.append(t)
    trades.append(t)

# 3) 集計
def stats(ts):
    n = len(ts)
    wins = [t for t in ts if t["hit"]]
    loss = [t for t in ts if not t["hit"]]
    gp = sum(t["pnl"] for t in wins)
    gl = -sum(t["pnl"] for t in loss)
    return {"trades": n, "hit": len(wins), "miss": len(loss),
            "win_rate": round(len(wins) / n * 100, 1) if n else 0,
            "total_pnl": round(gp - gl), "gross_profit": round(gp),
            "gross_loss": round(gl),
            "avg_win": round(gp / len(wins)) if wins else 0,
            "avg_loss": round(gl / len(loss)) if loss else 0,
            "profit_factor": round(gp / gl, 2) if gl else None}

by_year = defaultdict(list)
for t in trades:
    by_year[t["date"][:4]].append(t)

# 最大ドローダウン（決済順の累積損益）
eq, peak, mdd = 0, 0, 0
for t in sorted(trades, key=lambda t: t["exit_date"]):
    eq += t["pnl"]
    peak = max(peak, eq)
    mdd = min(mdd, eq - peak)

# 比較用：日経平均を同期間持ち続けた場合
bench = None
try:
    n225 = yf.download("^N225", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
    bench = round((float(n225.iloc[-1]) / float(n225.iloc[0]) - 1) * 100, 1)
except Exception:
    pass

reasons = defaultdict(int)
for t in trades:
    reasons[t["reason"]] += 1

result = {"all": stats(trades),
          "by_year": {y: stats(v) for y, v in sorted(by_year.items())},
          "max_drawdown": round(mdd), "nikkei_change_pct": bench,
          "exit_reasons": dict(reasons),
          "signals_total": len(cands), "stocks_loaded": len(prices),
          "trades": trades[-60:]}
with open("data/backtest.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

a = result["all"]
lines = ["# 検証結果（過去5年）", "",
         f"- 取得銘柄数: {len(prices)} / {len(STOCKS)}",
         f"- 取引数: {a['trades']}（予測出来た {a['hit']} / 出来なかった {a['miss']}）",
         f"- 勝率: {a['win_rate']}%",
         f"- 合計損益: {a['total_pnl']:,}円",
         f"- 平均利益 {a['avg_win']:,}円 / 平均損失 {a['avg_loss']:,}円",
         f"- PF（総利益÷総損失）: {a['profit_factor']}",
         f"- 最大ドローダウン: {result['max_drawdown']:,}円",
         f"- 日経平均の同期間騰落: {bench}%",
         f"- 決済理由: {dict(reasons)}", "", "## 年別"]
for y, s in result["by_year"].items():
    lines.append(f"- {y}: {s['trades']}回 勝率{s['win_rate']}% 損益{s['total_pnl']:,}円")
with open("data/backtest.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
