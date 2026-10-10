"""検証6：後出しチェック（前半で条件を選び、後半で試す）＋現実のコスト
前半（学習）：2021-10〜2023-12　後半（試験）：2024-01〜2026-10
コスト：
- 約定の厳しさ：翌日の安値が指値より0.2%以上下がった時だけ約定（触れただけは不成立）
- 値段のずれ：買いは0.1%高く、売りは0.1%安く約定
- ETFの乗り換え：売り買いの度に0.05%
- 税金：年間の売買益がプラスなら20.315%（ETF側の値上がり益は売らないので非課税扱い）
条件の候補：売買代金 10/30/50/100/200億円 × VIXで買い停止 あり/なし"""
import json
import pandas as pd
from core import plan, add_indicators, CAPITAL, MAX_POSITIONS
from data import load
import strategy
from strategy import is_breakout
from risk import factors, risk_off

SPLIT = pd.Timestamp("2024-01-01")
SLIP, ETF_FEE, TAX, FILL = 0.001, 0.0005, 0.20315, 0.998

U = json.load(open("data/universe_all.json", encoding="utf-8"))
raw = load("5y", codes=list(U), size=50, wait=10)
frames = {}
for c, df in raw.items():
    df = df.copy(); df.index = pd.to_datetime(df.index).tz_localize(None)
    frames[c] = add_indicators(df)
F = factors("6y")
roff = {d: risk_off(F.loc[d]) for d in F.index}
at = lambda d: F.index[max(F.index.searchsorted(d, side="right") - 1, 0)]
start = max(min(d.index[0] for d in frames.values()) + pd.Timedelta(days=130), F.index[0])
print("銘柄", len(frames), "開始", start.date())


def sim(d, i, p, max_hold=60):
    """厳しめの約定と値段のずれを入れた売買"""
    n = len(d)
    if i + 1 >= n or d.Low.iloc[i + 1] > p["entry"] * FILL:
        return None
    buy = min(d.Open.iloc[i + 1], p["entry"]) * (1 + SLIP)
    for k in range(i + 1, min(i + 1 + max_hold, n)):
        r = d.iloc[k]
        if r.Low <= p["stop"]:
            px = r.Open if (k > i + 1 and r.Open < p["stop"]) else p["stop"]
            return buy, px * (1 - SLIP), k, "損切り"
        if r.Close < r.sma25 and k + 1 < n:
            return buy, d.Open.iloc[k + 1] * (1 - SLIP), k + 1, "25日線割れ"
    if i + max_hold < n:
        return buy, d.Close.iloc[i + max_hold] * (1 - SLIP), i + max_hold, "期限"
    return None


# 一番ゆるい条件（10億）でシグナルを集め、各条件はそこから絞り込む
strategy.MIN_TURNOVER = 10e8
pool = []
for code, d in frames.items():
    for i in range(86, len(d)):
        if d.index[i] < start or not is_breakout(d, i):
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p:
            continue
        s = sim(d, i, p)
        if not s:
            continue
        buy, sell, k, why = s
        pool.append({"date": d.index[i], "code": code, "to": float(d.turnover20.iloc[i]),
                     "vr": float(d.Volume.iloc[i] / d.vol20.iloc[i]), "shares": p["shares"],
                     "cost": p["entry"] * p["shares"], "buy": buy, "sell": sell,
                     "entry_date": d.index[i + 1], "exit_date": d.index[k], "why": why,
                     "pnl": (sell - buy) * p["shares"]})
pool.sort(key=lambda t: (t["date"], -t["vr"]))
print("シグナル（約定したもの）", len(pool))


def run(th, vix, a, b):
    trades, open_pos = [], []
    for t in pool:
        if not (a <= t["date"] < b) or t["to"] < th or (vix and roff[at(t["date"])]):
            continue
        open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        if (len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL
                or any(o["code"] == t["code"] for o in open_pos)):
            continue
        open_pos.append(t); trades.append(t)
    n = F["n225"][(F.index >= a) & (F.index < b)]
    ret = n.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t); sells.setdefault(t["exit_date"], []).append(t)
    idle, held, eq, yr_pnl = float(CAPITAL), [], [], {}
    prev_y = None
    for dt, r in ret.items():
        if prev_y is not None and dt.year != prev_y:      # 年が変わったら前年分の税金を払う
            idle -= max(0.0, yr_pnl.get(prev_y, 0.0)) * TAX
        prev_y = dt.year
        idle *= 1 + float(r)
        for t in buys.get(dt, []):
            c = t["buy"] * t["shares"]; idle -= c + c * ETF_FEE; held.append(t)
        for t in sells.get(dt, []):
            v = t["sell"] * t["shares"]; idle += v - v * ETF_FEE
            held = [h for h in held if h is not t]
            yr_pnl[dt.year] = yr_pnl.get(dt.year, 0.0) + t["pnl"]
        val = sum(float(frames[h["code"]].Close.asof(dt)) * h["shares"] for h in held)
        eq.append(idle + val)
    eq[-1] -= max(0.0, yr_pnl.get(prev_y, 0.0)) * TAX   # 最終年の税金
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v); mdd = min(mdd, v - peak)
    bench = CAPITAL * (float(n.iloc[-1]) / float(n.iloc[0]) - 1)
    wins = [t for t in trades if t["pnl"] > 0]
    gp = sum(t["pnl"] for t in wins); gl = -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    return {"profit": round(eq[-1] - CAPITAL), "bench": round(bench),
            "vs": round(eq[-1] - CAPITAL - bench), "mdd": round(mdd), "n": len(trades),
            "hit": len(wins), "miss": len(trades) - len(wins), "pf": round(gp / gl, 2) if gl else None,
            "tax": round(sum(max(0, v) for v in yr_pnl.values()) * TAX)}


END = F.index[-1] + pd.Timedelta(days=1)
rows = []
for th in (10e8, 30e8, 50e8, 100e8, 200e8):
    for vix in (False, True):
        tr, te, al = run(th, vix, start, SPLIT), run(th, vix, SPLIT, END), run(th, vix, start, END)
        rows.append({"cfg": f"{int(th/1e8)}億・VIX{'あり' if vix else 'なし'}", "train": tr, "test": te, "all": al})
        print(rows[-1]["cfg"], "前半", tr["vs"], "後半", te["vs"], "全期間", al["vs"])

best = max(rows, key=lambda r: r["train"]["vs"])
rank_tr = sorted(rows, key=lambda r: -r["train"]["vs"])
rank_te = sorted(rows, key=lambda r: -r["test"]["vs"])
json.dump({"split": str(SPLIT.date()), "start": str(start.date()), "best_on_train": best["cfg"], "rows": rows},
          open("data/compare6.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
L = [f"前半 {start.date()}〜2023-12 / 後半 2024-01〜{F.index[-1].date()}（コスト・税金・厳しい約定込み）", "",
     f"前半で一番良かった条件：{best['cfg']}",
     f"→ 後半の成績：利益 {best['test']['profit']:+,} / 日経 {best['test']['bench']:+,} / 日経比 {best['test']['vs']:+,} / 最大落ち込み {best['test']['mdd']:,}"
     f" / 取引{best['test']['n']} 出来た{best['test']['hit']} 出来なかった{best['test']['miss']} PF{best['test']['pf']}", "",
     "## 全条件（前半の順位 → 後半の順位）"]
for r in rows:
    L.append(f"- {r['cfg']}：前半 日経比 {r['train']['vs']:+,}（{rank_tr.index(r)+1}位） → 後半 日経比 {r['test']['vs']:+,}（{rank_te.index(r)+1}位）"
             f" / 全期間 利益 {r['all']['profit']:+,} 日経比 {r['all']['vs']:+,} 税 {r['all']['tax']:,} PF {r['all']['pf']}")
open("data/compare6.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
