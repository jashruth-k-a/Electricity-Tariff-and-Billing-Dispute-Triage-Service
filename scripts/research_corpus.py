"""Fetch primary regulatory sources for local inspection; never disables TLS checks."""
import asyncio
import json
import re
import sys
import hashlib
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import httpx
import truststore

truststore.inject_into_ssl()
directory = Path("data/research")
directory.mkdir(parents=True, exist_ok=True)
sources = {
    "regulations.html": "https://kerc.karnataka.gov.in/27/regulations/en",
    "distribution-code-2025.pdf": "https://kerc.karnataka.gov.in/uploads/media_to_upload1753187455.pdf",
    "hescom.html": "https://hescom.karnataka.gov.in/",
}
if "--supplemental" in sys.argv:
    sources = {
        "consumer-rights-2022.pdf": "https://kerc.karnataka.gov.in/uploads/media_to_upload1720004194.pdf",
        "tariff-orders.html": "https://kerc.karnataka.gov.in/96/tariff-order/en",
        "draft-regulations.html": "https://kerc.karnataka.gov.in/28/draft-regulations/en",
    }
if "--tariff-details" in sys.argv:
    sources = {
        "apr-2026.html": "https://kerc.karnataka.gov.in/147/annual-performance-review-2026/en",
        "tariff-2025.html": "https://kerc.karnataka.gov.in/143/tariff-order-2025/en",
    }
if "--tariff-updates" in sys.argv:
    sources = {
        "tariff-corrigendum-2025.pdf": "https://kerc.karnataka.gov.in/uploads/media_to_upload1748322531.pdf",
        "green-tariff-2025.pdf": "https://kerc.karnataka.gov.in/uploads/media_to_upload1753079665.pdf",
        "bescom-apr-2026.pdf": "https://kerc.karnataka.gov.in/uploads/17731776422105.pdf",
    }
if "--linked-cos" in sys.argv:
    html = Path("data/research/regulations.html").read_text(encoding="utf-8")
    table = next(t for t in re.findall(r"<table\b.*?</table>", html, flags=re.I | re.S)
                 if "kerc-SupplyCodereguln.2004.pdf" in t)
    inventory = []
    for number, row in enumerate(re.findall(r"<tr\b.*?</tr>", table, flags=re.I | re.S)):
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*ENGLISH\s*</a>', row, flags=re.I)
        if not links:
            continue
        name = f"cos-{number:02}.pdf"
        sources[name] = unescape(links[0])
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        inventory.append({"file": name, "title": re.sub(r"<[^>]+>", " ", unescape(cells[1])).strip(),
                          "date": re.sub(r"<[^>]+>", " ", unescape(cells[2])).strip(), "url": sources[name]})
    sources = {name: url for name, url in sources.items() if name.startswith("cos-")}
    Path("data/research/cos-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


async def main():
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async def one(name, url):
            try:
                response = await client.get(url)
                response.raise_for_status()
                (directory / name).write_bytes(response.content)
                result = {"file": name, "url": str(response.url), "bytes": len(response.content),
                          "sha256": hashlib.sha256(response.content).hexdigest()}
                if name.endswith(".html"):
                    links = [{"url": urljoin(str(response.url), unescape(href)),
                              "text": re.sub(r"<[^>]+>", " ", unescape(text)).strip()}
                             for href, text in re.findall(r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',
                                                          response.text, flags=re.I | re.S)]
                    result["links"] = [link for link in links if re.search(
                        r"supply|consumer|regulation|amendment|distribution|cos|tariff", link["text"], re.I)]
                return result
            except Exception as exc:
                return {"file": name, "url": url, "error": str(exc)}
        results = await asyncio.gather(*(one(name, url) for name, url in sources.items()))
        suffix = "updates" if "--tariff-updates" in sys.argv else "details" if "--tariff-details" in sys.argv else "supplemental" if "--supplemental" in sys.argv else "cos" if "--linked-cos" in sys.argv else "index"
        (directory / f"source-fetch-{suffix}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results, indent=2))


asyncio.run(main())
