"""
scrape_mytracks_db.py — Construit la base de données marques/modèles
en scrapant mytracks.fr/estimation.

Pour chaque marque disponible dans le dropdown :
  1. Clique sur la marque
  2. Récupère tous les modèles disponibles
  3. Sauvegarde dans models_db.json

Usage :
  python scrape_mytracks_db.py
  python scrape_mytracks_db.py --resume   # reprend depuis la dernière marque traitée
"""

import json, os, time, argparse
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URL       = "https://mytracks.fr/estimation"
UA        = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DB_PATH   = "models_db.json"
RAW_PATH  = "mytracks_raw.json"


def _slug(s: str) -> str:
    s = s.lower().strip()
    for src, dst in [("é","e"),("è","e"),("ê","e"),("ë","e"),
                     ("à","a"),("â","a"),("ä","a"),
                     ("ü","u"),("ù","u"),("û","u"),
                     ("ö","o"),("ô","o"),("î","i"),("ï","i"),("ç","c"),
                     ("/","_"),]:
        s = s.replace(src, dst)
    import re
    s = re.sub(r"[-\s]+", " ", s).strip()
    return s


def get_all_makes(page) -> list:
    """Récupère toutes les marques depuis le dropdown ouvert."""
    makes = page.evaluate("""() => {
        const items = document.querySelectorAll(
            '.relative.flex.cursor-default.select-none.items-center'
        );
        return [...items].map(el => el.innerText.trim()).filter(t => t.length > 0);
    }""")
    return makes


def open_make_dropdown(page):
    """Ouvre le dropdown marque."""
    page.locator("button:has-text('Marque')").first.click()
    time.sleep(0.8)


def select_make(page, make: str):
    """Clique sur une marque dans le dropdown."""
    page.locator(f".relative.flex.cursor-default.select-none.items-center >> text='{make}'").first.click()
    time.sleep(1)


def open_model_dropdown(page):
    """Ouvre le dropdown modèle après avoir sélectionné une marque."""
    try:
        page.locator("button:has-text('Modèle')").first.click()
        time.sleep(0.8)
        return True
    except:
        return False


def get_all_models(page) -> list:
    """Récupère tous les modèles depuis le dropdown modèle ouvert."""
    models = page.evaluate("""() => {
        const items = document.querySelectorAll(
            '.relative.flex.cursor-default.select-none.items-center'
        );
        return [...items].map(el => el.innerText.trim()).filter(t => t.length > 0);
    }""")
    return models


def close_dropdown(page):
    """Ferme le dropdown en cliquant ailleurs."""
    page.keyboard.press("Escape")
    time.sleep(0.3)


def reset_form(page):
    """Recharge la page pour repartir avec un formulaire vide."""
    page.reload(wait_until="domcontentloaded")
    time.sleep(2)
    try:
        page.locator("button:has-text('Accepter')").first.click(timeout=2000)
        time.sleep(0.5)
    except:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true",
                        help="Reprend depuis le dernier point de sauvegarde")
    args = parser.parse_args()

    # Charger les données existantes si resume
    raw = {}
    if args.resume and os.path.exists(RAW_PATH):
        with open(RAW_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"📂 Reprise — {len(raw)} marques déjà traitées")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx  = browser.new_context(user_agent=UA, locale="fr-FR",
                                   viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        # ── Chargement initial ──────────────────────────────────────
        print("🌐 Chargement de mytracks.fr...")
        page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)
        try:
            page.locator("button:has-text('Accepter')").first.click(timeout=3000)
            time.sleep(0.5)
        except:
            pass

        # ── Récupérer la liste des marques ──────────────────────────
        print("📋 Récupération des marques...")
        open_make_dropdown(page)
        all_makes = get_all_makes(page)
        close_dropdown(page)

        if not all_makes:
            print("❌ Aucune marque trouvée — arrêt")
            browser.close()
            return

        print(f"✅ {len(all_makes)} marques trouvées")

        # Filtrer les marques déjà traitées si resume
        makes_to_process = [m for m in all_makes if m not in raw]
        print(f"📝 {len(makes_to_process)} marques à traiter")

        # ── Traiter chaque marque ───────────────────────────────────
        for i, make in enumerate(makes_to_process):
            print(f"\n  [{i+1}/{len(makes_to_process)}] {make}...", end=" ", flush=True)

            try:
                # Ouvrir dropdown marque et sélectionner
                open_make_dropdown(page)
                time.sleep(0.3)

                # Chercher et cliquer sur la marque
                item = page.locator(
                    f"div.relative.flex.cursor-default.select-none.items-center"
                ).filter(has_text=make).first
                item.click(timeout=3000)
                time.sleep(1)

                # Ouvrir dropdown modèle
                if not open_model_dropdown(page):
                    print("⚠️  dropdown modèle inaccessible")
                    raw[make] = []
                    reset_form(page)
                    continue

                # Récupérer les modèles
                models = get_all_models(page)
                close_dropdown(page)

                raw[make] = models
                print(f"→ {len(models)} modèles")

                # Sauvegarder après chaque marque
                with open(RAW_PATH, "w", encoding="utf-8") as f:
                    json.dump(raw, f, ensure_ascii=False, indent=2)

                # Reset pour la prochaine marque
                reset_form(page)

            except Exception as e:
                print(f"❌ Erreur: {e}")
                raw[make] = []
                try:
                    reset_form(page)
                except:
                    pass

        browser.close()

    # ── Construire le DB final ──────────────────────────────────────
    print(f"\n📦 Construction de {DB_PATH}...")
    db = {}
    for make, models in raw.items():
        make_slug = _slug(make)
        db[make_slug] = {
            "_display": make,           # nom d'affichage officiel
            "_models":  {}
        }
        for model in models:
            model_slug = _slug(model)
            # Stocker le modèle avec plusieurs aliases
            db[make_slug]["_models"][model_slug] = model
            # Alias sans espaces
            db[make_slug]["_models"][model_slug.replace(" ", "")] = model
            # Alias avec tiret
            db[make_slug]["_models"][model_slug.replace(" ", "-")] = model

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    total_models = sum(len(v["_models"]) for v in db.values())
    print(f"✅ {DB_PATH} — {len(db)} marques, {total_models} aliases de modèles")
    print(f"\nAperçu :")
    for make in list(db.keys())[:3]:
        models = list(db[make]["_models"].items())[:4]
        print(f"  {db[make]['_display']}: {[v for k,v in models]}")


if __name__ == "__main__":
    main()