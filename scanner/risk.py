"""市場リスク指標（市場リスクダッシュボードと同じ閾値）を無料データで日次に再現する。
yfinance：VIX・米10年（^TNX）・Brent（BZ=F）・ドル円（JPY=X）
FRED（無料・登録不要のCSV）：HY OAS（BAMLH0A0HYM2）・NFCI"""
import io
import urllib.request
import pandas as pd
import yfinance as yf


def _fred(sid):
    import time
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    for k in range(4):
        try:
            body = urllib.request.urlopen(req, timeout=180).read(); break
        except Exception as e:
            print("FRED再試行", sid, k, e); time.sleep(20)
    else:
        raise RuntimeError("FRED取得失敗")
    df = pd.read_csv(io.BytesIO(body))
    df.columns = ["date", sid]
    df["date"] = pd.to_datetime(df["date"])
    df[sid] = pd.to_numeric(df[sid], errors="coerce")
    return df.set_index("date")[sid].dropna()


def _yf(sym, period):
    x = yf.download(sym, period=period, auto_adjust=False, progress=False)["Close"]
    x = x.squeeze()
    x.index = pd.to_datetime(x.index).tz_localize(None)
    return x.dropna()


def factors(period="6y"):
    """日次の指標表（営業日ベース、欠損は直前値で補完）"""
    f = pd.DataFrame({"vix": _yf("^VIX", period), "us10": _yf("^TNX", period),
                      "brent": _yf("BZ=F", period), "usdjpy": _yf("JPY=X", period),
                      "n225": _yf("^N225", period),
                      "hyg": _yf("HYG", period), "ief": _yf("IEF", period)})
    for sid, k in (("BAMLH0A0HYM2", "hy"), ("NFCI", "nfci")):
        try:
            f = f.join(_fred(sid).rename(k), how="left")
        except Exception as e:
            print("FRED取得失敗", sid, e)
            f[k] = float("nan")
    f = f.sort_index().ffill()
    # ^TNXは「%×10」の表記のことがあるので補正
    if f["us10"].median() > 20:
        f["us10"] = f["us10"] / 10
    f["vix_d"] = (f["vix"] >= 25).astype(int).groupby((f["vix"] < 25).cumsum()).cumsum()
    f["hy_20"] = f["hy"] - f["hy"].shift(20)
    f["us10_20"] = f["us10"] - f["us10"].shift(20)
    f["brent_20"] = f["brent"] / f["brent"].shift(20) - 1
    f["yen_20"] = f["usdjpy"] / f["usdjpy"].shift(20) - 1
    # 信用不安の代わり：ハイイールド債ETF÷米国債ETF の20日変化（下がるほど信用不安）
    f["credit_20"] = (f["hyg"] / f["ief"]) / (f["hyg"] / f["ief"]).shift(20) - 1
    return f


def state(r):
    """ある日の各指標の点灯状態。ダッシュボードの閾値（絶対水準）と、変化幅の両方を見る。"""
    lv = lambda v, lit, near: "na" if pd.isna(v) else "lit" if v >= lit else "near" if v >= near else "ok"
    s = {"brent": lv(r.brent, 110, 105), "us10": lv(r.us10, 5.00, 4.80),
         "hy": lv(r.hy, 3.00, 2.90), "nfci": lv(r.nfci, 0, -0.20),
         "vix": "lit" if r.vix_d >= 3 else "near" if r.vix >= 25 else "ok"}
    # 変化幅（急変）：水準に関係なく直近20営業日の悪化を見る
    s["hy_jump"] = "na" if pd.isna(r.hy_20) else "lit" if r.hy_20 >= 0.50 else "near" if r.hy_20 >= 0.30 else "ok"
    s["us10_jump"] = "lit" if r.us10_20 >= 0.40 else "near" if r.us10_20 >= 0.25 else "ok"
    s["oil_jump"] = "lit" if r.brent_20 >= 0.20 else "near" if r.brent_20 >= 0.10 else "ok"
    s["yen_jump"] = "lit" if r.yen_20 <= -0.05 else "near" if r.yen_20 <= -0.03 else "ok"
    s["credit"] = "na" if pd.isna(r.credit_20) else "lit" if r.credit_20 <= -CREDIT_TH else "near" if r.credit_20 <= -CREDIT_TH * 0.6 else "ok"
    return s


CREDIT_TH = 0.0    # 0なら信用（HYG/IEF）条件を使わない。検証5の結果で決める
USE_HY = False   # HY OASはGitHubからFREDに接続できず未検証のため、判定には使わない


def risk_off(r):
    """急変型のリスクオフ：VIX25超が3日連続、またはHY OASが20日で+50bp以上（USE_HY=Falseなら VIXのみ）"""
    hy = USE_HY and not pd.isna(r.hy_20) and r.hy_20 >= 0.50
    cr = CREDIT_TH > 0 and not pd.isna(r.credit_20) and r.credit_20 <= -CREDIT_TH
    return bool(r.vix_d >= 3 or hy or cr)
