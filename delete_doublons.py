import time
import gspread
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# ── CONFIGURATION ────────────────────────────────────────────────────────
import time
import gspread
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# ── CONFIGURATION ────────────────────────────────────────────────────────
CONFIG = {
    "headless": False,
    "page_timeout": 30_000,
    "wait_between_checks": 2, 
    "colonne_lien": 1,
    "nom_onglet": "Feuille 1", # Vérifiez aussi que c'est le bon nom d'onglet !
    "url_sheet": "https://docs.google.com/spreadsheets/d/1-VLmCy1bCjGe1nuVE83nhYThkMnvtLdfaL9AeFi9maI/edit#gid=0"
}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ── LOGIQUE DE VÉRIFICATION (PLAYWRIGHT) ───────────────────────────────

def verifier_annonce(page, url):
    try:
        reponse = page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
        
        if reponse.status in [404, 410]:
            return "MORT"
        if reponse.status in [403]:
            return "ERREUR" # Bloqué par anti-bot

        html = page.content().lower()
        if "plus disponible" in html or "véhicule vendu" in html:
            return "MORT"
            
        return "ACTIF"

    except Exception as e:
        print(f"  ❌ Erreur sur {url}: {e}")
        return "ERREUR"

# ── LOGIQUE GOOGLE SHEETS & EXECUTION ──────────────────────────────────

def nettoyer_base():
    print("🔌 Connexion à Google Sheets...")
    # Connexion via le fichier JSON téléchargé
    gc = gspread.service_account(filename='credentials.json')
    
    # Ouverture du tableau
    sh = gc.open_by_url(CONFIG["url_sheet"])
    worksheet = sh.worksheet(CONFIG["nom_onglet"])
    
    # On récupère toutes les valeurs de la colonne contenant les liens
    colonne_donnees = worksheet.col_values(CONFIG["colonne_lien"])
    
    lignes_supprimees = 0

    print("🚀 Lancement du navigateur furtif...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=CONFIG["headless"],
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(user_agent=USER_AGENT, locale="fr-FR")
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # On parcourt la liste À L'ENVERS (de la fin vers le début)
        # len(colonne_donnees) donne la dernière ligne. On s'arrête à 1 (pour ignorer l'en-tête de la colonne)
        for index in range(len(colonne_donnees), 1, -1):
            
            # gspread est indexé à partir de 1, mais la liste python à partir de 0
            url = colonne_donnees[index - 1] 
            ligne_excel = index

            # Si la cellule est vide ou n'est pas un lien HTTP, on ignore
            if not url or not str(url).startswith("http"):
                continue

            print(f"[{ligne_excel}] Test de : {url}")
            statut = verifier_annonce(page, url)
            
            if statut == "MORT":
                print(f"   👉 🗑️ Annonce MORTE. Suppression de la ligne {ligne_excel}...")
                worksheet.delete_rows(ligne_excel)
                lignes_supprimees += 1
                
                # Petite pause pour ne pas saturer l'API de Google Sheets (Quota)
                time.sleep(1) 
                
            elif statut == "ACTIF":
                print("   👉 ✅ Active.")
                
            # Pause pour ne pas bloquer l'anti-bot des sites auto
            time.sleep(CONFIG["wait_between_checks"])

        browser.close()
        
    print(f"\n🎉 Nettoyage terminé ! {lignes_supprimees} annonces vendues ont été supprimées du fichier.")

if __name__ == "__main__":
    nettoyer_base()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ── LOGIQUE DE VÉRIFICATION (PLAYWRIGHT) ───────────────────────────────

def verifier_annonce(page, url):
    try:
        reponse = page.goto(url, timeout=CONFIG["page_timeout"], wait_until="domcontentloaded")
        
        if reponse.status in [404, 410]:
            return "MORT"
        if reponse.status in [403]:
            return "ERREUR" # Bloqué par anti-bot

        html = page.content().lower()
        if "plus disponible" in html or "véhicule vendu" in html:
            return "MORT"
            
        return "ACTIF"

    except Exception as e:
        print(f"  ❌ Erreur sur {url}: {e}")
        return "ERREUR"

# ── LOGIQUE GOOGLE SHEETS & EXECUTION ──────────────────────────────────

def nettoyer_base():
    print("🔌 Connexion à Google Sheets...")
    # Connexion via le fichier JSON téléchargé
    gc = gspread.service_account(filename='credentials.json')
    
    # Ouverture du tableau
    sh = gc.open_by_url(CONFIG["url_sheet"])
    worksheet = sh.worksheet(CONFIG["nom_onglet"])
    
    # On récupère toutes les valeurs de la colonne contenant les liens
    colonne_donnees = worksheet.col_values(CONFIG["colonne_lien"])
    
    lignes_supprimees = 0

    print("🚀 Lancement du navigateur furtif...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=CONFIG["headless"],
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(user_agent=USER_AGENT, locale="fr-FR")
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # On parcourt la liste À L'ENVERS (de la fin vers le début)
        # len(colonne_donnees) donne la dernière ligne. On s'arrête à 1 (pour ignorer l'en-tête de la colonne)
        for index in range(len(colonne_donnees), 1, -1):
            
            # gspread est indexé à partir de 1, mais la liste python à partir de 0
            url = colonne_donnees[index - 1] 
            ligne_excel = index

            # Si la cellule est vide ou n'est pas un lien HTTP, on ignore
            if not url or not str(url).startswith("http"):
                continue

            print(f"[{ligne_excel}] Test de : {url}")
            statut = verifier_annonce(page, url)
            
            if statut == "MORT":
                print(f"   👉 🗑️ Annonce MORTE. Suppression de la ligne {ligne_excel}...")
                worksheet.delete_rows(ligne_excel)
                lignes_supprimees += 1
                
                # Petite pause pour ne pas saturer l'API de Google Sheets (Quota)
                time.sleep(1) 
                
            elif statut == "ACTIF":
                print("   👉 ✅ Active.")
                
            # Pause pour ne pas bloquer l'anti-bot des sites auto
            time.sleep(CONFIG["wait_between_checks"])

        browser.close()
        
    print(f"\n🎉 Nettoyage terminé ! {lignes_supprimees} annonces vendues ont été supprimées du fichier.")

if __name__ == "__main__":
    nettoyer_base()