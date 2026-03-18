"""
Debug — capture the real listing URL by intercepting network requests.
  python debug.py
"""
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URL = "https://www.autoscout24.fr/lst?sort=age&desc=1&ustate=N%2CU&size=20&page=1&cy=F&atype=C"
UA  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent=UA, locale="fr-FR")
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)

    try:
        page.locator("button:has-text('Tout accepter')").first.click()
        time.sleep(1)
    except:
        pass

    # Inspect first 3 articles — get guid and all hrefs inside
    result = page.evaluate("""() =>
        [...document.querySelectorAll('article')].slice(0, 3).map(a => {
            const guid = a.getAttribute('data-guid') || a.id || '';
            const allAnchors = [...a.querySelectorAll('a')].map(el => ({
                href_attr: el.getAttribute('href') || '',
                href_prop: el.href || '',
                text: el.innerText.slice(0, 40)
            }));
            return { guid, allAnchors };
        })
    """)

    print("\n=== ARTICLES ===")
    for i, art in enumerate(result):
        print(f"\nArticle {i} — guid: {art['guid']}")
        print(f"  Anchors inside ({len(art['allAnchors'])}):")
        for a in art['allAnchors']:
            print(f"    attr : {a['href_attr'][:100]}")
            print(f"    prop : {a['href_prop'][:100]}")

    browser.close()
    print("\n=== DONE ===")