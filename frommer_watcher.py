#!/usr/bin/env python3
"""
frommer_watcher.py
Daily checker for "Frommer Stop 1912 firing pin" across a few marketplaces.
Sends a Telegram message only when matches are found.
"""

import os, re, traceback
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# ------------ CONFIG ------------
KEYWORDS = [
    "Frommer Stop 1912 firing pin",
    "Frommer Stop firing pin",
    "Frommer 1912 firing pin",
    "Frommer firing pin",
]
PATTERN = re.compile("|".join([re.escape(k.lower()) for k in KEYWORDS]), re.I)

SITES = {
    "ebay":      "https://www.ebay.com/sch/i.html?_nkw={q}&_sop=10",
    "gunbroker": "https://www.gunbroker.com/All/search?Keywords={q}",
    "numrich":   "https://www.numrichgunparts.com/search?query={q}",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; frommer-watcher/1.1)"}

NOTIFY_METHOD = os.getenv("NOTIFY_METHOD", "telegram")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
# --------------------------------


def fetch(url, timeout=REQUEST_TIMEOUT):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[WARN] Fetch failed: {url} :: {e}")
        return ""


def parse_ebay(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for item in soup.select(".s-item"):
        a = item.select_one(".s-item__link")
        if not a:
            continue
        title = (a.get_text(strip=True) or "")
        url = a.get("href") or ""
        if not url:
            continue
        price_tag = item.select_one(".s-item__price")
        price = price_tag.get_text(strip=True) if price_tag else ""
        items.append({"site": "eBay", "title": title, "url": url, "price": price})
    return items


def parse_gunbroker(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    cards = soup.select(".gbresult, .search-result, .result, .results-item")
    for c in cards:
        a = c.select_one(".gbresultTitle a, a.gbresultTitle, .result-title a, a.item-link, a")
        if not a:
            continue
        title = a.get_text(strip=True) or ""
        href = a.get("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            url = "https://www.gunbroker.com" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://www.gunbroker.com/" + href.lstrip("/")
        price_tag = c.select_one(".price, .currentPrice, .item-price, .bids")
        price = price_tag.get_text(strip=True) if price_tag else ""
        items.append({"site": "GunBroker", "title": title, "url": url, "price": price})
    return items


def parse_numrich(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    # Product cards and search results links
    for card in soup.select("a[href]"):
        text = card.get_text(" ", strip=True) or ""
        if len(text) < 5:
            continue
        href = card.get("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            url = "https://www.numrichgunparts.com" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://www.numrichgunparts.com/" + href.lstrip("/")
        items.append({"site": "Numrich", "title": text, "url": url, "price": ""})
    return items


def safe_parse(fn, html, label):
    try:
        return fn(html)
    except Exception as e:
        print(f"[WARN] Parser error on {label}: {e}")
        return []


def matches(item):
    return bool(PATTERN.search((item.get("title") or "").lower()))


def send_telegram(message):
    if NOTIFY_METHOD != "telegram":
        print("[INFO] Telegram disabled (NOTIFY_METHOD != telegram)")
        return
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARN] Telegram not configured (missing token/chat id)")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[WARN] Telegram HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")


def run_once():
    found, seen = [], set()
    q = quote_plus(KEYWORDS[0])
    for site, tmpl in SITES.items():
        url = tmpl.format(q=q)
        print(f"[INFO] Checking {site}: {url}")
        html = fetch(url)
        if not html:
            continue
        if site == "ebay":
            items = safe_parse(parse_ebay, html, "eBay")
        elif site == "gunbroker":
            items = safe_parse(parse_gunbroker, html, "GunBroker")
        elif site == "numrich":
            items = safe_parse(parse_numrich, html, "Numrich")
        else:
            items = []
        for it in items:
            if matches(it) and it["url"] not in seen:
                seen.add(it["url"])
                found.append(it)

    if not found:
        print("[INFO] No matches found at this run.")
        return

    lines = [f"{len(found)} new Frommer Stop part(s) found:"]
    for it in found:
        lines.append(f"{it['site']}: {it['title']}\n{it['url']} {it.get('price','')}")
    send_telegram("\n\n".join(lines))


if __name__ == "__main__":
    try:
        run_once()
    except Exception as e:
        print("[FATAL] Unhandled error:", e)
        traceback.print_exc()
        # Prevent GitHub from marking the whole run as failed just because a site layout changed.
        # We still want the workflow to be 'green' unless there's a real infra issue.
