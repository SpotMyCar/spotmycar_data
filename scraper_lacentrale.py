import asyncio
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

URL = "https://www.lacentrale.fr/listing"

async def main():
    stealth = Stealth()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await stealth.async_stealth(page)

        print(f"⏳ Chargement...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))

        # Scroll humain
        await page.mouse.move(640, 400)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await page.mouse.wheel(0, 300)
        await asyncio.sleep(random.uniform(0.8, 1.5))

        html = await page.content()
        with open("debug2.html", "w", encoding="utf-8") as f:
            f.write(html)

        print(f"✓ HTML : {len(html)} caractères")
        print(f"📄 Titre : {await page.title()}")

        cards = await page.query_selector_all("a[href*='/voiture-']")
        print(f"🚗 Liens voitures : {len(cards)}")

        await browser.close()

asyncio.run(main())