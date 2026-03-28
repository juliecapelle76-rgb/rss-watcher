"""
Surveille les flux RSS des médias français et envoie une notification
Telegram dès qu'un article sur la Russie est publié.
"""

import feedparser
import requests
import json
import os
import hashlib
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

FEEDS = {
    "Le Monde":        "https://www.lemonde.fr/rss/une.xml",
    "Le Figaro":       "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "Libération":      "https://www.liberation.fr/arc/outboundfeeds/rss/",
    "France Info":     "https://www.francetvinfo.fr/titres.rss",
    "France 24":       "https://www.france24.com/fr/rss",
    "RFI":             "https://www.rfi.fr/fr/rss",
}

# Mots-clés déclencheurs (insensible à la casse)
KEYWORDS = [
    "russie", "russe", "russes", "kremlin", "moscou",
    "poutine", "putin", "ukraine", "donbass", "wagner",
    "sanctions russo", "soviet",
]

SEEN_FILE = "seen_articles.json"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def article_id(entry) -> str:
    """Identifiant stable basé sur le lien ou le titre."""
    raw = getattr(entry, "link", "") or getattr(entry, "title", "")
    return hashlib.md5(raw.encode()).hexdigest()


def matches_russia(entry) -> bool:
    """Retourne True si l'article mentionne la Russie."""
    text = " ".join([
        getattr(entry, "title",   "") or "",
        getattr(entry, "summary", "") or "",
    ]).lower()
    return any(kw in text for kw in KEYWORDS)


def send_telegram(source: str, title: str, link: str, pub_date: str):
    msg = (
        f"🇷🇺 *Nouvel article sur la Russie*\n\n"
        f"📰 *{source}*\n"
        f"📌 {title}\n"
        f"🕐 {pub_date}\n"
        f"🔗 [Lire l'article]({link})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }, timeout=10)
    resp.raise_for_status()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    seen = load_seen()
    new_seen = set()
    found = 0

    for source, url in FEEDS.items():
        print(f"[{source}] Lecture du flux…")
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"  ⚠️  Erreur lecture flux : {e}")
            continue

        for entry in feed.entries:
            aid = article_id(entry)
            new_seen.add(aid)

            if aid in seen:
                continue  # déjà traité

            if not matches_russia(entry):
                continue

            title    = getattr(entry, "title",   "Sans titre")
            link     = getattr(entry, "link",    url)
            pub_date = getattr(entry, "published", datetime.now().strftime("%d/%m/%Y %H:%M"))

            print(f"  ✅ Correspondance : {title[:80]}")
            try:
                send_telegram(source, title, link, pub_date)
                found += 1
            except Exception as e:
                print(f"  ❌ Erreur Telegram : {e}")

    save_seen(seen | new_seen)
    print(f"\nTerminé — {found} notification(s) envoyée(s).")


if __name__ == "__main__":
    main()
