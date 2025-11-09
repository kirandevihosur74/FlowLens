# AI Workflow Capture

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

### Manual Setup (Alternative)

```bash
# macOS example
CHROME_EXECUTABLE=/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
python - <<'PY'
import os, subprocess
from pathlib import Path
chrome = os.environ['CHROME_EXECUTABLE']
profile = Path('auth_states/linear')
profile.mkdir(parents=True, exist_ok=True)
subprocess.Popen([chrome, f'--user-data-dir={profile}', '--start-maximized', 'https://linear.app'])
input('Login manually, then press Enter...')
PY
```

### Auth Files

```
auth_states/
  linear/  # persistent Chrome profile
  notion/
  asana/
```

**Security Note:** These files contain session tokens. Keep `auth_states/` out of version control (see `.gitignore`).

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

Interactive mode:

```bash
python main.py
```

Demo mode (captures sample workflows and builds a dataset):

```bash
python main.py --demo
```

API mode (read request from stdin, respond with JSON):

```bash
echo '{"task":"Create project","app_url":"https://linear.app"}' | python main.py --api
```

## Outputs

Runs generate `output/<app>/<task_slug_timestamp>/` containing:

- `workflow.json` – structured metadata (screenshots, actions, history)
- `README.md` – Markdown walkthrough
- `guide.html` – interactive gallery
- `screenshots/` – PNG captures of each step

`python main.py --demo` additionally compiles `output/dataset.json` and `output/README.md` summarizing every workflow.

## Notes

- Uses Chromium launched by Playwright (non-headless) with a modern UA string.
- Claude must return valid JSON decisions; malformed responses are handled and may stop the run early.
- The system is general-purpose: no workflows are hardcoded beyond optional URL hints in `core.config.Config.APP_URLS`.
- Saved auth states dramatically improve success rates—run `python scripts/setup_auth.py` for each app before demoing.
- Requires Google Chrome installed locally (the system launches the Chrome channel for authentication).
- Close any Chrome window using the same profile before running; delete `auth_states/<app>/SingletonLock` if a previous session crashed.
