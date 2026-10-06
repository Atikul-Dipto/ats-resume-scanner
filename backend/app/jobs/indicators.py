"""Official Bangladesh labour-market indicators from the World Bank's
World Development Indicators API (public, no key, CC BY 4.0). The figures
are ILO modeled estimates published there. Used by Work Signal next to
the signals computed from Prottoy's own listings.

`python -m app.jobs.indicators` fetches and prints them (the ingest
workflow runs this to check the live API from GitHub's runners).
"""

import asyncio
import json

import httpx

API = "https://api.worldbank.org/v2/country/BGD/indicator/{id}"
SOURCE = {
    "name": "World Bank, World Development Indicators (ILO modeled estimates)",
    "url": "https://data.worldbank.org/country/bangladesh",
    "license": "CC BY 4.0",
}
INDICATORS = [
    ("SL.UEM.TOTL.ZS", "Unemployment rate", "% of labour force"),
    ("SL.UEM.1524.ZS", "Youth unemployment (15–24)", "% of youth labour force"),
    ("SL.UEM.ADVN.ZS", "Unemployment, advanced education", "% of labour force with a degree"),
    ("SL.TLF.CACT.ZS", "Labour force participation (15+)", "% of population 15+"),
    ("SL.AGR.EMPL.ZS", "Employment in agriculture", "% of employment"),
    ("SL.IND.EMPL.ZS", "Employment in industry", "% of employment"),
    ("SL.SRV.EMPL.ZS", "Employment in services", "% of employment"),
]
YEARS = 8


def parse(indicator_id: str, label: str, unit: str, payload) -> dict | None:
    """One WDI response -> latest value, the one before it, and the series."""
    if not (isinstance(payload, list) and len(payload) == 2 and isinstance(payload[1], list)):
        return None
    points = sorted(
        (int(row["date"]), float(row["value"]))
        for row in payload[1]
        if isinstance(row, dict) and row.get("value") is not None and str(row.get("date", "")).isdigit()
    )
    if not points:
        return None
    (year, value), previous = points[-1], (points[-2] if len(points) > 1 else None)
    return {
        "id": indicator_id,
        "label": label,
        "unit": unit,
        "year": year,
        "value": round(value, 1),
        "previous": {"year": previous[0], "value": round(previous[1], 1)} if previous else None,
        "series": [{"year": y, "value": round(v, 1)} for y, v in points],
    }


async def fetch_indicators(client: httpx.AsyncClient) -> dict:
    async def one(indicator_id, label, unit):
        try:
            resp = await client.get(API.format(id=indicator_id), params={"format": "json", "mrv": YEARS}, timeout=15.0)
            resp.raise_for_status()
            return parse(indicator_id, label, unit, resp.json())
        except (httpx.HTTPError, ValueError):
            return None

    results = await asyncio.gather(*(one(*spec) for spec in INDICATORS))
    items = [r for r in results if r]
    return {"available": bool(items), "source": SOURCE, "indicators": items}


async def _main() -> None:
    agent = "ProttoyBot/1.0 (+https://github.com/Atikul-Dipto/ats-resume-scanner)"
    async with httpx.AsyncClient(headers={"User-Agent": agent}) as client:
        data = await fetch_indicators(client)
    print(json.dumps(data, indent=2))
    if not data["available"]:
        raise SystemExit("No indicators could be fetched.")


if __name__ == "__main__":
    asyncio.run(_main())
