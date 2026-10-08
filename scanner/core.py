"""判定ロジック・株数計算・売買シミュレーション（検証と本番で共通）"""
import math
import pandas as pd

# ===== 運用条件（ユーザー指定） =====
CAPITAL = 7_000_000        # 運用資金の上限（円）
RISK_PCT = 0.01            # 1回の許容損失 = 資金の1%
MAX_POSITIONS = 5          # 同時保有の上限
MAX_PER_POSITION = CAPITAL / MAX_POSITIONS  # 1銘柄あたりの投入上限 = 140万円
LOT = 100                  # 100株単位
STOP_ATR = 2.0             # 損切り = 買値 − 2×ATR
TARGET_ATR = 3.0           # 利確 = 買値 + 3×ATR
MAX_HOLD = 20              # 最長保有（営業日）。超えたら終値で手仕舞い
MIN_TURNOVER = 1e9         # 20日平均売買代金 10億円以上（流動性フィルタ）


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["sma25"] = d["Close"].rolling(25).mean()
    d["sma75"] = d["Close"].rolling(75).mean()
    prev_close = d["Close"].shift(1)
    tr = pd.concat([d["High"] - d["Low"],
                    (d["High"] - prev_close).abs(),
                    (d["Low"] - prev_close).abs()], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14).mean()
    d["vol20"] = d["Volume"].rolling(20).mean()
    d["turnover20"] = (d["Close"] * d["Volume"]).rolling(20).mean()
    return d


def is_signal(d: pd.DataFrame, i: int) -> bool:
    """i日目の終値で買いシグナルが出たか。
    上昇トレンド中の押し目から、25日線を出来高を伴って回復した日。"""
    if i < 86:
        return False
    r, p = d.iloc[i], d.iloc[i - 1]
    if any(pd.isna(r[k]) for k in ("sma25", "sma75", "atr", "vol20")):
        return False
    uptrend = (r.Close > r.sma75 and r.sma25 > r.sma75
               and r.sma75 > d["sma75"].iloc[i - 10])
    reclaim = p.Close <= p.sma25 and r.Close > r.sma25
    volume = r.Volume > 1.2 * r.vol20
    liquid = r.turnover20 >= MIN_TURNOVER
    return bool(uptrend and reclaim and volume and liquid)


def plan(close: float, atr: float):
    """指値・損切り・利確・株数を計算する。株数0なら見送り。"""
    entry = round(close)
    stop = round(close - STOP_ATR * atr)
    target = round(close + TARGET_ATR * atr)
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return None
    by_risk = math.floor(CAPITAL * RISK_PCT / risk_per_share / LOT) * LOT
    by_cash = math.floor(MAX_PER_POSITION / entry / LOT) * LOT
    shares = min(by_risk, by_cash)
    if shares <= 0:
        return None
    return {"entry": entry, "stop": stop, "target": target, "shares": shares,
            "cost": entry * shares, "risk_yen": risk_per_share * shares,
            "risk_per_share": risk_per_share,
            "by_risk": by_risk, "by_cash": by_cash}


def simulate(d: pd.DataFrame, i: int, p: dict):
    """i日目シグナル → 翌日に指値で買い → 損切り/利確/期限で手仕舞い。
    同じ日に損切りと利確の両方に届いた場合は、保守的に損切りとする。
    戻り値: dict（未約定なら status='unfilled'、未決着なら status='open'）"""
    n = len(d)
    if i + 1 >= n:
        return {"status": "pending"}
    b = d.iloc[i + 1]
    if b.Low > p["entry"]:
        return {"status": "unfilled"}
    buy = min(b.Open, p["entry"])
    for k in range(i + 1, min(i + 1 + MAX_HOLD, n)):
        r = d.iloc[k]
        first_day = k == i + 1
        if r.Low <= p["stop"]:
            px = r.Open if (not first_day and r.Open < p["stop"]) else p["stop"]
            return _close(d, i, k, buy, px, p, "損切り")
        if r.High >= p["target"]:
            px = r.Open if (not first_day and r.Open > p["target"]) else p["target"]
            return _close(d, i, k, buy, px, p, "利確")
    if i + MAX_HOLD < n:
        k = i + MAX_HOLD
        return _close(d, i, k, buy, d.iloc[k].Close, p, "期限")
    return {"status": "open", "buy": float(buy)}


def _close(d, i, k, buy, sell, p, reason):
    pnl = (sell - buy) * p["shares"]
    return {"status": "closed", "buy": float(buy), "sell": float(sell),
            "reason": reason, "days": k - i,
            "exit_date": str(d.index[k].date()), "pnl": float(pnl),
            "hit": bool(pnl > 0)}
