"""
Aramisauto.com scraper — Playwright + Supabase

Collecte depuis chaque fiche véhicule :
  - titre, marque, modele, version, finition
  - prix, prix_origine, economie
  - annee, carburant, boite, kilometrage
  - disponibilite, mensualite
  - lien, image

Structure de la card (inner_text confirmée) :
  Line  0  → "24 heures"              disponibilite
  Line  1  → "Kia Sportage"           marque + modele
  Line  2  → "Hybride 239 ch BVA6"   version
  Line  3  → "•"                      SKIP
  Line  4  → "Active"                 finition
  Line  5  → "Hybride essence"        carburant
  Line  6  → "•"                      SKIP
  Line  7  → "Auto."                  boite
  Line  8  → "2026"                   annee
  Line  9  → "•"                      SKIP
  Line 10  → "Voiture 0 km"           kilometrage
  Line 11  → "29 999 €"               prix
  Line 12  → "Dès 114 €/mois"         mensualite
  Line 13  → "40 450 €"               prix_origine
  Line 14  → "Économisez 10 451 €..." economie

Steps :
  python scraper_aramis.py --step 1   → probe page (sélecteurs, sample)
  python scraper_aramis.py --step 2   → pagination test (5 pages)
  python scraper_aramis.py --step 3   → une page → CSV + Supabase
  python scraper_aramis.py            → full run
  python scraper_aramis.py --pages 10 → full run limité à 10 pages

Install :
  pip install playwright playwright-stealth beautifulsoup4
  playwright install chromium
"""

import argparse, csv, json, os, re, random, time
from normalize import normalize_make, normalize_model, get_generation
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from playwright_stealth import Stealth
from bs4 import BeautifulSoup


# ── CONFIG ─────────────────────────────────────────────────────────────
CONFIG = {
    "start_url":          "https://www.aramisauto.com/achat/",
    "base_url":           "https://www.aramisauto.com",
    "output_dir":         "output_aramis",
    "max_pages":          200,
    "headless":           True,
    "page_timeout":       60_000,
    "wait_after_load":    3,
    "wait_between_pages": 1,
}

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

os.makedirs(CONFIG["output_dir"], exist_ok=True)


# ── BROWSER ────────────────────────────────────────────────────────────

def make_browser(pw):
    return pw.chromium.launch(
        headless=CONFIG["headless"],
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
        ignore_default_args=["--enable-automation"],
    )


def make_page(browser) -> Page:
    ctx = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": random.randint(1280, 1920), "height": random.randint(768, 1080)},
        locale="fr-FR",
        timezone_id="Europe/Paris",
        extra_http_headers={
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    return page


def accept_cookies(page: Page):
    try:
        btn = page.locator(
            "button:has-text('Tout accepter'), button:has-text('Accepter'), "
            "button:has-text('Accept all')"
        ).first
        if btn.is_visible(timeout=4_000):
            btn.click()
            print("  🍪 Cookies acceptés")
            time.sleep(1)
    except Exception:
        pass


def is_blocked(html: str) -> bool:
    return any(s in html.lower() for s in
               ["captcha", "cf-challenge", "cf-turnstile",
                "access denied", "verifying you are human"])


# ── SAUVEGARDE ─────────────────────────────────────────────────────────

def save_json(data):
    path = os.path.join(CONFIG["output_dir"], "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON → {path} ({len(data)} annonces)")


def save_csv(data):
    if not data:
        print("⚠️  Aucune donnée à sauvegarder")
        return
    path = os.path.join(CONFIG["output_dir"], "results.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ CSV  → {path}")


# ── SUPABASE ───────────────────────────────────────────────────────────

def send_to_supabase(records: list):
    import urllib.request, urllib.error

    headers = {
        "Content-Type":  "application/json",
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer":        "resolution=ignore-duplicates",
    }

    batch_size    = 100
    sent          = 0
    errors        = 0
    total_batches = (len(records) + batch_size - 1) // batch_size

    print(f"\n📤 Envoi de {len(records):,} annonces vers Supabase...")

    for i in range(0, len(records), batch_size):
        batch     = records[i: i + batch_size]
        batch_num = i // batch_size + 1

        rows = []
        for rec in batch:
            prix_raw = (
                rec.get("prix", "")
                .replace(" €", "").replace("€", "")
                .replace("\u202f", "").replace("\xa0", "").replace(" ", "")
                .strip()
            )
            km_raw = (
                rec.get("kilometrage", "")
                .replace(" km", "").replace("km", "")
                .replace("\u202f", "").replace("\xa0", "").replace(" ", "")
                .strip()
            )
            rows.append({
                "titre":         rec.get("titre",         ""),
                "prix":          float(prix_raw) if prix_raw.replace(".", "").isdigit() else None,
                "kilometrage":   float(km_raw)   if km_raw.isdigit()                    else None,
                "date_voiture":  rec.get("date_mec", rec.get("annee", "")),
                "marque":        rec.get("marque",        ""),
                "modele":        rec.get("modele",        ""),
                "modele_unifie": rec.get("modele_unifie", ""),
                "generation": rec.get("generation", "N/A"),
                "lien_annonce":  rec.get("lien",          ""),
                "lien_image":    rec.get("image",         ""),
                "source":        rec.get("source",        ""),
            })

        payload = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        try:
            req = urllib.request.Request(SUPABASE_URL, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
            sent += len(batch)
            print(f"  Batch {batch_num}/{total_batches} → {status}  ({sent:,} envoyées)")
        except urllib.error.HTTPError as e:
            errors += 1
            body = e.read().decode("utf-8", errors="ignore")
            print(f"  ❌ Batch {batch_num} HTTP {e.code}: {body[:100]}")
        except Exception as e:
            errors += 1
            print(f"  ❌ Batch {batch_num} erreur: {e}")
        if i + batch_size < len(records):
            time.sleep(0.5)

    print(f"✅ Supabase — {sent:,} envoyées, {errors} erreurs")


# ── HELPERS ────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return " ".join(s.split()).strip()


def _parse_price(s: str) -> str:
    digits = re.sub(r"[^\d\s]", "", s).strip()
    digits = re.sub(r"\s+", " ", digits).strip()
    return f"{digits} €" if digits else "N/A"


def _is_price(s: str) -> bool:
    return bool(re.search(r"\d", s) and "€" in s and "/mois" not in s)


def _is_mensualite(s: str) -> bool:
    return "/mois" in s.lower()


def _is_km(s: str) -> bool:
    return "km" in s.lower() and "wltp" not in s.lower()


def _is_wltp(s: str) -> bool:
    return "wltp" in s.lower()


def _is_annee(s: str) -> bool:
    return bool(re.fullmatch(r"20\d{2}", s.strip()))


# ── EXTRACTION ─────────────────────────────────────────────────────────

def extract_cards(page_or_html) -> list:
    if isinstance(page_or_html, str):
        soup      = BeautifulSoup(page_or_html, "html.parser")
        cards_raw = []
        for a in soup.select("a.product-card"):
            wrapper = a.select_one(".product-card-content-wrapper")
            cards_raw.append({
                "attrs": dict(a.attrs),
                "text":  wrapper.get_text("\n") if wrapper else a.get_text("\n"),
                "img":   (a.find("img") or {}).get("src", ""),
                "href":  a.get("href", ""),
            })
    else:
        cards_raw = page_or_html.evaluate("""() =>
            [...document.querySelectorAll('a.product-card')].map(a => {
                const wrapper = a.querySelector('.product-card-content-wrapper');
                const img     = a.querySelector('img');
                const attrs   = {};
                for (const attr of a.attributes) attrs[attr.name] = attr.value;
                return {
                    attrs: attrs,
                    text:  wrapper ? wrapper.innerText : a.innerText,
                    img:   img ? img.src : '',
                    href:  a.getAttribute('href') || ''
                };
            })
        """)

    print(f"  → {len(cards_raw)} cards")
    results = []

    for i, card in enumerate(cards_raw):
        try:
            attrs = card["attrs"]
            img   = card["img"]
            href  = card["href"]

            lines = [_clean(ln) for ln in card["text"].splitlines()
                     if _clean(ln) and _clean(ln) != "•"]

            if href.startswith("http"):
                lien = href.split("?")[0]
            elif href.startswith("/"):
                lien = f"{CONFIG['base_url']}{href.split('?')[0]}"
            else:
                lien = "N/A"

            marque = attrs.get("makerid", "N/A").title()
            modele = attrs.get("modelid", "N/A").upper()

            disponibilite = lines[0] if len(lines) > 0 else "N/A"
            titre         = _clean(f"{lines[1]} {lines[2]}") if len(lines) > 2 else "N/A"
            version       = lines[2] if len(lines) > 2 else "N/A"
            finition      = lines[3] if len(lines) > 3 else "N/A"
            carburant     = lines[4] if len(lines) > 4 else "N/A"
            boite         = lines[5] if len(lines) > 5 else "N/A"

            annee       = "N/A"
            kilometrage = "N/A"
            autonomie   = "N/A"
            mensualite  = "N/A"
            economie    = "N/A"
            prix_list   = []

            for ln in lines[6:]:
                if _is_annee(ln) and annee == "N/A":
                    annee = ln
                elif _is_wltp(ln) and autonomie == "N/A":
                    autonomie = ln
                elif _is_km(ln) and kilometrage == "N/A":
                    km_digits = re.sub(r"[^\d\s]", "", ln).strip()
                    km_digits = re.sub(r"\s+", " ", km_digits).strip()
                    kilometrage = f"{km_digits} km" if km_digits else "N/A"
                elif _is_mensualite(ln):
                    mensualite = ln
                elif "conomisez" in ln.lower() or ("%" in ln and "€" in ln and re.search(r"-\d+%", ln)):
                    economie = ln
                elif _is_price(ln):
                    prix_list.append(_parse_price(ln))

            prix         = prix_list[0] if len(prix_list) >= 1 else "N/A"
            prix_origine = prix_list[1] if len(prix_list) >= 2 else "N/A"

            modele_unifie = normalize_model(marque, modele)

            results.append({
                "titre":         titre,
                "marque":        marque,
                "modele":        modele,
                "version":       version,
                "finition":      finition,
                "prix":          prix,
                "prix_origine":  prix_origine,
                "economie":      economie,
                "mensualite":    mensualite,
                "annee":         annee,
                "kilometrage":   kilometrage,
                "autonomie":     autonomie,
                "carburant":     carburant,
                "boite":         boite,
                "disponibilite": disponibilite,
                "source":        "aramisauto",
                "lien":          lien,
                "modele_unifie": modele_unifie,
                "generation":    get_generation(modele_unifie, annee),
                "image":         img,
            })
        except Exception as e:
            print(f"  ⚠️  Card {i} erreur: {e}")

    return results


def get_page_url(base_url: str, page_num: int) -> str:
    if page_num == 1:
        return base_url
    if "?" in base_url:
        return re.sub(r'([?&]page=)\d+', f'\\g<1>{page_num}',
                      base_url if "page=" in base_url else f"{base_url}&page={page_num}")
    return f"{base_url}?page={page_num}"


# ── STEPS ──────────────────────────────────────────────────────────────

def step1_probe():
    print("\n━━━ STEP 1: Probe page ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw)
        page = make_page(browser)
        try:
            page.goto(CONFIG["start_url"], timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
            time.sleep(CONFIG["wait_after_load"])
            accept_cookies(page)
            html = page.content()

            print(f"  Taille   : {len(html):,} bytes")
            print(f"  Bloqué   : {'🔴 OUI' if is_blocked(html) else '✅ NON'}")

            cards = extract_cards(page)
            print(f"  Cards extraites : {len(cards)}")
            if cards:
                print(f"  Sample :\n{json.dumps(cards[0], ensure_ascii=False, indent=2)}")

            path = os.path.join(CONFIG["output_dir"], "probe.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  HTML sauvegardé → {path}")
        except Exception as e:
            print(f"❌ Erreur: {e}")
        finally:
            browser.close()


def step2_pagination():
    print("\n━━━ STEP 2: Test pagination (5 pages) ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw)
        page = make_page(browser)
        try:
            for page_num in range(1, 6):
                url = get_page_url(CONFIG["start_url"], page_num)
                print(f"\n  Page {page_num}: {url}")
                page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
                time.sleep(CONFIG["wait_after_load"])
                if page_num == 1:
                    accept_cookies(page)

                html  = page.content()
                cards = extract_cards(page)
                print(f"  Cards: {len(cards)}  |  Bloqué: {is_blocked(html)}")

                if is_blocked(html):
                    print("  🔴 Bloqué — arrêt")
                    break
                if len(cards) == 0:
                    print("  0 cards — dernière page atteinte")
                    break
                time.sleep(CONFIG["wait_between_pages"])
            print("\n✅ Test pagination terminé")
        except Exception as e:
            print(f"❌ Erreur: {e}")
        finally:
            browser.close()


def step3_one_page():
    print("\n━━━ STEP 3: Extraction une page ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw)
        page = make_page(browser)
        try:
            page.goto(CONFIG["start_url"], timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
            time.sleep(CONFIG["wait_after_load"])
            accept_cookies(page)
            html = page.content()

            if is_blocked(html):
                print("❌ Bloqué")
                return []

            cards = extract_cards(page)
            print(f"Extraites : {len(cards)} cards")
            if cards:
                print("Sample :", json.dumps(cards[0], ensure_ascii=False, indent=2))
            if cards:
                save_json(cards)
                save_csv(cards)
                send_to_supabase(cards)
            else:
                print("✅ Aucune nouvelle annonce")
            return cards
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return []
        finally:
            browser.close()


# ── FULL RUN ───────────────────────────────────────────────────────────

def full_run(max_pages: int = None):
    limit = max_pages or CONFIG["max_pages"]
    print(f"\n━━━ FULL RUN — max {limit} pages (~{limit * 24:,} annonces max) ━━━")
    all_cards = []

    with sync_playwright() as pw:
        browser  = make_browser(pw)
        page     = make_page(browser)
        page_num = 1

        try:
            while page_num <= limit:
                url = get_page_url(CONFIG["start_url"], page_num)
                print(f"\n── Page {page_num}/{limit} ── {url}")

                try:
                    page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
                except PWTimeout:
                    print(f"  ⏳ Timeout page {page_num} — arrêt")
                    break

                time.sleep(CONFIG["wait_after_load"])
                if page_num == 1:
                    accept_cookies(page)

                html = page.content()

                if is_blocked(html):
                    print(f"  🔴 Bloqué page {page_num} — arrêt")
                    break

                cards = extract_cards(page)
                all_cards.extend(cards)
                print(f"  Cards cette page: {len(cards)}  |  Total: {len(all_cards):,}  ({page_num}/{limit} pages)")

                if len(cards) == 0:
                    print("  0 cards — dernière page atteinte")
                    break

                page_num += 1
                time.sleep(CONFIG["wait_between_pages"])

        except Exception as e:
            print(f"❌ Erreur page {page_num}: {e}")
        finally:
            browser.close()

    print(f"\n📦 Total scraped : {len(all_cards)} annonces")
    if all_cards:
        save_json(all_cards)
        save_csv(all_cards)
        send_to_supabase(all_cards)
    else:
        print("✅ Aucune nouvelle annonce à envoyer")


# ── ENTRY ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step",  type=int, choices=[1, 2, 3],
                        help="1=probe  2=pagination  3=une page")
    parser.add_argument("--pages", type=int, default=None,
                        help="Nombre max de pages (écrase CONFIG max_pages)")
    args = parser.parse_args()

    {1: step1_probe,
     2: step2_pagination,
     3: step3_one_page}.get(args.step, lambda: full_run(args.pages))()
