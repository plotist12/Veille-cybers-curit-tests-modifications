#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Alerts RSS -> résumés quotidiens + historique (robuste)

- FORCE_ALL=1  : ignore seen.json (retraite tout) et réécrit l'historique.
- RENDER_ONLY=1: ne collecte rien ; reconstruit toutes les sorties à partir de l'historique.

Sorties:
  output/YYYY-MM-DD.md  (un fichier par jour de publication)
  output/latest.md       (alias vers le jour le plus récent)
  output/all_articles.json
  output/all_articles.md (historique complet sous forme de markdown)
"""

import os, re, sys, json, logging, hashlib, time
from datetime import datetime, timezone, date
from urllib.parse import urlparse, parse_qs, unquote
from collections import defaultdict

import feedparser
import trafilatura
from bs4 import BeautifulSoup

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# --- bootstrap NLTK data (français) ---
try:
    import nltk
    for res in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{res}")
        except LookupError:
            nltk.download(res, quiet=True)
except Exception:
    pass
# --- fin bootstrap ---

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LANGUAGE = "french"

# ---------- utils ----------
def get_env_list(name: str):
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    parts = []
    for chunk in raw.replace("\\n", "\n").splitlines():
        parts += [p.strip() for p in chunk.split(",") if p.strip()]
    return parts

def extract_original_url(url: str) -> str:
    try:
        p = urlparse(url)
        qs = parse_qs(p.query)
        for key in ("url", "q"):
            if key in qs and qs[key]:
                return unquote(qs[key][0])
        frag_qs = parse_qs(p.fragment)
        if "url" in frag_qs and frag_qs["url"]:
            return unquote(frag_qs["url"][0])
        return url
    except Exception:
        return url

def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def hash_id(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def dt_to_iso(d: datetime | date | None) -> str:
    if not d: return ""
    if isinstance(d, datetime): return d.astimezone().date().isoformat()
    return d.isoformat()

def html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""

def fetch_text(url: str, timeout: int = 20) -> str:
    downloaded = None
    try:
        downloaded = trafilatura.fetch_url(url)  # compat Windows
    except Exception:
        downloaded = None
    if not downloaded:
        try:
            import requests
            headers = {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0 Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            downloaded = r.text
        except Exception:
            return ""
    text = trafilatura.extract(
        downloaded,
        include_tables=False,
        include_formatting=False,
        include_comments=False,
        favor_recall=False,
        no_fallback=True,
        url=url,
        output_format="txt",
    )
    return text or ""

def summarize_text(text: str, sentences: int = 4) -> str:
    if not text:
        return ""
    parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    stemmer = Stemmer(LANGUAGE)
    summarizer = TextRankSummarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)
    try:
        sents = [str(s) for s in summarizer(parser.document, sentences)]
    except Exception:
        sents = [str(s) for s in parser.document.sentences[:sentences]]
    sents = [re.sub(r"\s+", " ", s).strip(" .") for s in sents if s.strip()]
    return "\n".join(f"- {s}." for s in sents) if sents else ""

# ---------- persistance ----------
def load_seen(path: str) -> set:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(path: str, seen: set):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(seen)), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_history(hist_path: str) -> list[dict]:
    if os.path.exists(hist_path):
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_history(hist_path: str, items: list[dict]):
    try:
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---------- dates RSS ----------
def parse_pub_date(entry) -> str:
    # 1) champs parsés
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            try:
                d = datetime.fromtimestamp(time.mktime(t)).date()
                return dt_to_iso(d)  # YYYY-MM-DD
            except Exception:
                pass
    # 2) brut (ISO str-like)
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if raw:
            try:
                d = datetime.fromisoformat(raw[:10])
                return dt_to_iso(d)
            except Exception:
                pass
    return ""

# ---------- rendu markdown ----------
def render_markdown(day_iso: str, articles: list[dict]) -> str:
    header = f"# Résumés – {day_iso}\n\n"
    if not articles:
        return header + "_Aucun article._\n"
    parts = [header]
    for r in articles:
        title = r.get("title", "(Sans titre)")
        link = r.get("link", "")
        source = r.get("source", "")
        pub = r.get("pub_date", "")
        meta = " | ".join([p for p in (f"Source : {source}" if source else "", f"Publication : {pub}" if pub else "") if p])
        meta_line = f"*{meta}*" if meta else ""
        parts.append(f"## [{title}]({link})  \n{meta_line}\n\n{r.get('summary','')}\n")
    return "\n".join(parts)

# ---------- programme ----------
def main():
    feeds = get_env_list("FEEDS")
    sentences = int(os.getenv("SENTENCES", "4"))
    max_per_feed = int(os.getenv("MAX_PER_FEED", "20"))
    timeout = int(os.getenv("TIMEOUT", "20"))
    out_dir = os.getenv("OUTPUT_DIR", "output")
    force_all = os.getenv("FORCE_ALL", "").strip() == "1"
    render_only = os.getenv("RENDER_ONLY", "").strip() == "1"

    os.makedirs(out_dir, exist_ok=True)
    seen_path = os.path.join(out_dir, "seen.json")
    history_path = os.path.join(out_dir, "all_articles.json")
    md_all_path = os.path.join(out_dir, "all_articles.md")
    latest_path = os.path.join(out_dir, "latest.md")

    seen = load_seen(seen_path)
    history = load_history(history_path)

    # ----- MODE RENDER_ONLY : (re)générer les fichiers depuis l'historique -----
    if render_only:
        return render_from_history(history, out_dir, md_all_path, latest_path)

    if not feeds:
        logging.error("Aucun flux RSS spécifié. Définissez FEEDS.")
        sys.exit(1)

    # ----- Collecte / enrichissement historique -----
    items = []
    for feed_url in feeds:
        logging.info(f"Lecture du flux: {feed_url}")
        fp = feedparser.parse(feed_url)
        if fp.bozo and not fp.entries:
            logging.warning(f"Flux invalide ou inaccessible: {feed_url}")
            continue
        for entry in fp.entries[:max_per_feed]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not link:
                continue
            orig = extract_original_url(link)

            # extrait un "hint" depuis le RSS
            hint_html = ""
            if entry.get("summary"):
                hint_html = entry.get("summary")
            elif entry.get("summary_detail") and isinstance(entry["summary_detail"], dict) and entry["summary_detail"].get("value"):
                hint_html = entry["summary_detail"]["value"]
            elif entry.get("content") and isinstance(entry["content"], list) and entry["content"]:
                first = entry["content"][0]
                if isinstance(first, dict) and first.get("value"):
                    hint_html = first["value"]
            hint_text = html_to_text(hint_html)
            pub_date = parse_pub_date(entry)

            uid = hash_id(orig or link)
            if not force_all and uid in seen:
                continue

            items.append({
                "uid": uid,
                "title": title or "(Sans titre)",
                "link": orig or link,
                "source": domain_of(orig or link),
                "hint": hint_text,
                "pub_date": pub_date,
            })

    logging.info(f"{len(items)} nouvel(le)s article(s) à traiter.")

    # Résumer + mise à jour de l'historique (mais PAS d'écriture du jour ici)
    for it in items:
        url = it["link"]
        title = it["title"]
        hint = it.get("hint", "")
        try:
            full = fetch_text(url, timeout=timeout)
            base_text = full or hint or title
            summary = summarize_text(base_text, sentences=sentences) if base_text else ""
            if not summary:
                summary = "- (Résumé indisponible – texte non détecté)."

            seen.add(it["uid"])
            history.append({
                "id": it["uid"],
                "title": it["title"],
                "link": it["link"],
                "source": it.get("source",""),
                "pub_date": it.get("pub_date",""),
                "summary": summary,
                "added_on": dt_to_iso(datetime.now().astimezone()),
            })
            logging.info(f"OK: {title} [{it.get('source','')}]")
        except Exception as e:
            logging.warning(f"Echec: {title} ({url}) -> {e}")

    # ----- Dédup + tri de l'historique puis rendu complet -----
    dedup = {}
    for a in history:
        if isinstance(a, dict) and a.get("id"):
            dedup[a["id"]] = a
    hist = list(dedup.values())
    # tri par (pub_date, added_on) décroissant
    hist.sort(key=lambda a: (a.get("pub_date",""), a.get("added_on","")), reverse=True)

    save_seen(seen_path, seen)
    save_history(history_path, hist)

    # (ré)générer toutes les sorties depuis l'historique
    render_from_history(hist, out_dir, md_all_path, latest_path)


def render_from_history(history: list[dict], out_dir: str, md_all_path: str, latest_path: str):
    """Reconstruit output/*.md + latest.md + all_articles.md depuis l'historique.
       -> Empêche qu'un run vide efface les sorties.
    """
    # 1) Grouper par jour de publication (repli: added_on)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for a in history:
        d = (a.get("pub_date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d or ""):
            d = (a.get("added_on") or "").strip()[:10]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d or ""):
                d = datetime.now(timezone.utc).astimezone().date().isoformat()
        by_day[d].append(a)

    if not by_day:
        # rien dans l'historique -> vider prudemment latest.md
        with open(md_all_path, "w", encoding="utf-8") as f:
            f.write("# Historique (vide)\n\n")
        open(latest_path, "w", encoding="utf-8").write("# Résumés – (vide)\n\n_Aucun article._\n")
        print("Historique vide. Sorties minimales générées.")
        return

    # 2) Écrire un fichier output/<day>.md par jour
    os.makedirs(out_dir, exist_ok=True)
    days_sorted = sorted(by_day.keys())
    for day in days_sorted:
        md_path = os.path.join(out_dir, f"{day}.md")
        md_text = render_markdown(day, by_day[day])
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    # 3) latest.md = jour le plus récent
    latest_day = max(days_sorted)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(latest_day, by_day[latest_day]))

    # 4) all_articles.md (historique complet)
    #    On réutilise le même rendu en mettant 'latest_day' comme entête.
    flat = []
    for d in sorted(by_day.keys(), reverse=True):
        flat.extend(by_day[d])
    with open(md_all_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(latest_day, flat))

    print(
        f"Jours générés: {', '.join(days_sorted)} | Dernier: {latest_day}\n"
        f"Écrit: output/<day>.md, output/latest.md, output/all_articles.md"
    )


if __name__ == "__main__":
    main()
