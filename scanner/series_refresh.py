"""期限切れの日次・週次系列を、自動で取れるものだけ最新化する（data/series_live.json）。
VIX（Yahoo、確定終値のみ）・VIX25超の連続日数・米10年（Yahoo）、HY/IG OAS・NFCI・10年-2年（FRED。失敗したら米財務省の利回り曲線で10年-2年だけ補う）。
取れなかった系列は何も書かない（推測値で埋めない）。"""
import io, json, urllib.request, warnings
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
JST = timezone(timedelta(hours=9)); out = {}
def get(u, t=25):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode("utf-8", "ignore")
def settled(s):
    n = datetime.now(ZoneInfo("America/New_York"))
    return s.iloc[:-1] if len(s) and s.index[-1].date() == n.date() and n.hour + n.minute / 60 < 16.5 else s
def y(t):
    x = yf.download(t, period="3mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return settled(x)
try:
    v = y("^VIX"); d = str(v.index[-1].date()); n = 0
    for z in reversed(v.values):
        if z >= 25: n += 1
        else: break
    out["vix"] = {"value": round(float(v.iloc[-1]), 2), "observedAt": d, "change": f"前日比 {float(v.iloc[-1]-v.iloc[-2]):+.2f}（Yahoo確定終値）", "source": "https://finance.yahoo.com/quote/%5EVIX/"}
    out["vixd"] = {"value": n, "observedAt": d, "change": "VIX25以上の連続日数（確定終値から計算）", "source": "https://finance.yahoo.com/quote/%5EVIX/"}
    t = y("^TNX"); out["us10"] = {"value": round(float(t.iloc[-1]), 3), "observedAt": str(t.index[-1].date()), "change": f"前日比 {float(t.iloc[-1]-t.iloc[-2]):+.3f}（Yahoo確定終値）", "source": "https://finance.yahoo.com/quote/%5ETNX/"}
except Exception as e:
    print("Yahoo失敗", e)
def fred(i):
    for k in range(1):
        try:
            d = pd.read_csv(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", 20)))
            d.index = pd.to_datetime(d.iloc[:, 0]); s = pd.to_numeric(d.iloc[:, 1], errors="coerce").dropna()
            if len(s): return s
        except Exception as e:
            print("FRED失敗", i, k, str(e)[:80])
    return None
for sid, fid, unit in (("hy", "BAMLH0A0HYM2", "%"), ("ig", "BAMLC0A0CM", "%"), ("nfci", "NFCI", ""), ("t10y2y", "T10Y2Y", "")):
    s = fred(fid)
    if s is not None:
        out[sid] = {"value": round(float(s.iloc[-1]), 3), "observedAt": str(s.index[-1].date()),
                    "change": f"直近比 {float(s.iloc[-1]-s.iloc[-2]):+.3f}（FRED）", "source": f"https://fred.stlouisfed.org/series/{fid}"}
if "t10y2y" not in out:
    try:
        yr = datetime.now(JST).year
        d = pd.read_csv(io.StringIO(get(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{yr}/all?type=daily_treasury_yield_curve&field_tdr_date_value={yr}&page&_format=csv")))
        d["Date"] = pd.to_datetime(d["Date"]); d = d.sort_values("Date")
        r = d.iloc[-1]; out["t10y2y"] = {"value": round(float(r["10 Yr"] - r["2 Yr"]), 3), "observedAt": str(r["Date"].date()),
                                          "change": "財務省の利回り曲線（10年−2年）", "source": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"}
    except Exception as e:
        print("財務省失敗", str(e)[:80])
out["_at"] = datetime.now(JST).isoformat(timespec="minutes")
json.dump(out, open("data/series_live.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: (v["value"], v["observedAt"]) for k, v in out.items() if k != "_at"})
