"""高値更新（ブレイクアウト）方式：採用版"""
import pandas as pd
from core import MIN_TURNOVER

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


