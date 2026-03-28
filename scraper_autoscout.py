"""
AutoScout24.fr scraper — Playwright + SmartProxy

Collects from each listing card:
  - title, make, model, version
  - price
  - year, mileage, fuel, gearbox, power
  - seller type, location
  - listing URL

Steps (run independently to debug):
  python scraper_autoscout.py --step 1  → proxy check
  python scraper_autoscout.py --step 2  → probe page: find selectors, dump HTML
  python scraper_autoscout.py --step 3  → extract one page, save CSV
  python scraper_autoscout.py --step 4  → pagination test
  python scraper_autoscout.py           → full run, all pages

Install:
  pip install playwright playwright-stealth beautifulsoup4
  playwright install chromium
"""

import argparse, csv, json, os, re, random, time
from datetime import datetime
from normalize import normalize_make, normalize_model, get_generation
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
from playwright_stealth import Stealth
from bs4 import BeautifulSoup


# ── CONFIG ─────────────────────────────────────────────────────────────
CONFIG = {
    "start_url": (
        "https://www.autoscout24.fr/lst"
        "?sort=age&desc=1&ustate=N%2CU&size=40&page=1&cy=F&atype=C"
    ),
    "proxy_host":         "proxy.smartproxy.net",
    "proxy_port":         3120,
    "proxy_username":     "smart-uxw575g61n3q_area-FR_life-30_session-PR9E309SR",
    "proxy_password":     "bpKGpmIg89DtkfQO",
    "output_dir":         "output_autoscout",
    "max_pages":          60,
    "headless":           True,
    "page_timeout":       60_000,
    "wait_after_load":    2,
    "wait_between_pages": 1,
    "webhook_url":        "https://hook.eu1.make.com/j7opk3mbec3vmucyygqh2ob2jxx7r0po",
    "webhook_batch_size": 100,
}

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces?on_conflict=marque,modele,prix,kilometrage,lien_image"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


# ── SETUP ──────────────────────────────────────────────────────────────
os.makedirs(CONFIG["output_dir"], exist_ok=True)


def proxy_cfg():
    return {
        "server":   f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}",
        "username": CONFIG["proxy_username"],
        "password": CONFIG["proxy_password"],
    }


def make_browser(pw, use_proxy=True):
    return pw.chromium.launch(
        headless=CONFIG["headless"],
        proxy=proxy_cfg() if use_proxy else None,
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
            "button:has-text('Accept'), #didomi-notice-agree-button, "
            "[data-testid='as24-cmp-accept-all-button']"
        ).first
        if btn.is_visible(timeout=4_000):
            btn.click()
            print("  🍪 Cookies accepted")
            time.sleep(1)
    except Exception:
        pass


def is_blocked(html: str) -> bool:
    return any(s in html.lower() for s in
               ["captcha-delivery.com", "cf-challenge", "cf-turnstile",
                "geo.captcha", "access denied", "verifying you are human"])


def save_json(data):
    path = os.path.join(CONFIG["output_dir"], "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON → {path} ({len(data)} records)")


def save_csv(data):
    if not data:
        print("⚠️  No data to save")
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
        "Prefer": "resolution=merge-duplicates",
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
                "last_seen_at":  datetime.utcnow().isoformat(),  
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


def _extract_from_jsonld(soup) -> list:
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                items = data
            elif data.get("@type") == "ItemList":
                items = [el.get("item", el) for el in data.get("itemListElement", [])]
            elif data.get("@type") in ("Car", "Vehicle", "Product"):
                items = [data]
            else:
                continue
            for item in items:
                if not item:
                    continue
                offers    = item.get("offers", {})
                price     = offers.get("price", "") or offers.get("lowPrice", "")
                currency  = offers.get("priceCurrency", "EUR")
                odometer  = item.get("mileageFromOdometer", {})
                km        = odometer.get("value", "N/A") if isinstance(odometer, dict) else odometer
                brand     = item.get("brand", {})
                marque    = brand.get("name", "N/A") if isinstance(brand, dict) else str(brand)
                engine    = item.get("vehicleEngine", {})
                puissance = str(engine.get("enginePower", "N/A")) if isinstance(engine, dict) else "N/A"
                image     = item.get("image", "N/A")
                if isinstance(image, list):
                    image = image[0] if image else "N/A"
                results.append({
                    "lien":        item.get("url", "N/A"),
                    "titre":       item.get("name", "N/A"),
                    "marque":      marque,
                    "prix":        f"{price} {currency}".strip() if price else "N/A",
                    "annee":       str(item.get("vehicleModelDate", item.get("modelDate", "N/A"))),
                    "kilometrage": str(km),
                    "carburant":   item.get("fuelType", "N/A"),
                    "boite":       item.get("vehicleTransmission", "N/A"),
                    "puissance":   puissance,
                    "couleur":     item.get("color", "N/A"),
                    "image":       image,
                })
        except Exception:
            pass
    return results


# ── EXTRACTION ─────────────────────────────────────────────────────────

def extract_cards(page_or_html, html: str = None) -> list:
    FUEL_MAP = {
        "b": "Essence", "d": "Diesel", "e": "Électrique",
        "h": "Hybride", "l": "GPL",    "g": "GNV", "m": "Mild-Hybrid",
    }

    if isinstance(page_or_html, str):
        html      = page_or_html
        soup      = BeautifulSoup(html, "html.parser")
        articles  = soup.find_all("article")
        cards_raw = []
        for art in articles:
            a = next((t for t in art.find_all("a", href=True)
                      if "/offres/" in t["href"]), None)
            cards_raw.append({
                "attrs": dict(art.attrs),
                "text":  art.get_text("\n"),
                "img":   (art.find("img") or {}).get("src", ""),
                "href":  a["href"] if a else "",
            })
    else:
        try:
            page_or_html.wait_for_selector('a[href*="/offres/"]', timeout=5000)
        except Exception:
            pass

        cards_raw = page_or_html.evaluate("""() => {
            const guidToUrl = {};
            for (const a of document.querySelectorAll('a[href]')) {
                const href = a.getAttribute('href') || '';
                if (!href.includes('/offres/')) continue;
                const path  = href.split('?')[0];
                const parts = path.split('-');
                const guid  = parts.slice(-5).join('-');
                if (guid && !guidToUrl[guid]) guidToUrl[guid] = path;
            }
            return [...document.querySelectorAll('article')].map(a => {
                const attrs = {};
                for (const attr of a.attributes) attrs[attr.name] = attr.value;
                const guid = a.getAttribute('data-guid') || a.id || '';
                const img  = a.querySelector('img');
                return {
                    attrs: attrs,
                    text:  a.innerText,
                    img:   img ? img.src : '',
                    href:  guidToUrl[guid] || ''
                };
            });
        }""")

    print(f"  → {len(cards_raw)} articles")
    results = []

    for i, card in enumerate(cards_raw):
        try:
            attrs = card["attrs"]
            text  = card["text"]
            img   = card["img"]

            lines = [_clean(ln) for ln in text.splitlines() if _clean(ln)]
            def get(idx):
                return lines[idx] if idx < len(lines) else "N/A"

            guid = attrs.get("data-guid", attrs.get("id", ""))
            href = card.get("href", "")
            if href.startswith("http"):
                lien = href.split("?")[0]
            elif href.startswith("/offres/"):
                lien = f"https://www.autoscout24.fr{href.split('?')[0]}"
            elif guid:
                make_slug  = attrs.get("data-make",  "").lower().replace(" ", "-")
                model_slug = attrs.get("data-model", "").lower().replace(" ", "-")
                fuel_slug  = FUEL_MAP.get(attrs.get("data-fuel-type", ""), "").lower()
                slug = "-".join(filter(None, [make_slug, model_slug, fuel_slug]))
                lien = f"https://www.autoscout24.fr/offres/{slug}-{guid}"
            else:
                lien = "N/A"

            prix_raw    = attrs.get("data-price", "")
            prix        = f"{prix_raw} €" if prix_raw else "N/A"

            km_raw      = attrs.get("data-mileage", "")
            kilometrage = f"{km_raw} km" if km_raw else "N/A"

            marque = attrs.get("data-make", get(0).split()[0] if get(0) != "N/A" else "N/A").title()
            modele = attrs.get("data-model", " ".join(get(0).split()[1:]) if get(0) != "N/A" else "N/A").upper()

            reg = attrs.get("data-first-registration", "")
            if reg and "-" in reg:
                mm, yyyy = reg.split("-", 1)
                date_mec = f"{mm}/{yyyy}"
                annee    = yyyy
            else:
                date_mec = "N/A"
                annee    = "N/A"

            fuel_code = attrs.get("data-fuel-type", "")
            carburant = FUEL_MAP.get(fuel_code, fuel_code.capitalize() if fuel_code else "N/A")

            titre        = _clean(f"{get(0)} {get(1)}")
            version      = get(1)
            puissance    = get(9)
            vendeur      = get(10)
            localisation = get(11)

            modele_unifie = normalize_model(marque, modele)

            results.append({
                "titre":         titre,
                "marque":        marque,
                "modele":        modele,
                "version":       version,
                "prix":          prix,
                "annee":         annee,
                "date_mec":      date_mec,
                "kilometrage":   kilometrage,
                "carburant":     carburant,
                "puissance":     puissance,
                "vendeur":       vendeur,
                "localisation":  localisation,
                "source":        "autoscout24",
                "lien":          lien,
                "modele_unifie": modele_unifie,
                "generation":    get_generation(modele_unifie, annee),
                "image":         img,
            })
        except Exception as e:
            print(f"  ⚠️  Article {i} error: {e}")

    return results


def get_next_page_url(current_url: str, page_num: int) -> str:
    if "page=" in current_url:
        return re.sub(r'(page=)\d+', f'\\g<1>{page_num}', current_url)
    sep = "&" if "?" in current_url else "?"
    return f"{current_url}{sep}page={page_num}"


# ── STEPS ──────────────────────────────────────────────────────────────

def step1_check_proxy():
    print("\n━━━ STEP 1: Proxy check ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw, use_proxy=True)
        page = make_page(browser)
        try:
            page.goto("https://api.ipify.org?format=json", timeout=20_000)
            ip = json.loads(page.text_content("body"))["ip"]
            print(f"✅ Proxy OK — outbound IP: {ip}")
        except Exception as e:
            print(f"❌ Proxy failed: {e}")
        finally:
            browser.close()


def step2_probe():
    print("\n━━━ STEP 2: Probe page ━━━")
    for use_proxy in [False, True]:
        label = "with proxy" if use_proxy else "no proxy"
        print(f"\n  [{label}]")
        with sync_playwright() as pw:
            browser = make_browser(pw, use_proxy=use_proxy)
            page = make_page(browser)
            try:
                page.goto(CONFIG["start_url"], timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
                time.sleep(CONFIG["wait_after_load"])
                accept_cookies(page)
                html = page.content()

                print(f"  Size    : {len(html):,} bytes")
                print(f"  Blocked : {'🔴 YES' if is_blocked(html) else '✅ NO'}")

                articles = len(BeautifulSoup(html, "html.parser").find_all("article"))
                print(f"  <article> tags: {articles}")

                cards = extract_cards(page)
                print(f"  Cards extracted: {len(cards)}")
                if cards:
                    print(f"  Sample: {json.dumps(cards[0], ensure_ascii=False, indent=2)}")

                path = os.path.join(CONFIG["output_dir"], f"probe_{'proxy' if use_proxy else 'direct'}.html")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  HTML saved → {path}")

                if cards:
                    print(f"\n  ✅ [{label}] works — use this mode")
                    break

            except Exception as e:
                print(f"  ❌ Error: {e}")
            finally:
                browser.close()


def step3_one_page():
    print("\n━━━ STEP 3: Extract one page ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw, use_proxy=False)
        page = make_page(browser)
        try:
            page.goto(CONFIG["start_url"], timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
            time.sleep(CONFIG["wait_after_load"])
            accept_cookies(page)
            html = page.content()

            if is_blocked(html):
                print("❌ Blocked")
                return []

            cards = extract_cards(page)
            print(f"Extracted {len(cards)} cards")
            if cards:
                print("Sample:", json.dumps(cards[0], ensure_ascii=False, indent=2))
            if cards:
                save_json(cards)
                save_csv(cards)
                send_to_supabase(cards)
            else:
                print("✅ Aucune annonce extraite")
            return cards
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
        finally:
            browser.close()


def step4_pagination():
    print("\n━━━ STEP 4: Pagination test (first 5 pages) ━━━")
    with sync_playwright() as pw:
        browser = make_browser(pw, use_proxy=False)
        page = make_page(browser)
        try:
            for page_num in range(1, 6):
                url = get_next_page_url(CONFIG["start_url"], page_num)
                print(f"\n  Page {page_num}: {url}")
                page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
                time.sleep(CONFIG["wait_after_load"])
                if page_num == 1:
                    accept_cookies(page)

                html  = page.content()
                cards = extract_cards(page)
                blocked = is_blocked(html)
                print(f"  Cards: {len(cards)}  |  Blocked: {blocked}")

                if blocked:
                    print("  🔴 Blocked — stopping")
                    break
                if len(cards) == 0:
                    print("  0 cards — last page reached")
                    break
                time.sleep(CONFIG["wait_between_pages"])
            print("\n✅ Pagination test done")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            browser.close()


# ── FULL RUN ───────────────────────────────────────────────────────────

def full_run(max_pages: int = None):
    limit     = max_pages or CONFIG["max_pages"]
    print(f"\n━━━ FULL RUN — max {limit} pages (~{limit * 40:,} records max) ━━━")
    all_cards = []
    url       = CONFIG["start_url"]
    use_proxy = False

    with sync_playwright() as pw:
        browser  = make_browser(pw, use_proxy=use_proxy)
        page     = make_page(browser)
        page_num = 1

        try:
            while page_num <= limit:
                print(f"\n── Page {page_num}/{limit} ── {url}")

                try:
                    page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
                except PWTimeout:
                    print(f"  ⏳ Timeout on page {page_num} — skipping")
                    break

                time.sleep(CONFIG["wait_after_load"])
                if page_num == 1:
                    accept_cookies(page)

                html = page.content()

                if is_blocked(html):
                    print(f"  🔴 Blocked on page {page_num} — stopping")
                    break

                cards = extract_cards(page, html)
                all_cards.extend(cards)
                print(f"  Cards this page: {len(cards)}  |  Total so far: {len(all_cards):,}  ({page_num}/{limit} pages)")

                if len(cards) == 0:
                    print("  0 cards returned — last page reached")
                    break

                page_num += 1
                url = get_next_page_url(CONFIG["start_url"], page_num)
                time.sleep(CONFIG["wait_between_pages"])

        except Exception as e:
            print(f"❌ Error on page {page_num}: {e}")
        finally:
            browser.close()

    print(f"\n📦 Total scraped : {len(all_cards)} annonces")
    seen = set()
    unique_cards = []
    for card in all_cards:
        lien = card.get("lien", "")
        if lien and lien not in seen:
            seen.add(lien)
            unique_cards.append(card)
    print(f"📦 After dedup: {len(unique_cards)} unique records")
    if unique_cards:
        save_json(unique_cards)
        save_csv(unique_cards)
        send_to_supabase(unique_cards)
    else:
        print("✅ Aucune annonce à envoyer")



# ── ENTRY ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step",  type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--pages", type=int, default=None,
                        help="Max pages to scrape (overrides CONFIG max_pages)")
    args = parser.parse_args()

    {1: step1_check_proxy,
     2: step2_probe,
     3: step3_one_page,
     4: step4_pagination}.get(args.step, lambda: full_run(args.pages))()
