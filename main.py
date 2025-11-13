"""
Main entry point for Agent B.
UPDATED: Smart app detection and improved interactive mode.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from core.agent import AgentB
from core.config import Config
from utils.helpers import detect_app_from_task
from utils.storage import WorkflowStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

logger = logging.getLogger(__name__)

def check_auth(app_name: str | None = None) -> bool:
    """Looks for a saved Playwright auth profile so we know whether the browser can auto-login."""
    if not app_name:
        return True
    profile_dir = Path("auth_states") / app_name
    return profile_dir.exists() and any(profile_dir.iterdir())


def interactive_mode() -> None:
    """Runs the friendly CLI loop that captures workflows and auto-detects the target app when it can."""

    separator = "=" * 70
    logger.info("")
    logger.info(separator)
    logger.info("AI WORKFLOW CAPTURE SYSTEM (Agent B)")
    logger.info("   Playwright-based with Smart App Detection")
    logger.info(separator)
    logger.info("")
    logger.info("TIP: Include app name in your task for auto-detection!")
    logger.info("   Examples:")
    logger.info("   - 'Create a project in Linear'")
    logger.info("   - 'On a blank page, create a new database in Notion'")
    logger.info("   - 'Create a task in Asana'")
    logger.info("")
    logger.info("IMPORTANT: Run 'python scripts/setup_auth.py' first for best results.")
    logger.info("")
    logger.info("Type 'quit' to exit.")
    logger.info("")

    agent = AgentB()
    results: list[dict[str, object]] = []

    while True:
        task = input("Task (or 'quit'): ").strip()
        if not task or task.lower() in {"quit", "exit", "q"}:
            break

        detected_app = detect_app_from_task(task, Config.APP_URLS)

        if detected_app:
            detected_url = Config.get_app_url(detected_app)
            logger.info("")
            logger.info("Auto-detected: %s (%s)", detected_app.title(), detected_url)
            logger.info("   Using detected app automatically.")
            app_name = detected_app
            app_url = detected_url
            logger.info("")
        else:
            logger.info("")
            logger.info("WARNING: Could not detect app from task.")
            logger.info("   Please provide app details:")
            app_url = input("   App URL (optional): ").strip()
            app_name = input("   App name (optional): ").strip()
            logger.info("")

        if app_name and not check_auth(app_name):
            logger.info("WARNING: No saved auth found for %s!", app_name)
            logger.info("   Run: python scripts/setup_auth.py")
            logger.info("   Or the browser will open for manual login.")
            logger.info("")
            proceed = input("   Continue anyway? (y/n): ").strip().lower()
            if proceed != "y":
                logger.info("")
                continue

        request: dict[str, str] = {"task": task}
        if app_url:
            request["app_url"] = app_url
        if app_name:
            request["app_name"] = app_name

        logger.info("%s", "─" * 70)
        logger.info("")
        result = agent.handle_request(request)
        results.append(result)

        if result.get("success"):
            logger.info("")
            logger.info("SUCCESS: Workflow captured")
            logger.info("Output: %s", result.get("output_dir", "N/A"))
            logger.info("")
        else:
            logger.info("")
            logger.info("FAILED: %s", result.get("error", "Unknown error"))
            logger.info("")

        logger.info("%s", "-" * 70)
        logger.info("")

    if results and any(r.get("success") for r in results):
        logger.info("")
        logger.info(separator)
        logger.info("Generating final dataset...")
        logger.info("%s", separator)
        logger.info("")
        storage = WorkflowStorage()
        storage.export_dataset()


def api_mode() -> None:
    """Reads a JSON request from stdin so other tools can drive Agent B without the interactive prompts."""
    try:
        data = json.load(sys.stdin)
        agent = AgentB()
        result = agent.handle_request(data)
        logger.info("%s", json.dumps(result, indent=2, default=str))
    except json.JSONDecodeError:
        logger.info("%s", json.dumps({"success": False, "error": "Invalid JSON input"}))
    except Exception as exc:
        logger.info("%s", json.dumps({"success": False, "error": str(exc)}))


def main() -> None:
    """Dispatches CLI commands so users can launch interactive mode or wire up the API-friendly flow."""
    if len(sys.argv) == 1:
        interactive_mode()
        return

    command = sys.argv[1].lower()

    if command in {"interactive", "i"}:
        interactive_mode()
    elif command in {"api", "a"}:
        api_mode()
    elif command in {"help", "-h", "--help"}:
        logger.info("")
        logger.info(
            "Usage: python main.py [interactive|api]\n"
            "   interactive (default) - start interactive capture mode\n"
            "   api                   - read JSON request from stdin\n"
        )
    else:
        logger.info("")
        logger.info("WARNING: Unknown command: %s", command)
        logger.info(
            "Available commands:\n"
            "   interactive (default)\n"
            "   api\n"
        )


if __name__ == "__main__":
    main()