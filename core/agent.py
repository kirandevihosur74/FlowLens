"""
Main Agent B orchestrator.
Receives tasks from Agent A and captures workflows.
"""

from __future__ import annotations

from typing import Any, Dict

import logging

from capture.playwright_capture import PlaywrightCapture
from core.config import Config
from utils.helpers import detect_app_from_task, extract_app_name
from utils.storage import WorkflowStorage


logger = logging.getLogger(__name__)


class AgentB:
    """Agent B – orchestrates workflow capture with smart app detection."""

    def __init__(self) -> None:
        self.capture = PlaywrightCapture()
        self.storage = WorkflowStorage(base_dir=Config.OUTPUT_DIR)

        logger.info("Agent B initialized")
        logger.info("   Ready to receive tasks from Agent A")
        logger.info("")

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Figures out the right app context, hands the task to Playwright, and bundles the capture results."""

        task = request.get("task")
        if not task:
            return {"success": False, "error": "No task provided"}

        app_name = request.get("app_name")
        app_url = request.get("app_url")

        if not app_name and not app_url:
            detected_app = detect_app_from_task(task, Config.APP_URLS)
            if detected_app:
                app_name = detected_app
                logger.info("Detected app from task: '%s'", task)
                logger.info("   → %s", app_name.title())
                logger.info("")

        if not app_name and app_url:
            app_name = extract_app_name(app_url)

        if not app_url and app_name:
            app_url = Config.get_app_url(app_name)

        if not app_url:
            return {
                "success": False,
                "error": (
                    "Could not determine app URL. Please provide either:\n"
                    "  - app_url (e.g., 'https://linear.app')\n"
                    "  - app_name (e.g., 'linear')\n"
                    "  - Or include app name in task (e.g., 'Create project in Linear')"
                ),
            }

        if not app_name:
            app_name = extract_app_name(app_url)

        separator = "=" * 70
        logger.info("%s", separator)
        logger.info("REQUEST FROM AGENT A")
        logger.info("%s", separator)
        logger.info("Task: %s", task)
        logger.info("App: %s", app_name)
        logger.info("URL: %s", app_url)
        logger.info("%s", separator)
        logger.info("")

        try:
            result = self.capture.capture_workflow(task=task, app_url=app_url, app_name=app_name)
            if result.get("success"):
                output_dir = self.storage.save_workflow(result)
                result["output_dir"] = str(output_dir)
            return result
        except Exception as exc:
            logger.info("")
            logger.error("Unexpected error: %s", exc, exc_info=True)
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(exc), "task": task, "app": app_name}


__all__ = ["AgentB"]
