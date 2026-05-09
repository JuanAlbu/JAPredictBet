"""Scrape Superbet using Playwright (headless Chromium) to capture JS-rendered events.

Usage:
    python scripts/scrape_superbet_playwright.py [--day quinta-feira] [--headless]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# --- Config ---
DAY = "quinta-feira"  # default: Thursday (tomorrow)
if len(sys.argv) > 1 and sys.argv[1].startswith("--day="):
    DAY = sys.argv[1].split("=", 1)[1]
HEADLESS = "--no-headless" not in sys.argv

OUTPUT_DIR = ROOT / "data"
OUTPUT_FILE = OUTPUT_DIR / f"_playwright_{DAY.replace('-','_')}.json"

URL = f"https://superbet.bet.br/apostas/futebol?day={DAY}"

# We'll intercept SSE and REST API calls on these patterns
INTERCEPT_PATTERNS = [
    "freetls.fastly.net",
    "events/prematch",
    "events/all",
    "v2/pt-BR/events",
    "tournaments",
    "offer",
]


def main() -> None:
    print("=" * 70)
    print(f"  PLAYWRIGHT SCRAPER - Superbet day={DAY}")
    print(f"  URL: {URL}")
    print(f"  Headless: {HEADLESS}")
    print("=" * 70)

    from playwright.sync_api import sync_playwright

    results: dict[str, Any] = {
        "url": URL,
        "day": DAY,
        "captured_requests": [],
        "captured_responses": [],
        "page_title": "",
        "page_content_snippets": [],
        "events_found": [],
    }

    captured_events: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
        )
        page = context.new_page()

        # Intercept network requests
        def handle_request(request):
            url = request.url
            method = request.method
            # Only capture relevant URLs
            if any(p in url for p in INTERCEPT_PATTERNS) or "api" in url.lower():
                results["captured_requests"].append({
                    "url": url,
                    "method": method,
                    "resource_type": request.resource_type,
                })
                print(f"  [REQUEST] {method} {url[:120]}")

        def handle_response(response):
            url = response.url
            status = response.status
            # Only capture relevant URLs
            if any(p in url for p in INTERCEPT_PATTERNS) or "api" in url.lower():
                try:
                    body = response.text()
                    content_preview = body[:500] if body else ""
                except Exception:
                    content_preview = ""
                
                result_item = {
                    "url": url,
                    "status": status,
                    "content_type": response.headers.get("content-type", ""),
                    "content_length": len(content_preview),
                    "content_preview": content_preview,
                }
                results["captured_responses"].append(result_item)
                print(f"  [RESPONSE] {status} {url[:120]} ({len(content_preview)} chars)")

                # Try to parse JSON from response
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        data = response.json()
                        # Extract event IDs if present
                        if isinstance(data, dict):
                            for key in ["id", "eventId", "event_id", "matchId"]:
                                if key in data:
                                    captured_events.append({
                                        "source": url,
                                        "event_id": data[key],
                                        "data": str(data)[:300],
                                    })
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    for key in ["id", "eventId", "event_id", "matchId"]:
                                        if key in item:
                                            captured_events.append({
                                                "source": url,
                                                "event_id": item[key],
                                                "data": str(item)[:300],
                                            })
                    except Exception:
                        pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # Navigate and wait for content to load
        print(f"\n  Navigando para {URL}...")
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"  [WARN] Timeout/navigation issue: {e}")
            # Still continue - page might have loaded partially

        # Wait a bit more for dynamic content
        page.wait_for_timeout(5000)

        # Get page title
        results["page_title"] = page.title()
        print(f"\n  Page title: {page.title()}")

        # Try to extract text content - look for event/match elements
        try:
            # Get all visible text
            body_text = page.inner_text("body")
            # Save snippets of the body text
            lines = [l.strip() for l in body_text.split("\n") if l.strip()]
            results["page_content_snippets"] = lines[:200]

            # Try to find elements with event/match data
            selectors_to_try = [
                "div[data-event-id]",
                "div[data-match-id]",
                "div[data-tournament-id]",
                "[class*=event]",
                "[class*=match]",
                "[class*=game]",
                "[data-testid*=event]",
                "[data-testid*=match]",
                "a[href*='/odds/']",
            ]

            for selector in selectors_to_try:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        print(f"\n  Found {len(elements)} elements matching '{selector}'")
                        for el in elements[:10]:
                            html = el.inner_html()[:200]
                            attrs = el.evaluate("el => { const attrs = {}; for (const attr of el.attributes) { attrs[attr.name] = attr.value; } return attrs; }")
                            print(f"    Attributes: {attrs}")
                            print(f"    HTML: {html[:100]}")
                except Exception as e:
                    print(f"    Selector '{selector}' error: {e}")

        except Exception as e:
            print(f"  [WARN] Could not extract content: {e}")

        # Save screenshot for debugging
        screenshot_path = OUTPUT_DIR / f"_screenshot_{DAY}.png"
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"\n  Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"  [WARN] Screenshot failed: {e}")

        # Try to get the full HTML after JS execution
        html_after_js = page.content()
        results["html_after_js_length"] = len(html_after_js)
        
        # Save full HTML for analysis
        html_path = OUTPUT_DIR / f"_page_html_{DAY}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_after_js)
        print(f"\n  Full HTML saved: {html_path} ({len(html_after_js)} bytes)")

        results["events_found"] = captured_events
        browser.close()

    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Results saved: {OUTPUT_FILE}")
    print(f"  Captured {len(captured_events)} events from API responses")
    print(f"  Captured {len(results['captured_requests'])} requests")
    print(f"  Captured {len(results['captured_responses'])} responses")
    print("  Done!")


if __name__ == "__main__":
    main()
