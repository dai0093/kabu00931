"""検証3：監視対象を東証全銘柄（売買代金10億円以上）に拡大した高値更新方式。
待機資金は日経平均で運用。結果を data/compare3.md / compare3.json に、
条件を満たす銘柄一覧を data/universe_all.json に書き出す。"""
import json
import time
import urllib.request
import pandas as pd
import yfinance as yf
from core import add_indicators, plan, CAPITAL, MAX_POSITIONS, MIN_TURNOVER
from strategy import is_breakout, simulate_trend

JPX = ("https://www.jpx.co.jp/markets/statistics-equities/misc/"
       "tvdivq0000001vg2-att/data_j.xls")


def all_codes():
    req = urllib.request.Request(JPX, headers={"User-Agent": "Mozilla/5.0"})
    open("/tmp/data_j.xls", "wb").write(urllib.request.urlopen(req, timeout=60).read())
    df = pd.read_excel("/tmp/data_j.xls")
    mk = df["市場・商品区分"].astype(str)
    df = df[mk.str.contains("内国株式")]          # ETF・REIT・外国株は除外
    return {str(c): str(n) for c, n in zip(df["コード"], df["銘柄名"])}


def download(codes):
    out, codes = {}, list(codes)
    for k in range(0, len(codes), 200):
        chunk = [f"{c}.T" for c in codes[k:k + 200]]
        try:
            raw = yf.download(chunk, period="5y", group_by="ticker",
                              auto_adjust=True, threads=True, progress=False)
        except Exception as e:
            print("chunk失敗", k, e); continue
        for t in chunk:
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(subset=["Close"])
                if len(df) > 120:
                    out[t[:-2]] = df
        time.sleep(3)
    return out


import traceback, os
os.makedirs("data", exist_ok=True)
log = open("data/compare3_log.txt", "w", encoding="utf-8")
try:
    names = all_codes()
    log.write(f"JPX一覧OK {len(names)}\n")
except Exception:
    log.write("JPX一覧の取得失敗→4桁コード総当たりに切替\n" + traceback.format_exc())
    names = {str(c): str(c) for c in range(1300, 10000)}
log.flush()
print("内国株式", len(names))
raw = download(names)
frames = {}
for c, df in raw.items():
    d = add_indicators(df)
    if d["turnover20"].max() >= MIN_TURNOVER:     # 5年間で一度でも10億円以上になった銘柄
        frames[c] = d
print("取得", len(raw), "流動性あり", len(frames))
log.write(f"取得 {len(raw)} 流動性あり {len(frames)}\n"); log.flush()

cands = []
for code, d in frames.items():
    for i in range(86, len(d)):
        if not is_breakout(d, i):
            continue
        p = plan(d.Close.iloc[i], d.atr.iloc[i])
        if not p:
            continue
        r = simulate_trend(d, i, p)
        if r["status"] == "closed":
            cands.append({"date": str(d.index[i].date()), "code": code,
                          "vr": float(d.Volume.iloc[i] / d.vol20.iloc[i]), **p, **r})

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

n225 = yf.download("^N225", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
bench = CAPITAL * (float(n225.iloc[-1]) / float(n225.iloc[0]) - 1)


def equity(park):
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
            idle += t["sell"] * t["shares"]; held = [h for h in held if h is not t]
        val = 0.0
        for h in held:
            c = frames[h["code"]].Close
            val += float(c.asof(dt)) * h["shares"] if dt >= c.index[0] else h["buy"] * h["shares"]
        eq.append(idle + val)
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v); mdd = min(mdd, v - peak)
    return eq[-1] - CAPITAL, mdd


wins = [t for t in trades if t["hit"]]
gp = sum(t["pnl"] for t in wins)
gl = -sum(t["pnl"] for t in trades if not t["hit"])
years = {}
for t in trades:
    years[t["date"][:4]] = years.get(t["date"][:4], 0) + t["pnl"]
res = {"stocks": len(frames), "signals": len(cands), "n": len(trades), "hit": len(wins),
       "miss": len(trades) - len(wins), "gp": round(gp), "gl": round(gl),
       "trade_pnl": round(gp - gl), "pf": round(gp / gl, 2) if gl else None,
       "years": {y: round(v) for y, v in sorted(years.items())}, "bench_profit": round(bench)}
for park in (True, False):
    p, m = equity(park)
    k = "park" if park else "cash"
    res[f"profit_{k}"], res[f"mdd_{k}"] = round(p), round(m)

json.dump(res, open("data/compare3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({c: names[c] for c in frames}, open("data/universe_all.json", "w", encoding="utf-8"),
          ensure_ascii=False)
lines = [f"対象 {len(frames)}銘柄（候補 {len(names)} のうち売買代金10億円以上）",
         f"日経平均を700万円で5年保有: {bench:+,.0f}円", "",
         f"全シグナル {len(cands)} → 資金制約で実行 {len(trades)}回",
         f"予測出来た {len(wins)} / 出来なかった {len(trades)-len(wins)}",
         f"総利益 {gp:,.0f} / 総損失 {gl:,.0f} / 売買損益 {gp-gl:+,.0f} / PF {res['pf']}",
         f"待機資金を日経運用: 最終利益 {res['profit_park']:+,}円（日経比 {res['profit_park']-bench:+,.0f}）最大落ち込み {res['mdd_park']:,}",
         f"待機資金は現金: 最終利益 {res['profit_cash']:+,}円 最大落ち込み {res['mdd_cash']:,}",
         f"年別売買損益 {res['years']}"]
open("data/compare3.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
