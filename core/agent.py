"""
Main Agent B orchestrator.
Receives tasks from Agent A and captures workflows.
"""

from __future__ import annotations

from typing import Any, Dict

from capture.playwright_capture import PlaywrightCapture
from core.config import Config
from utils.helpers import extract_app_name
from utils.storage import WorkflowStorage


class AgentB:
    """Agent B – orchestrates workflow capture."""

    def __init__(self) -> None:
        self.capture = PlaywrightCapture()
        self.storage = WorkflowStorage(base_dir=Config.OUTPUT_DIR)

        print("🤖 Agent B initialized")
        print("   Ready to receive tasks from Agent A\n")

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        task = request.get("task")
        if not task:
            return {"success": False, "error": "No task provided"}

        app_name = request.get("app_name")
        app_url = request.get("app_url")

        if not app_name and app_url:
            app_name = extract_app_name(app_url)

        if not app_url and app_name:
            app_url = Config.get_app_url(app_name)

        if not app_url:
            return {
                "success": False,
                "error": "Could not determine app URL. Please provide app_url.",
            }

        if not app_name:
            app_name = extract_app_name(app_url)

        print("=" * 70)
        print("📨 REQUEST FROM AGENT A")
        print("=" * 70)
        print(f"Task: {task}")
        print(f"App: {app_name}")
        print(f"URL: {app_url}")
        print("=" * 70 + "\n")

        try:
            result = self.capture.capture_workflow(task=task, app_url=app_url, app_name=app_name)
            if result.get("success"):
                output_dir = self.storage.save_workflow(result)
                result["output_dir"] = str(output_dir)
            return result
        except Exception as exc:  # noqa: BLE001
            print(f"\n❌ Unexpected error: {exc}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(exc), "task": task, "app": app_name}


__all__ = ["AgentB"]
