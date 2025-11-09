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

    print("\n" + "=" * 70)
    print(f"🔐 AUTHENTICATION SETUP: {app_name}")
    print("=" * 70)
    print(f"Profile directory: {profile_dir}")
    print(f"URL: {app_url}")
    print("\nInstructions:")
    print("1. Chrome will open with a dedicated profile.")
    print("2. Complete the login flow manually.")
    print("3. When you reach the app dashboard, return here and press Enter.\n")

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
        except Exception as exc:  # noqa: BLE001
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
            print(f"🌐 Opening {app_url}...")
            try:
                page.goto(app_url, wait_until="networkidle", timeout=30000)
                logger.info("Navigation successful", extra={"url": page.url})
                print(f"✅ Page loaded: {page.url}\n")
            except Exception as nav_error:  # noqa: BLE001
                logger.error("Navigation failed", extra={"error": str(nav_error)})
                print("⚠️  Navigation failed. Please navigate manually in Chrome.\n")

            input("Press Enter after logging in and reaching the main app screen...")
            logger.info("User indicated login complete", extra={"app": app_name})
        finally:
            context.close()
            logger.info("Chrome context closed", extra={"app": app_name})

    print("\n✅ SUCCESS!")
    print(f"   Saved Chrome profile for {app_name} at {profile_dir}")
    print("   Future workflows will reuse this profile automatically.\n")


def main() -> None:
    print("\n" + "=" * 70)
    print("🔐 AUTHENTICATION SETUP FOR AI WORKFLOW CAPTURE")
    print("=" * 70)
    print("\nThis script saves Chrome profiles for each app to bypass Google SSO restrictions.\n")

    for idx, (name, url) in enumerate(APPS, start=1):
        print(f"  {idx}. {name.title()} ({url})")
    print(f"  {len(APPS) + 1}. All apps")
    print("  0. Exit")

    choice = input("\nSelect app (number): ").strip()

    try:
        choice_num = int(choice)
    except ValueError:
        logger.warning("Non-numeric menu selection", extra={"choice": choice})
        print("\n❌ Please enter a number\n")
        return

    if choice_num == 0:
        logger.info("Auth setup exited by user")
        print("\n👋 Goodbye!\n")
        return

    if choice_num == len(APPS) + 1:
        logger.info("Setting up auth for all apps")
        for app_name, app_url in APPS:
            try:
                launch_chrome_with_profile(app_name, app_url)
                print("\n" + "─" * 70 + "\n")
                time.sleep(2)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Auth setup failed", extra={"app": app_name})
                print(f"\n❌ Error setting up {app_name}: {exc}\n")
    elif 1 <= choice_num <= len(APPS):
        app_name, app_url = APPS[choice_num - 1]
        logger.info("Setting up auth for single app", extra={"app": app_name})
        launch_chrome_with_profile(app_name, app_url)
    else:
        logger.warning("Invalid menu choice", extra={"choice": choice_num})
        print("\n❌ Invalid choice\n")
        return

    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE")
    print("=" * 70)
    print("\nYou can now run:")
    print("  python main.py")
    print("\nWorkflows will reuse the saved Chrome profiles for seamless login.\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    main()
