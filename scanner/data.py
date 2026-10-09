import json
import os
import time
import yfinance as yf
from universe import STOCKS

_U = os.path.join(os.path.dirname(__file__), "..", "data", "universe_all.json")


def universe():
    """監視対象：東証の流動性のある銘柄一覧（検証3で作成）＋主要93銘柄"""
    u = dict(STOCKS)
    if os.path.exists(_U):
        u.update(json.load(open(_U, encoding="utf-8")))
    return u


def load(period="1y", codes=None, size=100, wait=5):
    """日足を小分けに取得（レート制限対策）。失敗分は1回だけ再試行。{code: DataFrame}"""
    todo, out = list(codes or universe()), {}
    for attempt in range(2):
        failed = []
        for k in range(0, len(todo), size):
            chunk = [f"{c}.T" for c in todo[k:k + size]]
            try:
                raw = yf.download(chunk, period=period, group_by="ticker",
                                  auto_adjust=True, threads=True, progress=False)
            except Exception:
                failed += [t[:-2] for t in chunk]; time.sleep(60); continue
            for t in chunk:
                df = raw[t].dropna(subset=["Close"]) if t in raw.columns.get_level_values(0) else None
                if df is not None and len(df) > 100:
                    out[t[:-2]] = df
                elif df is None or not len(df):
                    failed.append(t[:-2])
            time.sleep(wait)
        todo = failed
        if not todo:
            break
        time.sleep(90)
    return out
