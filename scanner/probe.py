import urllib.request, json
U = {"cleveland_page": "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting",
 "cleveland_json1": "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_quarter.json",
 "cleveland_json2": "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json",
 "ff_cpi": "https://www.forexfactory.com/calendar/78-us-cpi-mm",
 "nowflation_dates": "https://nowflation.com/cpi-release-dates",
 "nowflation_sep": "https://nowflation.com/cpi-preview/september-2026",
 "te_cpi": "https://tradingeconomics.com/united-states/core-inflation-rate-mom",
 "investing_cpi": "https://www.investing.com/economic-calendar/core-cpi-56",
 "bls_api": "https://api.bls.gov/publicAPI/v2/timeseries/data/CUSR0000SA0L1E",
 "fred_alfred": "https://alfred.stlouisfed.org/series/downloaddata?seid=CPILFESL",
 "mql5_cpi": "https://www.mql5.com/en/economic-calendar/united-states/core-consumer-price-index-mm/export",
 "fxstreet_cal": "https://calendar-api.fxstreet.com/en/api/v1/eventDates/9d4f1ba2-8ed8-4a6e-8eb0-4c8d5d0dcb6b/historical?take=200"}
out = {}
for k, u in U.items():
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "*/*"}), timeout=40)
        b = r.read(); out[k] = {"status": r.status, "len": len(b), "head": b[:400].decode("utf-8", "ignore")}
        open(f"data/probe_{k}.txt", "wb").write(b[:300000])
    except Exception as e:
        out[k] = {"err": str(e)[:200]}
json.dump(out, open("data/probe.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
