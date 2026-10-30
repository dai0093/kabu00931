"""私募信用運用会社・G-SIB・プライマリーディーラー・BDC の監視。
data/finwatch_source.txt（富士さん提供の名簿、2026-10-20）を元に、上場している主体の株価を毎回取得し、
急落（1日/5日/高値からの下落）を検知して data/finwatch.json に書く。非上場は報道監視（ダッシュボード側）に回す。
独自の売買判断はしない。警戒の閾値は下記 TH（検証前の暫定値）。"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
import yfinance as yf
import pandas as pd

JST = timezone(timedelta(hours=9))
TH = {"d1": -4.0, "d5": -8.0, "dd": -20.0}   # 暫定：1日≤-4%、5日≤-8%、60日高値から≤-20%
# (グループ, 名簿の表記, ティッカー)
L = [
 ("PC", "アレス", "ARES"), ("PC", "アポロ", "APO"), ("PC", "ブラックストーン", "BX"), ("PC", "KKR", "KKR"),
 ("PC", "ブルー・アウル", "OWL"), ("PC", "ブラックロック(HPS)", "BLK"), ("PC", "ブルックフィールド(オークツリー)", "BN"),
 ("PC", "カーライル", "CG"), ("PC", "TPG(アンジェロ・ゴードン)", "TPG"), ("PC", "T.ロウ(OHA)", "TROW"),
 ("PC", "フランクリン(BSP)", "BEN"), ("PC", "プルデンシャル(PGIM)", "PRU"), ("PC", "アリアンツ(AGI/PIMCO)", "ALV.DE"),
 ("PC", "ICG", "ICG.L"), ("PC", "CVC", "CVC.AS"), ("PC", "ティケオー", "TKO.PA"), ("PC", "ユーラゼオ", "RF.PA"),
 ("PC", "M&G", "MNG.L"), ("PC", "パートナーズ・グループ", "PGHN.SW"), ("PC", "ハミルトン・レーン", "HLNE"),
 ("PC", "ステップストーン", "STEP"), ("PC", "ケネディ・ウィルソン", "KW"), ("PC", "メトリクス", "MXT.AX"),
 ("PC", "チャレンジャー", "CGF.AX"), ("PC", "ニューバーガー系(参考)", "NMRK"),
 ("BDC", "Ares Capital", "ARCC"), ("BDC", "Blue Owl Capital Corp", "OBDC"), ("BDC", "FS KKR", "FSK"),
 ("BDC", "Blackstone Secured Lending", "BXSL"), ("BDC", "Golub BDC", "GBDC"), ("BDC", "BDC ETF", "BIZD"),
 ("米銀", "JPモルガン", "JPM"), ("米銀", "バンカメ", "BAC"), ("米銀", "シティ", "C"), ("米銀", "ゴールドマン", "GS"),
 ("米銀", "モルガン・スタンレー", "MS"), ("米銀", "ウェルズ・ファーゴ", "WFC"), ("米銀", "BNY", "BK"),
 ("米銀", "ステート・ストリート", "STT"), ("米銀", "ジェフリーズ", "JEF"),
 ("欧州銀", "HSBC", "HSBA.L"), ("欧州銀", "バークレイズ", "BARC.L"), ("欧州銀", "スタンチャート", "STAN.L"),
 ("欧州銀", "NatWest", "NWG.L"), ("欧州銀", "BNPパリバ", "BNP.PA"), ("欧州銀", "クレディ・アグリコル", "ACA.PA"),
 ("欧州銀", "ナティクシス(BPCE)", "KN.PA"), ("欧州銀", "ソシエテ・ジェネラル", "GLE.PA"),
 ("欧州銀", "ドイツ銀行", "DBK.DE"), ("欧州銀", "ING", "INGA.AS"), ("欧州銀", "UBS", "UBSG.SW"),
 ("欧州銀", "サンタンデール", "SAN.MC"),
 ("加豪銀", "RBC", "RY"), ("加豪銀", "TD", "TD"), ("加豪銀", "BMO", "BMO"), ("加豪銀", "スコシア", "BNS"),
 ("加豪銀", "マッコーリー", "MQG.AX"),
 ("日本", "三菱UFJ", "8306.T"), ("日本", "みずほ", "8411.T"), ("日本", "三井住友", "8316.T"),
 ("日本", "野村", "8604.T"), ("日本", "大和証券G", "8601.T"),
 ("日本その他", "SBI HD", "8473.T"), ("日本その他", "銀行業ETF", "1615.T"), ("日本その他", "ゆうちょ銀行", "7182.T"), ("日本その他", "りそな", "8308.T"), ("日本その他", "コンコルディア", "7186.T"),
 ("中国", "中国工商銀行", "1398.HK"), ("中国", "中国農業銀行", "1288.HK"), ("中国", "中国銀行", "3988.HK"),
 ("中国", "中国建設銀行", "0939.HK"), ("中国", "交通銀行", "3328.HK"), ("中国", "中信証券", "600030.SS"),
]
L = [x for x in L if x[2] != "NMRK"]   # 参考枠は外す
tick = [x[2] for x in L]
df = yf.download(tick, period="6mo", auto_adjust=False, progress=False, threads=True)["Close"]
from zoneinfo import ZoneInfo
CUT = {".L": ("Europe/London", 17.5), ".PA": ("Europe/Paris", 18.0), ".DE": ("Europe/Berlin", 18.0), ".AS": ("Europe/Amsterdam", 18.0),
       ".SW": ("Europe/Zurich", 18.0), ".MC": ("Europe/Madrid", 18.0), ".T": ("Asia/Tokyo", 15.75), ".HK": ("Asia/Hong_Kong", 16.75),
       ".SS": ("Asia/Shanghai", 15.5), ".AX": ("Australia/Sydney", 16.75)}
INTRA = os.environ.get("INTRADAY") == "1"   # 速報モード：未確定の途中値で判定し、data/finwatch_intraday.json にだけ書く
def settled(s, t):
    """取引時間中の未確定バーを落とす（確定終値だけで判定する）"""
    if INTRA:
        return s
    tz, cut = next((v for k, v in CUT.items() if t.endswith(k)), ("America/New_York", 16.5))
    now = datetime.now(ZoneInfo(tz))
    if len(s) and s.index[-1].date() == now.date() and now.hour + now.minute / 60 < cut:
        return s.iloc[:-1]
    return s
from datetime import timedelta
def expected_date(t):
    """その市場で、いま確定しているはずの最新の営業日（祝日は考慮しない＝祝日は誤って期限切れと出る場合あり）"""
    tz, cut = next((v for k, v in CUT.items() if t.endswith(k)), ("America/New_York", 16.5))
    now = datetime.now(ZoneInfo(tz)); d = now.date()
    if now.hour + now.minute / 60 < cut: d -= timedelta(days=1)
    while d.weekday() >= 5: d -= timedelta(days=1)
    return d
rows, bad, stale = [], [], []
for g, nm, t in L:
    try:
        s = settled(df[t].dropna(), t)
        if len(s) < 25: raise ValueError("bars")
        if not INTRA and s.index[-1].date() < expected_date(t):
            # Yahooが最新日の足を返さないことがある → 個別に取り直し、それでも古ければ「期限切れ」として記録
            try:
                h = yf.Ticker(t).history(period="1mo", auto_adjust=False)["Close"].dropna(); h.index = pd.to_datetime(h.index).tz_localize(None)
                h2 = settled(h, t)
                if len(h2) >= 25 and h2.index[-1] > s.index[-1]:
                    s = pd.concat([s[s.index < h2.index[0]], h2]) if False else h2.combine_first(s)
            except Exception:
                pass
            if s.index[-1].date() < expected_date(t): stale.append(t)
        c = float(s.iloc[-1]); d1 = (c / float(s.iloc[-2]) - 1) * 100; d5 = (c / float(s.iloc[-6]) - 1) * 100
        hi = float(s.iloc[-60:].max()); dd = (c / hi - 1) * 100
        flag = [k for k, v, th in (("1日", d1, TH["d1"]), ("5日", d5, TH["d5"]), ("高値比", dd, TH["dd"])) if v <= th]
        rows.append({"g": g, "name": nm, "t": t, "date": str(s.index[-1].date()), "close": round(c, 2),
                     "d1": round(d1, 1), "d5": round(d5, 1), "dd": round(dd, 1), "flag": flag})
    except Exception as e:
        bad.append(t)
if len(rows) < len(L) * 0.5:
    print("取得失敗が多いため書き込まない", bad); sys.exit(1)
import statistics as st
groups = {}
for g in dict.fromkeys(x[0] for x in L):
    r = [x for x in rows if x["g"] == g]
    if r:
        groups[g] = {"n": len(r), "med_dd": round(st.median(x["dd"] for x in r), 1), "med_d1": round(st.median(x["d1"] for x in r), 1),
                     "med_d5": round(st.median(x["d5"] for x in r), 1),
                     "n_flag": sum(1 for x in r if x["flag"])}
flagged = sorted([x for x in rows if x["flag"]], key=lambda x: x["dd"])
out = {"updatedAt": datetime.now(JST).isoformat(timespec="minutes"), "th": TH, "groups": groups,
       "rows": rows, "flagged": [f'{x["name"]}({x["t"]})' for x in flagged], "missing": bad,
       "note": "非上場の運用会社（Cerberus, Golub本体, Sixth Street等）は報道監視。名簿は data/finwatch_source.txt"}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fintree
try:
    _s = settled(yf.download("^SOX", period="1mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna(), "^SOX")
    sox5 = float((_s.iloc[-1] / _s.iloc[-6] - 1) * 100)
except Exception:
    sox5 = None
# 信用（社債）の代替：FREDのHY/IG OASが取れないため、社債ETF÷米国債ETFの比で毎日見る（閾値は未検証。表示のみ）
try:
    _cx = yf.download(["HYG", "LQD", "IEF"], period="1y", auto_adjust=True, progress=False)["Close"].dropna()
    _cr = {}
    for _k in ("HYG", "LQD"):
        _q = _cx[_k] / _cx["IEF"]
        _cr[_k] = {"d5": round(float((_q.iloc[-1] / _q.iloc[-6] - 1) * 100), 2), "d20": round(float((_q.iloc[-1] / _q.iloc[-21] - 1) * 100), 2),
                   "dd": round(float((_q.iloc[-1] / _q.iloc[-250:].max() - 1) * 100), 2)}
    out["credit"] = {"date": str(_cx.index[-1].date()), **_cr,
                     "rule": "HYG＝ハイイールド社債、LQD＝投資適格社債。米国債(IEF)に対する比が下がる＝社債が売られている（信用の悪化）。HY/IG OASの代わり。閾値は未検証"}
except Exception as _e:
    out["credit"] = {"error": repr(_e)[:80]}
tst, thit = fintree.state(groups)
stale_groups = [g for g in groups if sum(1 for x in rows if x["g"] == g and x["t"] in stale) >= max(1, groups[g]["n"] // 2)]
out["stale"] = stale; out["stale_groups"] = stale_groups
if tst == "ok" and any(g in ("欧州銀", "米銀", "日本") for g in stale_groups): tst = "stale"
strong, swhy = fintree.strong(groups, sox5)
out["tree"] = {"state": tst, "hits": thit, "strong": strong, "strong_why": swhy, "sox5": None if sox5 is None else round(sox5, 1)}
if INTRA:
    # 速報：ロジックツリー・確定データには触れない。変化があった時だけ【未確定】と明記して通知
    jp, eu, us = (groups.get(k, {}) for k in ("日本", "欧州銀", "米銀"))
    hot = [f"{k} 1日{v['med_d1']}%" for k, v in groups.items() if k in ("日本", "欧州銀", "米銀") and v["med_d1"] <= (-4 if k == "日本" else -3)]
    sig = "|".join([tst, str(strong)] + hot)
    SI = "data/finwatch_intraday.json"
    try: prev_sig = json.load(open(SI)).get("sent_sig", "")
    except Exception: prev_sig = ""
    sent = prev_sig
    TOPIC = os.environ.get("NTFY_TOPIC")
    if TOPIC and (tst != "ok" or strong or hot) and sig != prev_sig:
        body = "【未確定の途中値】引けで変わる可能性あり\n" + "\n".join(f"{k}: 1日{v['med_d1']}% / 5日{v['med_d5']}%" for k, v in groups.items() if k in ("日本", "欧州銀", "米銀")) + \
               f"\nSOX5日 {out['tree']['sox5']}%  状態:{tst}" + ("\n【強警戒（未確定）】" + "／".join(swhy) if strong else "") + ("\n銀行群 1日≤-4%：検証（後半）で10営業日内に日経-7%が約29%（平常の約4.7倍）。外れる確率が約7割あります。縮小の検討：日経関連・半導体を半分程度に（判断は富士さん）" if groups.get("日本", {}).get("med_d1", 0) <= -4 else "")
        q = urllib.parse.urlencode({"title": "【速報・未確定】金融機関株価", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=body.encode("utf-8"), method="POST"), timeout=30)
        sent = sig
    out["sent_sig"] = sent; out["provisional"] = True
    json.dump(out, open(SI, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("速報モード", tst, strong, hot, {k: (v["med_d1"], v["med_d5"]) for k, v in groups.items()})
    sys.exit(0)
# ---- 検証37：米大型株の時間外急落（−5%以下）→ 当日の東京の半導体は下がりやすい（6割程度・注意のみ。目標%には入れない） ----
try:
    _AH = ["GOOGL","NVDA","MSFT","AAPL","AMZN","META","INTC","AMD","AVGO","QCOM","MU","TXN","AMAT","LRCX","KLAC","ORCL","CSCO","IBM"]
    _hx = yf.download(_AH, period="5d", interval="1h", prepost=True, auto_adjust=False, progress=False)["Close"]
    _dx = yf.download(_AH, period="5d", auto_adjust=False, progress=False)["Close"]
    _ah = []
    for _t in _AH:
        try:
            _h = _hx[_t].dropna(); _ix = _h.index.tz_convert("America/New_York") if _h.index.tz is not None else _h.index.tz_localize("UTC").tz_convert("America/New_York")
            _hm = _ix.hour * 60 + _ix.minute; _reg = _h[(_hm >= 570) & (_hm < 960)]
            if not len(_reg) or _h.index[-1] <= _reg.index[-1]: continue  # 引け後のバーがなければ判定しない
            _cl = float(_reg.iloc[-1]); _last = float(_h.iloc[-1]); _r = (_last / _cl - 1) * 100  # 同じ日の通常取引の最後の値と比べる
            if _r <= -5: _ah.append(f"{_t} {_r:+.1f}%")
        except Exception: pass
    _AHF = "data/ah_sent.json"
    try: _pa = json.load(open(_AHF)).get("sig", "")
    except Exception: _pa = ""
    _sg = ",".join(sorted(x.split()[0] for x in _ah))
    if _ah and _sg != _pa and os.environ.get("NTFY_TOPIC") and "--no-notify" not in sys.argv:
        _q = urllib.parse.urlencode({"title": "【注意】米大型株が時間外で急落", "priority": "3", "click": "https://dai0093.github.io/kabu00931/signals.html"})
        _b = "、".join(_ah) + "\n検証37：当日の東京エレクトロン・アドバンテストは下落しやすい（前半・後半とも6割程度。逆に上がる日も4割）。暴落の予兆ではない（検証38）。"
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{os.environ['NTFY_TOPIC']}?{_q}", data=_b.encode("utf-8"), method="POST"), timeout=30)
    json.dump({"sig": _sg, "items": _ah, "at": datetime.now(JST).isoformat(timespec="minutes")}, open(_AHF, "w"), ensure_ascii=False)
except Exception as _e:
    print("AH check skip", repr(_e)[:80])
# ---- 防御方針C（検証28）：広い信号の本数→持ち高の目安。鳴ってから10営業日は維持。自動売買はしない ----
try:
    import statistics as _st
    _px = yf.download(["^N225", "^SOX"], period="9mo", auto_adjust=False, progress=False)["Close"]
    nk_s = settled(_px["^N225"].dropna(), "N225.T"); sx_s = settled(_px["^SOX"].dropna(), "^SOX")
    # Yahooの日経が最新日を欠く時は、日経連動ETF(1321)の騰落で補う（欠損で判定が止まるのを防ぐ）
    try:
        _n2 = yf.download("^N225", period="1mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
        _n2.index = pd.to_datetime(_n2.index).tz_localize(None); _n2 = settled(_n2, "N225.T")
        nk_s.index = pd.to_datetime(nk_s.index).tz_localize(None)
        for _d, _v in _n2.items():
            if _d not in nk_s.index: nk_s.loc[_d] = _v
        _e = yf.download("1321.T", period="1mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
        _e.index = pd.to_datetime(_e.index).tz_localize(None); _e = settled(_e, "1321.T"); nk_s = nk_s.sort_index()
        for _d in _e.index[_e.index > nk_s.index[-1]]:
            _p = _e.index[_e.index < _d][-1]
            if _p in nk_s.index: nk_s.loc[_d] = float(nk_s[_p]) * float(_e[_d] / _e[_p])
        nk_s = nk_s.sort_index()
    except Exception as _en:
        print("日経補完失敗", repr(_en)[:80])
    _ser = {tt: settled(df[tt].dropna(), tt) for _, _, tt in L if tt in df}
    _gof = {tt: g for g, _, tt in L}
    def _grp_at(d):
        acc = {}
        for tt, s in _ser.items():
            s = s[s.index <= d]
            if len(s) < 25: continue
            c = float(s.iloc[-1]); acc.setdefault(_gof[tt], []).append(((c / float(s.iloc[-2]) - 1) * 100, (c / float(s.iloc[-6]) - 1) * 100, (c / float(s.iloc[-60:].max()) - 1) * 100))
        return {g: tuple(_st.median(v[i] for v in vs) for i in range(3)) for g, vs in acc.items()}
    _hist, _today = [], {}
    for d in list(nk_s.index[-12:]):
        i = nk_s.index.get_loc(d); r1 = (nk_s.iloc[i] / nk_s.iloc[i - 1] - 1) * 100; r5 = (nk_s.iloc[i] / nk_s.iloc[i - 5] - 1) * 100
        pv = sx_s[sx_s.index < d]; sp = (pv.iloc[-1] / pv.iloc[-2] - 1) * 100
        G = _grp_at(d); jp = G.get("日本", (0, 0, 0)); eu = G.get("欧州銀", (0, 0, 0)); us_ = G.get("米銀", (0, 0, 0))
        basef = eu[0] <= -6 or eu[1] <= -15 or us_[0] <= -5 or us_[1] <= -10 or jp[0] <= -5 or jp[1] <= -10 or jp[2] <= -25
        fl = {"日経1日≤-2%": r1 <= -2, "日経1日≤-3%": r1 <= -3, "日経5日≤-5%": r5 <= -5, "SOX前夜≤-4%": sp <= -4, "銀行群1日≤-4%": jp[0] <= -4, "金融機関基準": bool(basef)}
        _hist.append({"date": str(d.date()), "score": int(sum(fl.values()))}); _today = {"flags": {k: bool(v) for k, v in fl.items()}, "nk1": round(float(r1), 2), "nk5": round(float(r5), 2), "sox_prev": round(float(sp), 2), "jp_d1": round(jp[0], 1)}
    sh = max(h["score"] for h in _hist[-10:])
    target = 0.0 if sh >= 3 else 0.25 if sh >= 2 else 0.5 if sh >= 1 else 1.0
    stale_us = [x for x in stale if not x.endswith((".T", ".SS", ".HK"))]
    _sox5 = float((sx_s.iloc[-1] / sx_s.iloc[-6] - 1) * 100)
    _reb = {"sox5": round(_sox5, 2), "on": bool(_sox5 >= 5 and _hist[-1]["score"] == 0 and sh > 0), "rule": "SOX5日≥+5%かつ当日の信号0本（検証31：前半・後半とも20日後の日経が上昇）"}
    try:
        _ohlc = yf.download("^N225", period="3y", auto_adjust=False, progress=False)
        _ohlc.columns = [c[0] if isinstance(c, tuple) else c for c in _ohlc.columns]
        _ohlc.index = pd.to_datetime(_ohlc.index).tz_localize(None)
        _wk = _ohlc.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
        _H, _L, _C = _wk.High.values, _wk.Low.values, _wk.Close.values; _pk = _peak = None
        _peak, _pki, _m = _H[0], 0, None
        for _i in range(1, len(_wk)):
            if _H[_i] >= _peak: _peak, _pki, _m = _H[_i], _i, None; continue
            if _m is None or _L[_i] < _L[_m]: _m = _i
        _dd_now = (_C[-1] / _peak - 1) * 100
        _bt = {"peak": round(float(_peak), 0), "close": round(float(_C[-1]), 0), "dd": round(float(_dd_now), 1), "line10": round(float(_peak * 0.9), 0), "active": False,
               "rule": "検証35：高値から−10%以下の局面で、週足の終値が戻り高値を上抜けると、26週後の騰落の中央値は+7〜11%（的中は基準の2倍強）。件数が少なく、動画の94%は再現できず"}
        if _m is not None and _L[_m] / _peak - 1 <= -0.10:
            _lo = max(_pki, _m - 8); _rh = float(_H[_lo:_m].max()) if _m > _lo else None
            _bt.update(active=True, valley=round(float(_L[_m]), 0), valleyDate=str(_wk.index[_m].date()), reb=None if _rh is None else round(_rh, 0),
                       above=bool(_rh is not None and _C[-1] > _rh and len(_wk) - 1 > _m), toReb=None if _rh is None else round(float((_rh / _C[-1] - 1) * 100), 1))
    except Exception as _eb:
        _bt = {"error": repr(_eb)[:80]}
    dfn = {"asOf": _hist[-1]["date"], "updatedAt": datetime.now(JST).isoformat(timespec="minutes"), "provisional": bool(INTRA), "policy": "C", "target": target,
           "score_today": _hist[-1]["score"], "hold10_max": sh, "rebound": _reb, "bottom": _bt, "history": _hist, "dbg_nk": {str(k.date()): round(float(v), 2) for k, v in nk_s.tail(8).items()}, "dbg_sox": {str(k.date()): round(float(v), 2) for k, v in sx_s.tail(6).items()}, "today": _today,
           "note": ("米欧の一部が未更新（" + str(len(stale_us)) + "銘柄）。金融機関の信号が実際より弱く出ている可能性" if stale_us else "")}
    _fn = "data/defense_intraday.json" if INTRA else "data/defense.json"
    try:
        _old = json.load(open(_fn, encoding="utf-8"))
        if _old.get("asOf", "") > dfn["asOf"]:  # Yahoo欠損で日付が後戻りした場合は前回の判定を残す
            dfn = _old; dfn["note"] = "Yahooの日経データが一時的に欠けたため、前回の判定を維持（" + dfn["asOf"] + "）"
    except Exception: pass
    json.dump(dfn, open(_fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _DS = "data/defense_sent.json"
    try: _prev = json.load(open(_DS)).get("target", None)
    except Exception: _prev = None
    _TOP = os.environ.get("NTFY_TOPIC")
    if _TOP and _prev is not None and abs(_prev - target) > 1e-9 and "--no-notify" not in sys.argv:
        _body = f"持ち高の目安 {int(_prev*100)}% → {int(target*100)}%\n直近10営業日の最大信号本数 {sh}本（本日{_hist[-1]['score']}本）" + ("\n【未確定の途中値】" if INTRA else "") + ("\n" + dfn["note"] if dfn["note"] else "") + "\n自動売買はしません。判断は富士さん。検証：急落40件の最悪損失 -44%→-8%、後半の上昇は約8割逃す"
        _q = urllib.parse.urlencode({"title": "【防御方針C】持ち高の目安が変わりました", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{_TOP}?{_q}", data=_body.encode("utf-8"), method="POST"), timeout=30)
    try: _prev_reb = json.load(open(_DS)).get("reb", False)
    except Exception: _prev_reb = False
    if _TOP and _reb["on"] and not _prev_reb and not INTRA and "--no-notify" not in sys.argv:
        _q2 = urllib.parse.urlencode({"title": "【戻りの合図】SOX5日が+5%以上", "priority": "3", "click": "https://dai0093.github.io/kabu00931/signals.html"})
        urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{_TOP}?{_q2}", data=f"SOX5日 {_reb['sox5']:+.1f}%・当日の危険信号0本。防御中のため、戻してよい合図です。\n検証31：合図の日の20日後の日経は平均+1.9%（合図なし+0.2〜0.7%）。ただし戻した後の最悪損失は−8%→−12.5%に広がります。判断は富士さん。".encode("utf-8"), method="POST"), timeout=30)
    if (not INTRA) or _prev != target: json.dump({"target": target, "at": dfn["updatedAt"], "reb": bool(_reb["on"]) if not INTRA else _prev_reb}, open(_DS, "w"))
    print("防御方針C", target, "本日", _hist[-1]["score"], "10日最大", sh, dfn["note"])
except Exception as _e:
    print("防御方針C失敗", repr(_e)); import traceback; open("data/defense_err.txt", "w").write(datetime.now(JST).isoformat() + "\n" + traceback.format_exc())

try:
    _AS = [("日本株","1306.T","TOPIX連動ETF"),("米国株","SPY","S&P500"),("米国債","IEF","米国債7-10年"),("日本国債","2510.T","国内債券ETF"),("金","GLD","金"),("REIT","1343.T","東証REIT ETF"),("先進国株","EFA","先進国株(米除く)")]
    _ao = []
    for _n, _t, _d in _AS:
        try:
            _s = yf.Ticker(_t).history(period="2y")["Close"].dropna()
            _s = _s[_s.index.map(lambda x: x.date()) <= datetime.now(JST).date()]
            _r = lambda k: round(float(_s.iloc[-1] / _s.iloc[-1 - k] - 1) * 100, 2) if len(_s) > k else None
            _dd = round(float(_s.iloc[-1] / _s.tail(60).max() - 1) * 100, 2)
            _ao.append({"name": _n, "ticker": _t, "desc": _d, "date": str(_s.index[-1].date()), "d1": _r(1), "d5": _r(5), "d21": _r(21), "dd60": _dd, "ma200": round(float(_s.iloc[-1] / _s.tail(200).mean() - 1) * 100, 2) if len(_s) >= 200 else None})
        except Exception as _e2:
            _ao.append({"name": _n, "ticker": _t, "desc": _d, "error": repr(_e2)[:80]})
    json.dump({"updatedAt": datetime.now(JST).isoformat(timespec="minutes"), "items": _ao}, open("data/assets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("資産別", [(a["name"], a.get("d21")) for a in _ao])
except Exception as _e:
    print("資産別失敗", repr(_e))
try:
    prev_tree = json.load(open("data/finwatch.json")).get("tree", {}).get("state", "ok")
    if prev_tree not in ("ok", "near", "lit"): prev_tree = "ok"
except Exception:
    prev_tree = "ok"
try:
    lt = json.load(open("data/logic_tree.json"))
    json.dump(fintree.apply(lt, tst), open("data/logic_tree.json", "w"), ensure_ascii=False, indent=1)
except Exception as e:
    print("logic_tree反映失敗", e)
json.dump(out, open("data/finwatch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"取得{len(rows)}/{len(L)}  警戒{len(flagged)}  欠損{bad}")
for g, v in groups.items(): print(g, v)
for x in flagged[:15]: print(x["name"], x["d1"], x["d5"], x["dd"], x["flag"])
# 通知：警戒銘柄の顔ぶれが前回から増えた時だけ
SENT = "data/finwatch_sent.json"
prev = json.load(open(SENT)) if os.path.exists(SENT) else {"names": []}
new = [n for n in out["flagged"] if n not in prev["names"]]
TOPIC = os.environ.get("NTFY_TOPIC")
dk = [g for g, v in groups.items() if v["n_flag"] >= max(2, v["n"] // 4)]
prev_strong = False
try:
    prev_strong = json.load(open("data/finwatch_sent.json")).get("strong", False)
except Exception:
    pass
RANK = {"ok": 0, "stale": 0, "near": 1, "lit": 2}
if TOPIC and (RANK[tst] > RANK[prev_tree] or (strong and not prev_strong)) and "--no-notify" not in sys.argv:
    q = urllib.parse.urlencode({"title": f"【ロジックツリー】金融機関株価が{'点灯' if tst=='lit' else '接近'}", "priority": "4",
                                "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=("\n".join(thit) + ("\n【強警戒】" + "／".join(swhy) + "\n縮小の検討：日経関連・半導体ETFを半分程度に（自動売買はしません。判断は富士さん）" if strong else "") + "\n根拠：検証16（10営業日内に日経-7%の発生率が平均の約" + ("3" if tst=="lit" else "2") + "倍）").encode("utf-8"), method="POST"), timeout=30)
if TOPIC and (new and (len(new) >= 2 or dk)) and "--no-notify" not in sys.argv:
    body = "新しく警戒：" + "、".join(new[:10]) + ("\n群で警戒：" + "、".join(dk) if dk else "") + \
           "\n閾値：1日≤-4% / 5日≤-8% / 60日高値比≤-20%（暫定）"
    q = urllib.parse.urlencode({"title": "【金融機関 株価警戒】", "priority": "4",
                                "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=body.encode("utf-8"), method="POST"), timeout=30)
json.dump({"names": out["flagged"], "at": out["updatedAt"], "strong": strong}, open(SENT, "w"), ensure_ascii=False)
# run 2026-10-20_16:25:10
# run 2026-10-21 06:57 JST
# run 2026-10-22 06:58 JST
# run 2026-10-22T02:36:50
# run 2026-10-22T05:32:24
# run 2026-10-22T21:30:37
# run 2026-10-24T00:58:38
# run bottom
# run 2026-10-26 06:57 JST
# fix asof
# run reb
# run 2026-10-28 06:57 JST
# run 2026-10-29 06:56 JST
# run 2026-10-30 06:57 JST
# run credit
