#!/usr/bin/env python3
"""Capture Sana-Chan dashboard layout screenshots and check obvious overflow.

Usage:
  py -3.12 scripts/dashboard_layout_check.py --base-url http://127.0.0.1:5000

Install optional dependency when you want screenshots:
  py -3.12 -m pip install playwright
  py -3.12 -m playwright install chromium
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [
    "/",
    "/invite",
    "/servers",
    "/stats",
    "/guessing",
    "/admin/ui-preview?key=ImTheBestAdmin",
    "/admin/ui-health?key=ImTheBestAdmin",
]
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000},
    "tablet": {"width": 900, "height": 1100},
    "mobile": {"width": 390, "height": 900},
}


def normalize_base_url(value: str) -> str:
    return value.rstrip("/") or "http://127.0.0.1:5000"


def safe_name(path: str) -> str:
    clean = path.strip("/") or "home"
    for character in "?=&:#%\\/":
        clean = clean.replace(character, "-")
    return clean[:90]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sana-Chan dashboard layout screenshot checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Running dashboard base URL.")
    parser.add_argument("--output", default=str(ROOT / "screenshots" / "layout-check"), help="Screenshot output directory.")
    parser.add_argument("--path", action="append", dest="paths", help="Path to check. Can be repeated.")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] Playwright is not installed. Install with: py -3.12 -m pip install playwright && py -3.12 -m playwright install chromium")
        return 0

    base_url = normalize_base_url(args.base_url)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = args.paths or DEFAULT_PATHS
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for viewport_name, viewport in VIEWPORTS.items():
                page = browser.new_page(viewport=viewport)
                for path in paths:
                    url = f"{base_url}{path if path.startswith('/') else '/' + path}"
                    response = page.goto(url, wait_until="networkidle", timeout=20000)
                    status = response.status if response else 0
                    page.screenshot(path=str(output_dir / f"{viewport_name}-{safe_name(path)}.png"), full_page=True)
                    metrics = page.evaluate(
                        """
                        () => {
                          const doc = document.documentElement;
                          const body = document.body;
                          const overflowingButtons = [...document.querySelectorAll('button, .button, a.button')]
                            .filter((el) => el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2)
                            .map((el) => (el.textContent || el.getAttribute('aria-label') || el.className || el.tagName).trim())
                            .slice(0, 8);
                          return {
                            statusWidth: doc.scrollWidth,
                            clientWidth: doc.clientWidth,
                            bodyWidth: body ? body.scrollWidth : 0,
                            overflowingButtons,
                          };
                        }
                        """
                    )
                    if status >= 500:
                        failures.append(f"{viewport_name} {path}: HTTP {status}")
                    if metrics["statusWidth"] > metrics["clientWidth"] + 2 or metrics["bodyWidth"] > metrics["clientWidth"] + 2:
                        failures.append(f"{viewport_name} {path}: horizontal overflow {metrics['statusWidth']} > {metrics['clientWidth']}")
                    if metrics["overflowingButtons"]:
                        failures.append(f"{viewport_name} {path}: button overflow {', '.join(metrics['overflowingButtons'])}")
                page.close()
        finally:
            browser.close()

    if failures:
        print("[FAIL] Dashboard layout checks found issues:")
        for failure in failures:
            print(f"- {failure}")
        print(f"Screenshots: {output_dir}")
        return 1
    print(f"[OK] Dashboard layout checks passed. Screenshots: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
