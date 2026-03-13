import asyncio
import sys
import argparse
from playwright.async_api import async_playwright


async def take_screenshot(url, output_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Set a standard desktop viewport for UI comparison
        await page.set_viewport_size({"width": 1280, "height": 800})
        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle")
            await page.screenshot(path=output_path, full_page=True)
            print(f"Screenshot successfully saved to {output_path}")
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            sys.exit(1)
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Take a screenshot of a webpage")
    parser.add_argument("--url", default="http://localhost:3000", help="URL to capture")
    parser.add_argument("--output", default="current_ui.png", help="Output file path")
    args = parser.parse_args()

    asyncio.run(take_screenshot(args.url, args.output))
