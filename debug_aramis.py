"""
Debug — dump inner_text de 10 cards pour repérer les variations de structure.
  python debug_aramis.py
"""
import time, json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URL = "https://www.aramisauto.com/achat/"
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

    cards = page.evaluate("""() =>
        [...document.querySelectorAll('a.product-card')].slice(0, 10).map(a => {
            const wrapper = a.querySelector('.product-card-content-wrapper');
            const attrs   = {};
            for (const attr of a.attributes) attrs[attr.name] = attr.value;
            return {
                href:  a.getAttribute('href') || '',
                attrs: attrs,
                lines: (wrapper ? wrapper.innerText : a.innerText)
                         .split('\\n')
                         .map(l => l.trim())
                         .filter(l => l.length > 0)
            };
        })
    """)

    for i, card in enumerate(cards):
        print(f"\n{'='*60}")
        print(f"Card {i} — {card['href']}")
        print(f"  makerid={card['attrs'].get('makerid','')}  modelid={card['attrs'].get('modelid','')}")
        for j, line in enumerate(card['lines']):
            print(f"  L{j:2d} → {repr(line)}")

    browser.close()
    print("\n=== DONE ===")