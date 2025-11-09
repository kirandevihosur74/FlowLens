"""
Main entry point for Agent B.
UPDATED: Better guidance for authentication.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from core.agent import AgentB
from utils.storage import WorkflowStorage


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

def check_auth(app_name: str | None = None) -> bool:
    if not app_name:
        return True
    profile_dir = Path('auth_states') / app_name
    return profile_dir.exists() and any(profile_dir.iterdir())


def interactive_mode() -> None:
    print("\n" + "=" * 70)
    print("🤖 AI WORKFLOW CAPTURE SYSTEM (Agent B)")
    print("   Playwright-based")
    print("=" * 70)
    print("\n⚠️  IMPORTANT: Login Required!")
    print("   If this is your first time, run: python scripts/setup_auth.py")
    print("   to save your login credentials.\n")
    print("Provide tasks from Agent A. Type 'quit' to exit.\n")

    agent = AgentB()
    results: list[dict[str, object]] = []

    while True:
        task = input("📨 Task (or 'quit'): ").strip()
        if not task or task.lower() in {"quit", "exit", "q"}:
            break

        app_url = input("🌐 App URL (optional): ").strip()
        app_name = input("📛 App name (optional): ").strip()

        if app_name and not check_auth(app_name):
            print(f"\n⚠️  No saved auth found for {app_name}!")
            print("   Run: python scripts/setup_auth.py")
            print("   Or the browser will open for manual login.\n")
            proceed = input("Continue anyway? (y/n): ").strip().lower()
            if proceed != "y":
                continue

        request: dict[str, str] = {"task": task}
        if app_url:
            request["app_url"] = app_url
        if app_name:
            request["app_name"] = app_name

        result = agent.handle_request(request)
        results.append(result)

        if result.get("success"):
            print("\n✅ SUCCESS: Workflow captured")
            print(f"📁 Output: {result.get('output_dir', 'N/A')}\n")
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}\n")

        print("-" * 70 + "\n")

    if results and any(r.get("success") for r in results):
        print("\n" + "=" * 70)
        print("📦 Generating final dataset...")
        print("=" * 70 + "\n")
        storage = WorkflowStorage()
        storage.export_dataset()

    print("\n👋 Goodbye!\n")


def demo_mode() -> None:
    print("\n" + "=" * 70)
    print("🎬 DEMO MODE - Capturing Test Workflows")
    print("=" * 70)

    apps_needed = ["linear", "notion"]
    missing_auth = [app for app in apps_needed if not check_auth(app)]
    if missing_auth:
        print(f"\n⚠️  WARNING: Missing authentication for: {', '.join(missing_auth)}")
        print("   Please run: python scripts/setup_auth.py")
        print("   to save your login credentials first.\n")
        proceed = input("Continue anyway? (browser will open for manual login) (y/n): ").strip().lower()
        if proceed != "y":
            print("\n👋 Setup auth first, then run demo mode again.\n")
            return

    print("\nThis will capture 5 example workflows for the dataset.\n")

    agent = AgentB()
    test_workflows = [
        {"task": "Create a new project in Linear", "app_url": "https://linear.app", "app_name": "linear"},
        {"task": "Filter issues by assignee in Linear", "app_url": "https://linear.app", "app_name": "linear"},
        {"task": "Create a new issue in Linear", "app_url": "https://linear.app", "app_name": "linear"},
        {"task": "Create a database in Notion", "app_url": "https://www.notion.so", "app_name": "notion"},
        {"task": "Add a property to Notion database", "app_url": "https://www.notion.so", "app_name": "notion"},
    ]

    results: list[dict[str, object]] = []

    for idx, workflow in enumerate(test_workflows, start=1):
        print("\n" + "=" * 70)
        print(f"WORKFLOW {idx}/{len(test_workflows)}")
        print("=" * 70 + "\n")
        try:
            result = agent.handle_request(workflow)
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Error: {exc}")
            results.append({"success": False, "task": workflow["task"], "error": str(exc)})
        if idx < len(test_workflows):
            import time

            print("\n⏸️  Pausing 5 seconds before next workflow...")
            time.sleep(5)

    print("\n" + "=" * 70)
    print("📦 GENERATING FINAL DATASET")
    print("=" * 70 + "\n")

    storage = WorkflowStorage()
    dataset = storage.export_dataset()

    print("\n" + "=" * 70)
    print("📊 DEMO COMPLETE")
    print("=" * 70)

    successful = sum(1 for r in results if r.get("success"))
    print(f"\nResults: {successful}/{len(results)} successful")
    print("Dataset: output/dataset.json")
    print("README: output/README.md")
    print("\nYou can now:")
    print("1. View workflows in output/{app}/{task}/guide.html")
    print("2. Review dataset.json for complete metadata")
    print("3. Use this dataset for your take-home deliverable")
    print("=" * 70 + "\n")


def api_mode() -> None:
    try:
        data = json.load(sys.stdin)
        agent = AgentB()
        result = agent.handle_request(data)
        print(json.dumps(result, indent=2, default=str))
    except json.JSONDecodeError:
        print(json.dumps({"success": False, "error": "Invalid JSON input"}))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"success": False, "error": str(exc)}))


def main() -> None:
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "--demo":
            demo_mode()
        elif command == "--api":
            api_mode()
        elif command == "--help":
            print(
                """
AI Workflow Capture System - Agent B

USAGE:
    python main.py              # Interactive mode
    python main.py --demo       # Demo mode (generate test dataset)
    python main.py --api        # API mode (JSON via stdin)
    python main.py --help       # Show this help

SETUP (FIRST TIME):
    python scripts/setup_auth.py    # Save login credentials

INTERACTIVE MODE:
    Prompts you for tasks and captures workflows interactively.

DEMO MODE:
    Runs 5 predefined workflows to generate the dataset deliverable.

For more information, see README.md
                """
            )
        else:
            print(f"Unknown command: {command}")
            print("Use --help for usage information")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
