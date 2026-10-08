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
    req = urllib.request.Request(JPX, headers={"User-Agent": "Mozilla/5.0"})
    open(path, "wb").write(urllib.request.urlopen(req, timeout=60).read())
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


from strategy import is_breakout, simulate_trend


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


def equity(trades, n225, park, frames):
    """毎日の資産額 = 待機資金 + 保有株の終値評価額。
    park=Trueなら、待機資金は日経平均の値動きで増減する。"""
    ret = n225.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t)
        sells.setdefault(t["exit_date"], []).append(t)
    idle, held, eq = float(CAPITAL), [], []
    for dt, r in ret.items():
        ds = str(dt.date())
        if park:
            idle *= 1 + float(r)
        for t in buys.get(ds, []):
            idle -= t["buy"] * t["shares"]; held.append(t)
        for t in sells.get(ds, []):
            idle += t["sell"] * t["shares"]
            held = [h for h in held if h is not t]
        val = 0.0
        for h in held:
            c = frames[h["code"]].Close
            px = c.asof(dt) if dt >= c.index[0] else h["buy"]
            val += float(px) * h["shares"]
        eq.append(idle + val)
    return eq


def summarize(trades, n225, park, frames):
    wins = [t for t in trades if t["hit"]]
    gp = sum(t["pnl"] for t in wins)
    gl = -sum(t["pnl"] for t in trades if not t["hit"])
    eq = equity(trades, n225, park, frames)
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
_bv = CAPITAL * n225 / float(n225.iloc[0])
bench_mdd = float((_bv - _bv.cummax()).min())

try:
    prime = {}  # まずは主要93銘柄のみで検証
except Exception as e:
    print("JPX一覧の取得失敗:", e)
    prime = {}
    open("data/compare2_error.txt", "w").write(repr(e))
universes = {"主要93": STOCKS}
if prime and False:  # プライム全体は後回し（ユーザー指示）
    universes["プライム全体"] = prime

results = {}
for uname, codes in universes.items():
    frames = {c: add_indicators(df) for c, df in download(codes).items()}
    for kind in ("押し目", "高値更新"):
        trades = portfolio(candidates(frames, kind))
        for park in (False, True):
            key = f"{uname}×{kind}×{'待機資金を日経運用' if park else '待機資金は現金'}"
            results[key] = summarize(trades, n225, park, frames)
            results[key]["stocks"] = len(frames)
            print(key, results[key])

json.dump({"bench_profit": round(bench_profit), "results": results},
          open("data/compare2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lines = [f"日経平均を700万円で5年保有: {bench_profit:+,.0f}円（最大落ち込み {bench_mdd:,.0f}円）", ""]
for k, r in sorted(results.items(), key=lambda kv: -kv[1]["profit"]):
    lines.append(f"## {k}（{r['stocks']}銘柄）\n- 最終利益 {r['profit']:+,}円 / 日経比 {r['profit']-bench_profit:+,.0f}円"
                 f"\n- 取引{r['n']} 出来た{r['hit']} 出来なかった{r['miss']} 売買損益{r['trade_pnl']:+,} PF{r['pf']}"
                 f"\n- 最大落ち込み {r['mdd']:,}円\n- 年別売買損益 {r['years']}\n")
open("data/compare2.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
