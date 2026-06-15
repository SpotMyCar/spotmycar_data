"""
debug_leparking.py — Inspecte la structure de leparking.fr
  python debug_leparking.py
"""
import os, time, json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URL = "https://www.leparking.fr/voiture-occasion.html"
UA  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
SMARTPROXY_USERNAME = os.getenv("SMARTPROXY_USERNAME", "")
SMARTPROXY_PASSWORD = os.getenv("SMARTPROXY_PASSWORD", "")
proxy_config = None
if SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD:
    proxy_config = {
        "server":   "http://eu.smartproxy.net:3120",
        "username": SMARTPROXY_USERNAME,
        "password": SMARTPROXY_PASSWORD,
    }

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, proxy=proxy_config)
    ctx = browser.new_context(user_agent=UA, locale="fr-FR",
                              viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    api_calls = []
    def on_request(request):
        url = request.url
        if any(k in url for k in ["api", "search", "listing", "vehicle",
                                   "annonce", "json", "graphql", "ajax", "query"]):
            api_calls.append({"method": request.method, "url": url})

    page.on("request", on_request)

    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    time.sleep(4)

    try:
        page.locator("button:has-text('Accepter'), button:has-text('Tout accepter')").first.click()
        time.sleep(1)
    except:
        pass

    # 1. Inspecter les cards
    result = page.evaluate("""() => {
        const selectors = ['article', '[class*="card"]', '[class*="listing"]',
                           '[class*="result"]', '[class*="vehicle"]', '[class*="offer"]',
                           '[class*="annonce"]', 'li[class*="item"]'];
        const found = [];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            if (els.length > 3) {
                const first = els[0];
                found.push({
                    selector: sel,
                    count: els.length,
                    text: first.innerText.slice(0, 200),
                    attrs: Object.fromEntries([...first.attributes].map(a => [a.name, a.value.slice(0,80)])),
                    html: first.outerHTML.slice(0, 600),
                    link: first.querySelector('a[href]') ? first.querySelector('a[href]').getAttribute('href') : ''
                });
            }
        }
        return found;
    }""")

    print("\n=== CARDS AU CHARGEMENT INITIAL ===")
    for r in result:
        print(f"\n  {r['selector']} ({r['count']} elements)")
        print(f"  link : {r['link']}")
        print(f"  text : {r['text'][:150]}")
        print(f"  html : {r['html'][:300]}")

    # 2. Boutons charger plus
    btns = page.evaluate("""() =>
        [...document.querySelectorAll('button, a')]
            .filter(el => /charger|voir plus|suivant|more|load/i.test(el.innerText))
            .slice(0, 5)
            .map(el => ({ text: el.innerText.trim(), tag: el.tagName, cls: el.className.slice(0,80) }))
    """)
    print("\n=== BOUTONS CHARGER PLUS ===")
    for b in btns:
        print(f"  <{b['tag']}> '{b['text']}' class={b['cls']}")

    # 3. Scroll x3 et observer
    print("\n=== SCROLL ===")
    for i in range(3):
        before = len(page.evaluate("() => [...document.querySelectorAll('article, [class*=card]')]"))
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)
        after = len(page.evaluate("() => [...document.querySelectorAll('article, [class*=card]')]"))
        print(f"  Scroll {i+1}: {before} → {after} cards (+{after-before})")

    print("\n=== API CALLS AU SCROLL ===")
    for c in api_calls:
        print(f"  [{c['method']}] {c['url'][:120]}")

    browser.close()
    print("\n=== DONE ===")