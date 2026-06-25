"""Diagnostic: what do COFEPRIS pages actually return?"""
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9",
}

URLS = [
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales",
    "https://www.gob.mx/cofepris/documentos/plaguicidas-y-nutrientes-vegetales-registrados",
    "https://www.gob.mx/cofepris",
]

with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
    for url in URLS:
        print(f"\n{'='*60}")
        print(f"URL: {url}")
        try:
            r = client.get(url)
            print(f"Status: {r.status_code}  Final URL: {r.url}")
            print(f"Content-Type: {r.headers.get('content-type', '?')}")
            print(f"Body size: {len(r.content)} bytes")

            soup = BeautifulSoup(r.text, "html.parser")

            # Links to Excel/CSV/PDF
            excel_links = []
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if any(e in href.lower() for e in [".xlsx", ".xls", ".csv", "plaguicida", "pesticida"]):
                    excel_links.append(href)
            print(f"Excel/CSV links ({len(excel_links)}): {excel_links[:10]}")

            # Tables
            tables = soup.select("table")
            print(f"Tables: {len(tables)}")
            for i, t in enumerate(tables[:3]):
                rows = t.select("tr")
                print(f"  Table {i}: {len(rows)} rows, first headers: {[th.get_text(strip=True)[:30] for th in rows[0].select('th,td')][:6] if rows else []}")

            # Article / document links
            doc_links = []
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if "plaguicida" in href.lower() or "plaguicida" in text.lower():
                    doc_links.append(f"{text[:40]} → {href[:80]}")
            print(f"Plaguicida links ({len(doc_links)}): {doc_links[:8]}")

            # Page title + h1
            title = soup.select_one("title")
            h1 = soup.select_one("h1")
            print(f"Title: {title.get_text(strip=True)[:80] if title else '?'}")
            print(f"H1: {h1.get_text(strip=True)[:80] if h1 else '?'}")

            # First 500 chars of body text
            body_text = soup.get_text(separator=" ", strip=True)
            print(f"Body snippet: {body_text[:300]}")

        except Exception as e:
            print(f"ERROR: {e}")
