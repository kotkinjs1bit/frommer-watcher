#!/usr/bin/env python3
"""
frommer_watcher.py
Daily checker for "Frommer Stop 1912 firing pin" listings on eBay, GunBroker, Numrich, and more.
Sends you a Telegram message when a match appears.
"""

import os
import re
import requests
from bs4 import BeautifulSoup

# -------- CONFIGURATION --------
KEYWORDS = [
    "Frommer Stop 1912 firing pin",
    "Frommer Stop firing pin",
    "Frommer 1912 firing pin",
    "Frommer firing pin",
]

PATTERN = re.compile("|".join([re.escape(k.lower()) for k in KEYWORDS]), re.I)

SITES = {
    "ebay": "https://www.ebay.com/sch/i.html?_nkw={q}&_sop=10",
    "gunbroker": "https://www.gunbroker.com/All/search?Keywords={q}",
    "numrich": "https://www.numrichgunparts.com/search?query={q}"
}

NOTIFY_METHOD = os.getenv("NOTIFY_METHOD", "telegram")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; frommer-watcher/1.0)"}
# --------------------------------


def fetch(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Fetch error:", e)
        return ""


def parse_ebay(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for item in soup.select(".s-item"):
        title_tag = item.select_one(".s-item__title")
        link_tag = item.select_one(".s-item__link")
        price_tag = item.select_one("
