"""試運転：通知どおりに売買していたら、の成績を毎日自動で記録する。
検証6と同じ条件（厳しい約定・値段のずれ0.1%・ETF乗り換え0.05%・同時5銘柄・700万円）で計算し、
待機資金は日経225ETF（1321）の実際の値動きで運用したものとする。税金は見込み額を別に表示。"""
import pandas as pd
import yfinance as yf
from core import CAPITAL, MAX_POSITIONS

SLIP, ETF_FEE, TAX, FILL = 0.001, 0.0005, 0.20315, 0.998
START = "2026-10-09"   # 試運転の開始日（この日の終値判定から）

# 検証6の後半（2024-01〜2026-10、未使用期間）の成績：比較の目安
EXPECT = {"win_rate": 35.2, "pf": 1.76, "trades_per_year": round(162 / 2.77, 1),
          "excess_per_year": round(1991038 / 2.77)}


def _sim(d, i, p, max_hold=60):
    n = len(d)
    if i + 1 >= n:
        return {"status": "待ち"}
    if d.Low.iloc[i + 1] > p["entry"] * FILL:
        return {"status": "不成立"}
    buy = min(float(d.Open.iloc[i + 1]), p["entry"]) * (1 + SLIP)
    for k in range(i + 1, min(i + 1 + max_hold, n)):
        r = d.iloc[k]
        if r.Low <= p["stop"]:
            px = r.Open if (k > i + 1 and r.Open < p["stop"]) else p["stop"]
            return _done(d, i, k, buy, px * (1 - SLIP), p, "損切り")
        if r.Close < r.sma25 and k + 1 < n:
            return _done(d, i, k + 1, buy, float(d.Open.iloc[k + 1]) * (1 - SLIP), p, "25日線割れ")
    if i + max_hold < n:
        return _done(d, i, i + max_hold, buy, float(d.Close.iloc[i + max_hold]) * (1 - SLIP), p, "期限")
    return {"status": "保有中", "buy": buy, "entry_date": str(d.index[i + 1].date()),
            "last": float(d.Close.iloc[-1])}


def _done(d, i, k, buy, sell, p, why):
    return {"status": "決済", "buy": buy, "sell": sell, "why": why,
            "entry_date": str(d.index[i + 1].date()), "exit_date": str(d.index[k].date()),
            "pnl": (sell - buy) * p["shares"]}


def build(history, frames):
    cands = []
    for h in sorted(history, key=lambda x: (x["date"], -x.get("vol_ratio", 0))):
        if h["date"] < START or h["code"] not in frames:
            continue
        d = frames[h["code"]]
        idx = [k for k, x in enumerate(d.index) if str(x.date()) == h["date"]]
        if not idx:
            continue
        cands.append({**{k: h[k] for k in ("date", "code", "name", "entry", "stop", "shares")},
                      **_sim(d, idx[0], h)})
    # 同時5銘柄・700万円の枠
    taken, open_pos = [], []
    for t in cands:
        if t["status"] in ("待ち", "不成立"):
            t["taken"] = False; taken.append(t); continue
        open_pos = [o for o in open_pos if o.get("exit_date", "9999") > t["date"]]
        used = sum(o["buy"] * o["shares"] for o in open_pos)
        ok = (len(open_pos) < MAX_POSITIONS and used + t["buy"] * t["shares"] <= CAPITAL
              and not any(o["code"] == t["code"] for o in open_pos))
        t["taken"] = ok
        if ok:
            open_pos.append(t)
        taken.append(t)
    # 資産推移（待機資金は1321の実際の値動き）
    etf = yf.download("1321.T", start=START, auto_adjust=False, progress=False)["Close"].squeeze()
    n225 = yf.download("^N225", start=START, auto_adjust=False, progress=False)["Close"].squeeze()
    idle, curve = float(CAPITAL), []
    held = []
    prev = None
    for dt, px in etf.items():
        ds = str(dt.date())
        if prev is not None:
            idle *= float(px) / prev
        prev = float(px)
        for t in taken:
            if t.get("taken") and t.get("entry_date") == ds:
                c = t["buy"] * t["shares"]; idle -= c * (1 + ETF_FEE); held.append(t)
            if t.get("taken") and t.get("exit_date") == ds:
                v = t["sell"] * t["shares"]; idle += v * (1 - ETF_FEE); held = [h for h in held if h is not t]
        val = sum(float(frames[h["code"]].Close.asof(dt)) * h["shares"] for h in held)
        curve.append({"date": ds, "value": round(idle + val),
                      "nikkei": round(CAPITAL * float(n225.asof(dt)) / float(n225.iloc[0]))})
    closed = [t for t in taken if t.get("taken") and t["status"] == "決済"]
    wins = [t for t in closed if t["pnl"] > 0]
    gp = sum(t["pnl"] for t in wins); gl = -sum(t["pnl"] for t in closed if t["pnl"] <= 0)
    pnl = sum(t["pnl"] for t in closed)
    return {"start": START, "curve": curve, "trades": taken,
            "closed": len(closed), "hit": len(wins), "miss": len(closed) - len(wins),
            "pf": round(gp / gl, 2) if gl else None, "realized": round(pnl),
            "tax_est": round(max(0, pnl) * TAX), "expect": EXPECT}
