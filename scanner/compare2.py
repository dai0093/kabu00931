"""検証2：①待機資金を日経平均で運用 ②高値更新で買う方式 ③プライム全体へ拡大
結果を data/compare2.md / compare2.json に書き出す。"""
import json
import time
import urllib.request
import pandas as pd
import yfinance as yf
from core import (add_indicators, is_signal, plan, simulate, CAPITAL,
                  MAX_POSITIONS, STOP_ATR, MIN_TURNOVER)
from universe import STOCKS

JPX = ("https://www.jpx.co.jp/markets/statistics-equities/misc/"
       "tvdivq0000001vg2-att/data_j.xls")


def prime_codes():
    path = "/tmp/data_j.xls"
    urllib.request.urlretrieve(JPX, path)
    df = pd.read_excel(path)
    df = df[df["市場・商品区分"].astype(str).str.startswith("プライム")]
    return {str(c): str(n) for c, n in zip(df["コード"], df["銘柄名"])}


def download(codes):
    out, codes = {}, list(codes)
    for k in range(0, len(codes), 150):
        chunk = [f"{c}.T" for c in codes[k:k + 150]]
        raw = yf.download(chunk, period="5y", group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        for t in chunk:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(subset=["Close"])
                if len(df) > 300:
                    out[t[:-2]] = df
        time.sleep(5)
    return out


# ===== 高値更新（ブレイクアウト）方式 =====
def is_breakout(d, i):
    if i < 86:
        return False
    r = d.iloc[i]
    if any(pd.isna(r[k]) for k in ("sma25", "sma75", "atr", "vol20")):
        return False
    hi60 = d.High.iloc[i - 60:i].max()
    return bool(r.Close > hi60 and r.sma25 > r.sma75 and r.Close > r.sma25
                and r.Volume > 1.5 * r.vol20 and r.turnover20 >= MIN_TURNOVER)


def simulate_trend(d, i, p, max_hold=60):
    """翌日指値で買い → 損切り(2ATR)に触れるか、終値が25日線を割ったら翌日寄りで売る"""
    n = len(d)
    if i + 1 >= n:
        return {"status": "pending"}
    b = d.iloc[i + 1]
    if b.Low > p["entry"]:
        return {"status": "unfilled"}
    buy = min(b.Open, p["entry"])
    for k in range(i + 1, min(i + 1 + max_hold, n)):
        r = d.iloc[k]
        if r.Low <= p["stop"]:
            px = r.Open if (k > i + 1 and r.Open < p["stop"]) else p["stop"]
            return _res(d, i, k, buy, px, p, "損切り")
        if r.Close < r.sma25 and k + 1 < n:
            return _res(d, i, k + 1, buy, d.Open.iloc[k + 1], p, "25日線割れ")
    if i + max_hold < n:
        k = i + max_hold
        return _res(d, i, k, buy, d.Close.iloc[k], p, "期限")
    return {"status": "open"}


def _res(d, i, k, buy, sell, p, reason):
    pnl = (sell - buy) * p["shares"]
    return {"status": "closed", "buy": float(buy), "sell": float(sell),
            "entry_date": str(d.index[i + 1].date()),
            "exit_date": str(d.index[k].date()), "reason": reason,
            "pnl": float(pnl), "hit": bool(pnl > 0)}


def candidates(frames, kind):
    out = []
    for code, d in frames.items():
        for i in range(len(d)):
            if kind == "押し目":
                if not is_signal(d, i):
                    continue
                p = plan(d.Close.iloc[i], d.atr.iloc[i])
                sim = simulate
            else:
                if not is_breakout(d, i):
                    continue
                p = plan(d.Close.iloc[i], d.atr.iloc[i])
                sim = simulate_trend
            if not p:
                continue
            r = sim(d, i, p)
            if r["status"] == "closed":
                out.append({"date": str(d.index[i].date()), "code": code,
                            "vr": float(d.Volume.iloc[i] / d.vol20.iloc[i]), **p, **r})
    return out


def portfolio(cands):
    cands = sorted(cands, key=lambda t: (t["date"], -t["vr"]))
    open_pos, trades = [], []
    for t in cands:
        open_pos = [o for o in open_pos if o["exit_date"] > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        if (len(open_pos) >= MAX_POSITIONS or used + t["cost"] > CAPITAL
                or any(o["code"] == t["code"] for o in open_pos)):
            continue
        open_pos.append(t)
        trades.append(t)
    return trades


def equity(trades, n225, park):
    """毎日の資産額。park=Trueなら、株に使っていない資金は日経平均で運用。"""
    ret = n225.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t["buy"] * t["shares"])
        sells.setdefault(t["exit_date"], []).append(t["sell"] * t["shares"])
    idle, held, eq = float(CAPITAL), {}, []
    pos_val = 0.0
    for dt, r in ret.items():
        ds = str(dt.date())
        if park:
            idle *= 1 + float(r)
        for c in buys.get(ds, []):
            idle -= c; pos_val += c
        for v in sells.get(ds, []):
            idle += v
        eq.append(idle)
    # 保有中の評価額は決済時に反映（最終日に未決済は無い前提）
    return eq


def summarize(trades, n225, park):
    wins = [t for t in trades if t["hit"]]
    gp = sum(t["pnl"] for t in wins)
    gl = -sum(t["pnl"] for t in trades if not t["hit"])
    eq = equity(trades, n225, park)
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v); mdd = min(mdd, v - peak)
    final = eq[-1]
    years = {}
    for t in trades:
        years[t["date"][:4]] = years.get(t["date"][:4], 0) + t["pnl"]
    return {"n": len(trades), "hit": len(wins), "miss": len(trades) - len(wins),
            "trade_pnl": round(gp - gl), "pf": round(gp / gl, 2) if gl else None,
            "final": round(final), "profit": round(final - CAPITAL),
            "mdd": round(mdd), "years": {y: round(v) for y, v in sorted(years.items())}}


n225 = yf.download("^N225", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
bench_profit = CAPITAL * (float(n225.iloc[-1]) / float(n225.iloc[0]) - 1)

try:
    prime = prime_codes()
except Exception as e:
    print("JPX一覧の取得失敗:", e)
    prime = {}
universes = {"主要93": STOCKS}
if prime:
    universes["プライム全体"] = prime

results = {}
for uname, codes in universes.items():
    frames = {c: add_indicators(df) for c, df in download(codes).items()}
    for kind in ("押し目", "高値更新"):
        trades = portfolio(candidates(frames, kind))
        for park in (False, True):
            key = f"{uname}×{kind}×{'待機資金を日経運用' if park else '待機資金は現金'}"
            results[key] = summarize(trades, n225, park)
            results[key]["stocks"] = len(frames)
            print(key, results[key])

json.dump({"bench_profit": round(bench_profit), "results": results},
          open("data/compare2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = [f"日経平均を700万円で5年保有: {bench_profit:+,.0f}円", ""]
for k, r in sorted(results.items(), key=lambda kv: -kv[1]["profit"]):
    lines.append(f"## {k}（{r['stocks']}銘柄）\n- 最終利益 {r['profit']:+,}円 / 日経比 {r['profit']-bench_profit:+,.0f}円"
                 f"\n- 取引{r['n']} 出来た{r['hit']} 出来なかった{r['miss']} 売買損益{r['trade_pnl']:+,} PF{r['pf']}"
                 f"\n- 最大落ち込み {r['mdd']:,}円\n- 年別売買損益 {r['years']}\n")
open("data/compare2.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
