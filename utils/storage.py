"""
Storage utilities for organizing and exporting captured workflows.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from utils.helpers import slugify


class WorkflowStorage:
    """Manage persisted workflow artifacts."""

    def __init__(self, base_dir: str = "output") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def save_workflow(self, workflow_result: Dict[str, Any]) -> Path:
        app = workflow_result.get("app", "unknown")
        task = workflow_result.get("task", "unknown_task")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_slug = slugify(task)
        workflow_dir = self.base_dir / app / f"{task_slug}_{timestamp}"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        screenshots_dir = workflow_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        screenshots = workflow_result.get("screenshots", [])
        for screenshot in screenshots:
            data = screenshot.get("data")
            if not data:
                continue
            step = screenshot.get("step", 0)
            screenshot_path = screenshots_dir / f"step_{str(step).zfill(2)}.png"
            screenshot_path.write_bytes(base64.b64decode(data))

        metadata = {
            **workflow_result,
            "screenshots": [
                {
                    "step": s.get("step"),
                    "url": s.get("url"),
                    "timestamp": s.get("timestamp"),
                    "filename": f"screenshots/step_{str(s.get('step')).zfill(2)}.png",
                }
                for s in screenshots
            ],
        }

        (workflow_dir / "workflow.json").write_text(json.dumps(metadata, indent=2, default=str))
        self._generate_readme(workflow_dir, metadata)
        self._generate_html(workflow_dir, metadata)

        print(f"💾 Saved workflow to: {workflow_dir}\n")
        return workflow_dir

    def _generate_readme(self, workflow_dir: Path, metadata: Dict[str, Any]) -> None:
        lines = [
            f"# {metadata.get('task', 'Workflow')}\n",
            f"**App**: {metadata.get('app', 'Unknown')}  ",
            f"**Status**: {'✅ Success' if metadata.get('success') else '❌ Failed'}  ",
            f"**Steps**: {metadata.get('total_steps', 0)}  ",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n",
            "---\n",
            "## Overview\n",
            f"This workflow demonstrates how to: {metadata.get('task', 'accomplish a task')}\n",
            f"Starting URL: {metadata.get('starting_url', 'N/A')}\n",
            "## Steps\n",
        ]

        for screenshot in metadata.get("screenshots", []):
            step = screenshot.get("step")
            filename = screenshot.get("filename", "")
            url = screenshot.get("url", "N/A")

            lines.extend(
                [
                    f"### Step {step}\n",
                    f"![Step {step}]({filename})\n",
                    f"**URL**: {url}  \n",
                    "---\n",
                ]
            )

        (workflow_dir / "README.md").write_text("\n".join(lines))

    def _generate_html(self, workflow_dir: Path, metadata: Dict[str, Any]) -> None:
        task = metadata.get("task", "Workflow")
        app = metadata.get("app", "Unknown")
        success = metadata.get("success", False)
        total_steps = metadata.get("total_steps", 0)
        screenshots = metadata.get("screenshots", [])
        status_color = "#10b981" if success else "#f59e0b"
        status_text = "✓ Completed Successfully" if success else "⚠ Incomplete"

        html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{task}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f8f9fa;
            padding: 40px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        h1 {{ color: #2563eb; margin-bottom: 20px; }}
        .meta {{ color: #666; font-size: 15px; margin-top: 10px; }}
        .status {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            margin-top: 15px;
            background: {status_color};
            color: white;
        }}
        .step {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .step-header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }}
        .step-number {{
            background: #2563eb;
            color: white;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            font-weight: bold;
            margin-right: 20px;
            flex-shrink: 0;
        }}
        .step-title {{ font-size: 22px; font-weight: 600; }}
        .step-image {{
            width: 100%;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            margin: 20px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .step-info {{
            background: #f9fafb;
            padding: 16px;
            border-radius: 8px;
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            padding: 40px 20px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class=\"container\">
        <div class=\"header\">
            <h1>{task}</h1>
            <div class=\"meta\">
                <strong>Application:</strong> {app} •
                <strong>Steps:</strong> {total_steps}
            </div>
            <div class=\"status\">{status_text}</div>
        </div>
"""

        for screenshot in screenshots:
            step = screenshot.get("step")
            filename = screenshot.get("filename", "")
            url = screenshot.get("url", "N/A")

            html += f"""
        <div class=\"step\">
            <div class=\"step-header\">
                <div class=\"step-number\">{step}</div>
                <div class=\"step-title\">Step {step}</div>
            </div>
            <img src=\"{filename}\" alt=\"Step {step}\" class=\"step-image\">
            <div class=\"step-info\">
                <strong>URL:</strong> <code>{url}</code>
            </div>
        </div>
"""

        html += """
        <div class=\"footer\">
            Generated by AI Workflow Capture System
        </div>
    </div>
</body>
</html>
"""

        (workflow_dir / "guide.html").write_text(html)

    def list_workflows(self, app_name: str | None = None) -> List[Dict[str, Any]]:
        workflows: List[Dict[str, Any]] = []
        search_dir = self.base_dir / app_name if app_name else self.base_dir

        if not search_dir.exists():
            return workflows

        for workflow_json in search_dir.rglob("workflow.json"):
            try:
                data = json.loads(workflow_json.read_text())
                workflows.append(
                    {
                        "path": str(workflow_json.parent.relative_to(self.base_dir)),
                        "app": data.get("app", "unknown"),
                        "task": data.get("task", "Unknown"),
                        "method": data.get("method", "playwright"),
                        "success": data.get("success", False),
                        "steps": data.get("total_steps", 0),
                        "date": datetime.now().isoformat(),
                    }
                )
            except Exception:  # noqa: BLE001
                continue

        return workflows

    def export_dataset(self, output_file: str = "dataset.json") -> Dict[str, Any]:
        all_workflows = self.list_workflows()

        by_app: Dict[str, List[Dict[str, Any]]] = {}
        for workflow in all_workflows:
            by_app.setdefault(workflow["app"], []).append(workflow)

        dataset = {
            "generated_at": datetime.now().isoformat(),
            "total_workflows": len(all_workflows),
            "successful_workflows": sum(1 for w in all_workflows if w["success"]),
            "apps": list(by_app.keys()),
            "workflows_by_app": by_app,
            "all_workflows": all_workflows,
        }

        output_path = self.base_dir / output_file
        output_path.write_text(json.dumps(dataset, indent=2))
        self._generate_dataset_readme(dataset)

        print("\n" + "=" * 70)
        print("📦 DATASET EXPORTED")
        print("=" * 70)
        print(f"Location: {output_path}")
        print(f"Total workflows: {len(all_workflows)}")
        print(f"Successful: {dataset['successful_workflows']}/{len(all_workflows)}")
        print(f"Apps: {', '.join(by_app.keys()) if by_app else 'None'}")
        print("=" * 70 + "\n")

        return dataset

    def _generate_dataset_readme(self, dataset: Dict[str, Any]) -> None:
        lines = [
            "# AI Workflow Capture - Dataset\n",
            f"**Generated**: {dataset['generated_at'][:10]}  ",
            f"**Total Workflows**: {dataset['total_workflows']}  ",
            f"**Successful**: {dataset['successful_workflows']}  \n",
            "---\n",
            "## Overview\n",
            "This dataset contains captured UI workflows demonstrating how to accomplish various tasks.\n",
            "Each workflow includes sequential screenshots, metadata, and human-readable guides.\n",
            "## Applications\n",
        ]

        for app, workflows in dataset["workflows_by_app"].items():
            lines.append(f"### {app.title()}\n")
            lines.append(f"**Workflows**: {len(workflows)}\n")
            for workflow in workflows:
                status = "✅" if workflow["success"] else "⚠️"
                lines.append(
                    f"- {status} **{workflow['task']}** ({workflow['steps']} steps) — `{workflow['path']}`\n"
                )
            lines.append("")

        lines.extend(
            [
                "## Structure\n",
                "```\n",
                "output/\n",
                "  {app_name}/\n",
                "    {task_slug}_{timestamp}/\n",
                "      workflow.json\n",
                "      README.md\n",
                "      guide.html\n",
                "      screenshots/\n",
                "        step_01.png\n",
                "        step_02.png\n",
                "        ...\n",
                "```\n",
                "## Usage\n",
                "- Open `guide.html` for the interactive walkthrough\n",
                "- Read `README.md` for a Markdown summary\n",
                "- Inspect `workflow.json` for structured metadata\n",
            ]
        )

        readme_path = self.base_dir / "README.md"
        readme_path.write_text("\n".join(lines))
        print(f"📄 Generated dataset README: {readme_path}")


__all__ = ["WorkflowStorage"]
