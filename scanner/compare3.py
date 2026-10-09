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
    """JPXの一覧ページからExcelのリンクを探して取得（URLが変わっても追従）"""
    import re
    ua = {"User-Agent": "Mozilla/5.0"}
    page = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
    html = urllib.request.urlopen(urllib.request.Request(page, headers=ua), timeout=60).read().decode("utf-8", "ignore")
    links = re.findall(r'href="([^"]+data_j\.xlsx?)"', html)
    url = "https://www.jpx.co.jp" + links[0] if links[0].startswith("/") else links[0]
    ext = url.rsplit(".", 1)[1]
    open(f"/tmp/data_j.{ext}", "wb").write(urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=60).read())
    df = pd.read_excel(f"/tmp/data_j.{ext}")
    mk = df["市場・商品区分"].astype(str)
    df = df[mk.str.contains("内国株式")]          # ETF・REIT・外国株は除外
    return {str(c): str(n) for c, n in zip(df["コード"], df["銘柄名"])}


def download(codes, period, size=100, wait=8):
    """レート制限を避けるため小分けにして間隔を空け、失敗分は1回だけ再試行"""
    out, todo = {}, list(codes)
    for attempt in range(2):
        failed = []
        for k in range(0, len(todo), size):
            chunk = [f"{c}.T" for c in todo[k:k + size]]
            try:
                raw = yf.download(chunk, period=period, group_by="ticker",
                                  auto_adjust=True, threads=False, progress=False)
            except Exception:
                failed += [t[:-2] for t in chunk]; time.sleep(60); continue
            for t in chunk:
                ok = t in raw.columns.get_level_values(0)
                df = raw[t].dropna(subset=["Close"]) if ok else None
                if df is not None and len(df):
                    out[t[:-2]] = df
                else:
                    failed.append(t[:-2])
            time.sleep(wait)
        todo = failed
        if not todo:
            break
        time.sleep(120)
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
# 1段目：直近1か月で売買代金の平均が5億円以上の銘柄に絞る
recent = download(names, "1mo", size=100, wait=15)
liquid = [c for c, df in recent.items() if (df.Close * df.Volume).mean() >= MIN_TURNOVER / 2]
log.write(f"直近1か月取得 {len(recent)} / 売買代金5億円以上 {len(liquid)}\n"); log.flush()
# 2段目：絞った銘柄だけ5年分
raw = download(liquid, "5y", size=50, wait=10)
frames = {c: add_indicators(df) for c, df in raw.items() if len(df) > 120}
print("取得", len(raw), "流動性あり", len(frames))
log.write(f"取得 {len(raw)} 流動性あり {len(frames)}\n"); log.flush()

import core, strategy
n225 = yf.download("^N225", period="5y", auto_adjust=True, progress=False)["Close"].squeeze()
bench = CAPITAL * (float(n225.iloc[-1]) / float(n225.iloc[0]) - 1)


def run(th):
    strategy.MIN_TURNOVER = th          # 判定時の売買代金基準を差し替え
    cands = []
    for code, d in frames.items():
        for i in range(86, len(d)):
            if not strategy.is_breakout(d, i):
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
        open_pos.append(t); trades.append(t)
    ret = n225.pct_change().fillna(0)
    buys, sells = {}, {}
    for t in trades:
        buys.setdefault(t["entry_date"], []).append(t); sells.setdefault(t["exit_date"], []).append(t)
    idle, held, eq = float(CAPITAL), [], []
    for dt, r in ret.items():
        ds = str(dt.date()); idle *= 1 + float(r)
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
    wins = [t for t in trades if t["hit"]]
    gp = sum(t["pnl"] for t in wins); gl = -sum(t["pnl"] for t in trades if not t["hit"])
    years = {}
    for t in trades:
        years[t["date"][:4]] = years.get(t["date"][:4], 0) + t["pnl"]
    n_st = sum(1 for d in frames.values() if d.turnover20.iloc[-1] >= th)
    return {"th_oku": th / 1e8, "stocks_now": n_st, "signals": len(cands), "n": len(trades),
            "hit": len(wins), "miss": len(trades) - len(wins), "gp": round(gp), "gl": round(gl),
            "trade_pnl": round(gp - gl), "pf": round(gp / gl, 2) if gl else None,
            "profit": round(eq[-1] - CAPITAL), "vs_nikkei": round(eq[-1] - CAPITAL - bench),
            "mdd": round(mdd), "years": {y: round(v) for y, v in sorted(years.items())}}


res = {}
for th in (10e8, 30e8, 50e8, 100e8):
    res[f"{int(th/1e8)}億"] = run(th)
    print(th, res[f"{int(th/1e8)}億"])
json.dump({"bench_profit": round(bench), "results": res},
          open("data/compare3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({c: names.get(c, c) for c in frames}, open("data/universe_all.json", "w", encoding="utf-8"),
          ensure_ascii=False)
lines = [f"日経平均を700万円で5年保有: {bench:+,.0f}円", ""]
for k, r in res.items():
    lines.append(f"## 売買代金{k}以上（現在{r['stocks_now']}銘柄）\n- 最終利益 {r['profit']:+,}円 / 日経比 {r['vs_nikkei']:+,}円 / 最大落ち込み {r['mdd']:,}円"
                 f"\n- 取引{r['n']} 出来た{r['hit']} 出来なかった{r['miss']} 総利益{r['gp']:,} 総損失{r['gl']:,} PF{r['pf']}"
                 f"\n- 年別 {r['years']}\n")
open("data/compare3.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
