# Architecture

## Overview

Agent B combines Playwright-driven browser automation with Anthropic Claude to execute arbitrary tasks while capturing UI state. The flow:

1. **Agent B** receives a task from Agent A via CLI, stdin JSON, or demo runner.
2. **PlaywrightCapture** launches Chromium, navigates to the target app, and iteratively:
   - Captures the current UI state
   - Sends the screenshot + context to Claude
   - Executes Claude's chosen action (click/type/navigate/wait)
3. After completion, the agent packages screenshots and metadata via **WorkflowStorage**.

## Modules

- `core.config` – Loads environment variables, known app URLs, output paths. Validates Anthropic key.
- `core.agent` – Entry point for handling requests. Delegates to PlaywrightCapture and persists results.
- `capture.playwright_capture` – Vision-action loop that keeps the browser in sync with Claude’s decisions.
- `utils.helpers` – URL → app name extraction, slug generation.
- `utils.storage` – Saves screenshots, JSON metadata, Markdown, and HTML guides. Can export a dataset summary.

## Workflow Loop

```
Screenshot (PNG → base64)
        ↓
Claude (JSON decision)
        ↓
Playwright executes action
        ↓
Wait for stability → next iteration
```

Claude is prompted with the current URL, step number, and task description. It must emit JSON specifying an action and target. If the action is `done`, the loop stops.

## Output Structure

```
output/
  {app}/
    {task_slug}_{timestamp}/
      workflow.json
      README.md
      guide.html
      screenshots/
        step_01.png
        step_02.png
        ...
```

`workflow.json` retains all metadata while the HTML/Markdown files provide human-friendly artifacts.

## Extensibility

- Update `Config.APP_URLS` to add new default domains.
- Swap `Anthropic_MODEL` for other Claude variants.
- Extend `PlaywrightCapture._execute_action` for additional action types (e.g., select, hover).
- Integrate other storage backends by replacing `WorkflowStorage`.
