# ScreenFlow: Capture Any Web Workflow with AI

Playwright-driven system that partners with Anthropic Claude to capture UI workflows end-to-end. Agent B receives natural language tasks, autonomously operates a browser, records every UI state, and packages the results as datasets.

## Project Structure

```
ai-workflow-capture/
├── main.py
├── requirements.txt
├── core/
│   ├── config.py
│   └── agent.py
├── capture/
│   └── playwright_capture.py
├── tests/
│   ├── test_agent.py
│   └── test_helpers.py
├── scripts/
│   └── setup_auth.py
├── utils/
│   ├── helpers.py
│   └── storage.py
└── output/
```

## First-Time Setup: Authentication

Before capturing workflows, save your login credentials so the agent can reuse them.

### Quick Setup

```bash
python scripts/setup_auth.py
# Choose the app (e.g., 1 for Linear)
# Browser opens — log in manually
# Press Enter when done; profile saved under auth_states/
```

### Auth Files

```
auth_states/
  linear/  # persistent Chrome profile
  notion/
  asana/
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Configure environment variables in `.env` (or export them):

```
ANTHROPIC_API_KEY=your_key_here
OUTPUT_DIR=output  # optional override
MAX_STEPS=15       # optional override
```

## Usage

Interactive CLI:

```bash
python main.py
```

Explicit CLI commands are also available:

```bash
python main.py interactive   # same as running without args
python main.py api           # read JSON from stdin
```

API mode example:

```bash
echo '{"task":"Create project","app_url":"https://linear.app"}' | python main.py api
```

## Agent System Architecture

Agent B combines Playwright-driven browser automation with Anthropic Claude to execute arbitrary tasks while capturing UI state. The flow:

![Agent System Architecture](Architecture_diagram.png)

1. Agent B receives a task from Agent A via CLI or stdin JSON.
2. `PlaywrightCapture` launches Chrome, navigates to the target app, and iteratively:
   - Captures the current UI state.
   - Sends the screenshot plus context to Claude.
   - Executes Claude's chosen action (click/type/navigate/wait).
3. After completion, the agent packages screenshots and metadata via `WorkflowStorage`.

## Outputs

Runs generate `output/<app>/<task_slug_timestamp>/` containing:

- `workflow.json` – structured metadata (screenshots, actions, history)
- `README.md` – Markdown walkthrough
- `guide.html` – interactive gallery
- `screenshots/` – PNG captures of each step

When one or more workflows complete successfully in a session, the system also compiles an aggregated dataset (`output/dataset.json` and `output/README.md`) via `WorkflowStorage.export_dataset()`.

## Testing

Run the automated checks with pytest:

```bash
python -m pytest
```
