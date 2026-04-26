import json, time, urllib.request
from playwright.sync_api import sync_playwright

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxybHNrZ3h6cmtqb3RjeGV2emFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDQ3MDc2MSwiZXhwIjoyMDkwMDQ2NzYxfQ.CUkVj_NA8GXehEL2yM57gaMVUqgxKmZ6Bq6uZqvue_s"

EXPIRED_TEXTS = {
    "autoscout24": "n'est malheureusement plus disponible",
}

def fetch_active_annonces():
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    url = f"{SUPABASE_URL}?is_expired=eq.false&select=id,lien_annonce,source&limit=200"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def mark_expired(annonce_id):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{SUPABASE_URL}?id=eq.{annonce_id}"
    payload = json.dumps({"is_expired": True}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
    urllib.request.urlopen(req)

def run():
    annonces = fetch_active_annonces()
    print(f"🔍 {len(annonces)} annonces à vérifier")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        for ann in annonces:
            source = ann["source"]
            lien   = ann["lien_annonce"]
            marker = EXPIRED_TEXTS.get(source)

            if not marker:
                print(f"  ⏭️  Source non gérée ({source}) → {lien}")
                continue

            try:
                page.goto(lien, timeout=20_000, wait_until="domcontentloaded")
                print(page.content()[:3000])
                if marker in page.content():
                    mark_expired(ann["id"])
                    print(f"  🗑️  Expirée → {lien}")
                else:
                    print(f"  ✅ Active  → {lien}")
            except Exception as e:
                print(f"  ⚠️  Erreur  → {lien} : {e}")

            time.sleep(1.5)

        browser.close()

if __name__ == "__main__":
    run()