"""റിപ്പോർട്ട് വെബ്‌പേജ് PDF ആക്കുന്ന ഭാഗം (headless Chromium വഴി, GM World ചെയ്യുന്ന അതേ രീതി).

GitHub-ൽ workflow തന്നെ Chromium ഇൻസ്റ്റാൾ ചെയ്യും. Chromium ഇല്ലാത്തിടത്ത് (ഉദാ: സ്വന്തം
കമ്പ്യൂട്ടറിൽ പരീക്ഷിക്കുമ്പോൾ) PDF ഒഴിവാക്കും, ബാക്കി റിപ്പോർട്ട് സാധാരണപോലെ.
"""
from pathlib import Path


def render(html_path, pdf_path):
    """വിജയിച്ചാൽ pdf_path, പരാജയപ്പെട്ടാൽ None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  PDF ഒഴിവാക്കി: playwright ഇൻസ്റ്റാൾ ചെയ്തിട്ടില്ല")
        return None
    html_path, pdf_path = Path(html_path).resolve(), Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 900, "height": 1200})
            page.emulate_media(media="print", color_scheme="light")
            page.goto(html_path.as_uri(), wait_until="networkidle", timeout=60000)
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(500)
            page.pdf(path=str(pdf_path), format="A4", print_background=True,
                     margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
            browser.close()
        return pdf_path
    except Exception as e:  # noqa: BLE001
        print(f"  PDF ഉണ്ടാക്കാനായില്ല: {str(e)[:150]}")
        return None


def render_chart(data, png_path):
    """ബ്രെഡ്ത്ത് ഗ്രാഫുകൾ PNG ചിത്രമാക്കും (Telegram-ന്). പരാജയപ്പെട്ടാൽ None."""
    try:
        from playwright.sync_api import sync_playwright
        from lib import charts
    except ImportError:
        return None
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = png_path.with_suffix(".html")
    tmp.write_text(charts.standalone_html(data), encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 700, "height": 600}, device_scale_factor=2)
            page.goto(tmp.resolve().as_uri(), wait_until="networkidle", timeout=60000)
            page.evaluate("document.fonts.ready")
            page.locator("#c").screenshot(path=str(png_path))
            browser.close()
        return png_path
    except Exception as e:  # noqa: BLE001
        print(f"  ഗ്രാഫ് ചിത്രം ഉണ്ടാക്കാനായില്ല: {str(e)[:150]}")
        return None
