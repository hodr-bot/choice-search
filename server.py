#!/usr/bin/env python3
"""choice-search: static server + /api/search (stdlib only).

- Serves static files from cwd.
- GET /api/search?q=... queries public AliExpress search HTML, extracts
  product cards from embedded JSON, filters (FR shipping best-effort,
  bundle exclusion), returns clean JSON.
- If AliExpress blocks (403/captcha) or parsing yields nothing usable,
  returns {"fallback": true, "url": <filtered AliExpress search URL>}.
  Never invents products.
"""

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Titles matching this are "bundle" packs without a clear unit price -> excluded.
BUNDLE_RE = re.compile(
    r"bundle|\blot\b|\blots\b|x\s?\d+\s?(pcs|pi[eè]ces|pack)|"
    r"\d+\s?(pcs|pi[eè]ces)\b|pack\s?deal|set\s?of|wholesale\s?lot",
    re.IGNORECASE,
)


def search_url(query):
    q = urllib.parse.quote(query.replace(" ", "-"))
    params = urllib.parse.urlencode(
        {"SearchText": query, "shipFromCountry": "FR", "g": "y"}
    )
    return "https://www.aliexpress.com/w/wholesale-%s.html?%s" % (q, params)


def fetch_search_html(query):
    url = search_url(query)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise IOError("upstream status %s" % resp.status)
        raw = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _as_float(v):
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace("\u20ac", "").replace("EUR", "").strip()
        s = re.sub(r"[^\d.,]", "", s).replace(",", ".")
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def normalize_item(d):
    """Best-effort normalization of one raw product dict. None if unusable."""
    if not isinstance(d, dict):
        return None
    pid = _pick(d, "productId", "productid", "id", "itemId")
    title = _pick(d, "productTitle", "title", "subject", "name")
    if not pid or not title:
        return None
    title = html.unescape(str(title)).strip()
    if not title or BUNDLE_RE.search(title):
        return None
    price = _as_float(
        _pick(d, "salePrice", "price", "finalPrice", "targetSalePrice",
              "sale_price", "minPrice")
    )
    if price is None:
        return None
    img = _pick(d, "productImage", "image", "imageUrl", "picUrl", "imgUrl")
    if isinstance(img, str):
        img = img if img.startswith("http") else "https:" + img
    else:
        img = None
    rating = _as_float(_pick(d, "rating", "averageStar", "evaluateRate", "star"))
    sales_raw = _pick(d, "tradeCount", "sales", "sold", "orders", "totalSale")
    try:
        sales = int(re.sub(r"[^\d]", "", str(sales_raw))) if sales_raw else None
    except (ValueError, TypeError):
        sales = None
    blob = json.dumps(d, ensure_ascii=False).lower()
    choice = any(k in blob for k in ("choice", "choice_day", "superdeals"))
    free_ship = any(
        k in blob for k in ("free_shipping", "freeshipping", "free shipping")
    )
    link = "https://www.aliexpress.com/item/%s.html" % pid
    item = {
        "id": str(pid),
        "title": title,
        "price": round(price, 2),
        "currency": "EUR",
        "link": link,
    }
    if img:
        item["image"] = img
    if rating:
        item["rating"] = rating
    if sales is not None:
        item["sales"] = sales
    item["choice"] = bool(choice)
    item["freeShipping"] = bool(free_ship)
    return item


def extract_products(page_html):
    """Find product-like dicts in embedded JSON blobs of the search page."""
    found = []
    # Candidate JSON objects containing both a product id and a title key.
    for m in re.finditer(r"\{[^{}]*?(?:productId|product[idI]|itemId)[^{}]*?\}", page_html):
        try:
            d = json.loads(m.group(0))
        except ValueError:
            continue
        item = normalize_item(d)
        if item:
            found.append(item)
    # Dedupe by id, keep order.
    seen, out = set(), []
    for it in found:
        if it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
        if len(out) >= 30:
            break
    return out


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/search":
            self.handle_search(parsed)
        else:
            super().do_GET()

    def handle_search(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        q = (qs.get("q", [""])[0] or "").strip()
        if not q:
            return self.send_json(400, {"error": "missing q parameter"})
        url = search_url(q)
        try:
            page_html = fetch_search_html(q)
        except Exception:
            return self.send_json(200, {"fallback": True, "url": url})
        # Blocked (captcha/login wall) -> honest fallback.
        low = page_html[:5000].lower()
        if "captcha" in low or "slide to verify" in low or "login" in low and "productid" not in low:
            return self.send_json(200, {"fallback": True, "url": url})
        try:
            products = extract_products(page_html)
        except Exception:
            products = []
        if not products:
            return self.send_json(200, {"fallback": True, "url": url})
        return self.send_json(200, {"fallback": False, "url": url,
                                    "query": q, "results": products})

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("choice-search on http://127.0.0.1:%d" % args.port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
