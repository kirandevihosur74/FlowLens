"""
One-time authentication setup script.

Launches real Google Chrome with a dedicated profile so you can log in manually.
Playwright handles launching Chrome, navigation, and graceful shutdown so the saved
profile can be reused by workflow captures.

Usage:
    python scripts/setup_auth.py
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

APPS = [
    ("linear", "https://linear.app"),
    ("notion", "https://www.notion.so"),
    ("asana", "https://app.asana.com"),
]


def cleanup_singleton_locks(profile_dir: Path) -> None:
    """Remove Chrome lock files so profiles can be reopened."""

    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    for name in lock_files:
        path = profile_dir / name
        try:
            if path.exists():
                path.unlink()
                logger.debug("Removed stale %s", name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not remove %s: %s", name, exc)


def launch_chrome_with_profile(app_name: str, app_url: str) -> None:
    """Launch Chrome via Playwright using a persistent profile."""

    profile_dir = Path("auth_states") / app_name.lower()
    profile_dir.mkdir(parents=True, exist_ok=True)
    cleanup_singleton_locks(profile_dir)

    separator = "=" * 70
    logger.info("")
    logger.info(separator)
    logger.info("AUTHENTICATION SETUP: %s", app_name)
    logger.info(separator)
    logger.info("Profile directory: %s", profile_dir)
    logger.info("URL: %s", app_url)
    logger.info("")
    logger.info("Instructions:")
    logger.info("1. Chrome will open with a dedicated profile.")
    logger.info("2. Complete the login flow manually.")
    logger.info("3. When you reach the app dashboard, return here and press Enter.")
    logger.info("")

    logger.info("Launching Chrome", extra={"app": app_name, "profile": str(profile_dir)})

    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--start-maximized",
                ],
                viewport={"width": 1920, "height": 1080},
            )
        except Exception as exc: 
            logger.exception("Failed to launch Chrome", extra={"app": app_name})
            raise

        try:
            logger.info("Waiting for Chrome to initialize")
            time.sleep(3)

            if context.pages:
                page = context.pages[0]
                logger.info("Using existing page", extra={"url": page.url})
            else:
                page = context.new_page()
                logger.info("Created new page")

            logger.info("Navigating", extra={"url": app_url})
            logger.info("Opening %s...", app_url)
            try:
                page.goto(app_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
                logger.info("Navigation successful", extra={"url": page.url})
                logger.info("Page loaded: %s", page.url)
                logger.info("")
            except Exception as nav_error: 
                logger.error("Navigation failed", extra={"error": str(nav_error)})
                logger.info("WARNING: Navigation failed. Please navigate manually in Chrome.")
                logger.info("")

            input("Press Enter after logging in and reaching the main app screen...")
            logger.info("User indicated login complete", extra={"app": app_name})
        finally:
            context.close()
            logger.info("Chrome context closed", extra={"app": app_name})

    logger.info("")
    logger.info("SUCCESS!")
    logger.info("   Saved Chrome profile for %s at %s", app_name, profile_dir)
    logger.info("   Future workflows will reuse this profile automatically.")
    logger.info("")


def main() -> None:
    separator = "=" * 70
    logger.info("")
    logger.info(separator)
    logger.info("AUTHENTICATION SETUP FOR AI WORKFLOW CAPTURE")
    logger.info(separator)
    logger.info("")
    logger.info("This script saves Chrome profiles for each app to bypass Google SSO restrictions.")
    logger.info("")

    for idx, (name, url) in enumerate(APPS, start=1):
        logger.info("  %d. %s (%s)", idx, name.title(), url)
    logger.info("  %d. All apps", len(APPS) + 1)
    logger.info("  0. Exit")

    choice = input("\nSelect app (number): ").strip()

    try:
        choice_num = int(choice)
    except ValueError:
        logger.warning("Non-numeric menu selection", extra={"choice": choice})
        logger.info("")
        logger.info("Please enter a number")
        logger.info("")
        return

    if choice_num == 0:
        logger.info("Auth setup exited by user")
        logger.info("")
        logger.info("Goodbye!")
        logger.info("")
        return

    if choice_num == len(APPS) + 1:
        logger.info("Setting up auth for all apps")
        for app_name, app_url in APPS:
            try:
                launch_chrome_with_profile(app_name, app_url)
                logger.info("")
                logger.info("%s", "─" * 70)
                logger.info("")
                time.sleep(2)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Auth setup failed", extra={"app": app_name})
                logger.info("")
                logger.error("Error setting up %s: %s", app_name, exc, exc_info=True)
                logger.info("")
    elif 1 <= choice_num <= len(APPS):
        app_name, app_url = APPS[choice_num - 1]
        logger.info("Setting up auth for single app", extra={"app": app_name})
        launch_chrome_with_profile(app_name, app_url)
    else:
        logger.warning("Invalid menu choice", extra={"choice": choice_num})
        logger.info("")
        logger.info("Invalid choice")
        logger.info("")
        return

    logger.info("")
    logger.info(separator)
    logger.info("SETUP COMPLETE")
    logger.info(separator)
    logger.info("")
    logger.info("You can now run:")
    logger.info("  python main.py")
    logger.info("")
    logger.info("Workflows will reuse the saved Chrome profiles for seamless login.")
    logger.info("")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    main()
