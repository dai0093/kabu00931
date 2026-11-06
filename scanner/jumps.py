"""個別株の急落検知（取引時間中・引け後）：監視93銘柄で前日比 −7% 以下を検知し、ニュースの見出しを添えて通知。
先物・指数では分からない個別の悪材料（接収・不祥事・業績急変など）を拾うため。data/jumps.json"""
import json, os, sys, urllib.parse, urllib.request, re, html
from datetime import datetime, timedelta, timezone
import pandas as pd, yfinance as yf
sys.path.insert(0, os.path.dirname(__file__))
from universe import STOCKS
JST = timezone(timedelta(hours=9)); TH = -7.0
tk = [c + ".T" for c in STOCKS]
d = yf.download(tk, period="5d", interval="1d", auto_adjust=False, progress=False)["Close"]
m = yf.download(tk, period="1d", interval="5m", auto_adjust=False, progress=False)["Close"]
hits = []
for c, nm in STOCKS.items():
    t = c + ".T"
    try:
        s = d[t].dropna(); last = float(m[t].dropna().iloc[-1]) if t in m and m[t].notna().any() else float(s.iloc[-1])
        today = datetime.now(JST).date()
        prev = float(s[s.index.date < today].iloc[-1]) if (s.index.date < today).any() else float(s.iloc[-2])
        r = (last / prev - 1) * 100
        if r <= TH: hits.append({"code": c, "name": nm, "r": round(r, 1), "price": round(last), "prev": round(prev)})
    except Exception:
        pass
def news(q):
    try:
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
        x = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        its = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", x, re.S)[:3]
        return [{"title": html.unescape(a), "url": b, "date": c} for a, b, c in its]
    except Exception as e:
        return []
for h in hits: h["news"] = news(f"{h['name']} 株価")
hits.sort(key=lambda h: h["r"])
out = {"at": datetime.now(JST).isoformat(timespec="minutes"), "th": TH, "hits": hits}
try: old = {h["code"] for h in json.load(open("data/jumps.json"))["hits"]} if json.load(open("data/jumps.json"))["at"][:10] == out["at"][:10] else set()
except Exception: old = set()
json.dump(out, open("data/jumps.json", "w"), ensure_ascii=False, indent=1)
new = [h for h in hits if h["code"] not in old]
T = os.environ.get("NTFY_TOPIC")
if T and new:
    body = "\n".join(f"{h['name']}({h['code']}) {h['r']}% {h['price']:,}円" + (f"\n  {h['news'][0]['title']}" if h["news"] else "") for h in new)
    q = urllib.parse.urlencode({"title": "【個別株の急落】前日比−7%以下", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{T}?{q}", data=body.encode("utf-8"), method="POST"), timeout=30)
print(out["at"], [(h["name"], h["r"]) for h in hits])
try:
    print("JT", float(m["2914.T"].dropna().iloc[-1]), d["2914.T"].dropna().tail(3).to_dict())
except Exception as e: print("JT取得失敗", e)
