"""今夜〜明朝の米国の重要指標（予想・前回・CPIはクリーブランド連銀ナウキャスト）と、
検証12の『発表翌日の日経が−3%以下になった割合』を1行ずつ返す。予想の向きで売買を決めるのは検証で不採用。"""
import json, urllib.request
from datetime import datetime, timedelta, timezone
JST = timezone(timedelta(hours=9))
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
     "Accept": "application/json", "Origin": "https://www.investing.com", "Referer": "https://www.investing.com/"}
# 検証12（2000〜2026）：発表翌日の日経 −3%以下の割合（普段 2.3%）
EV = {56: ("コアCPI 前月比", 2.5), 69: ("CPI 前月比", 2.5), 227: ("雇用統計", 4.7), 300: ("失業率", 4.1),
      61: ("コアPCE 前月比", 4.7), 173: ("ISM製造業", 2.8), 256: ("小売売上高", 3.1), 238: ("PPI 前月比", 2.7),
      1: ("ADP雇用者数", 1.7), 168: ("FOMC 政策金利", 2.6)}


def nowcast():
    try:
        req = urllib.request.Request("https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json",
                                     headers={"User-Agent": H["User-Agent"]})
        J = json.loads(urllib.request.urlopen(req, timeout=90).read())
        out = {}
        for ch in J:
            for ds in ch["dataset"]:
                v = [float(p["value"]) for p in ds["data"] if p.get("value") not in ("", None)]
                if v: out[ds["seriesname"]] = v[-1]          # 最新の対象月で上書き
        return out
    except Exception:
        return {}


def upcoming(hours=40):
    now = datetime.now(JST); rows = []
    for eid, (nm, crash) in EV.items():
        u = f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/{eid}/occurrences?domain_id=1&limit=5"
        try:
            occ = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40).read())["occurrences"]
        except Exception:
            continue
        for o in occ:
            t = datetime.fromisoformat(o["occurrence_time"].replace("Z", "+00:00")).astimezone(JST)
            if now - timedelta(hours=2) <= t <= now + timedelta(hours=hours):
                rows.append((t, eid, nm, crash, o.get("forecast"), o.get("previous")))
    rows.sort()
    nc = nowcast() if any(e in (56, 69) for _, e, *_ in rows) else {}
    lines = []
    for t, eid, nm, crash, fc, pv in rows:
        s = f"{t:%m/%d %H:%M} {nm}：予想 {fc if fc is not None else '—'} / 前回 {pv}"
        if eid == 56 and "Core CPI Inflation" in nc: s += f" / ナウキャスト {nc['Core CPI Inflation']:.2f}"
        if eid == 69 and "CPI Inflation" in nc: s += f" / ナウキャスト {nc['CPI Inflation']:.2f}"
        s += f"\n  過去：翌日の日経−3%以下 {crash}%（普段2.3%）"
        lines.append(s)
    return lines


if __name__ == "__main__":
    print("\n".join(upcoming(24 * 30)))
