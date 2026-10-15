import urllib.request, json
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json",
     "Origin": "https://www.investing.com", "Referer": "https://www.investing.com/"}
out = {}
for eid in (56, 733, 227, 300, 61, 173, 256, 238, 168):
    for u in (f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/{eid}/occurrences?domain_id=1&limit=300",
              f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/{eid}/occurrences?domain_id=1"):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40).read()
            out[f"{eid}"] = {"len": len(b), "head": b[:600].decode("utf-8", "ignore")}
            open(f"data/inv_{eid}.json", "wb").write(b); break
        except Exception as e:
            out[f"{eid}"] = {"err": str(e)[:200], "u": u}
json.dump(out, open("data/probe.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1)[:5000])
