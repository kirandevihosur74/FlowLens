"""
Playwright-based workflow capture - UPDATED WITH ALL FIXES

- Action history tracking (prevents loops)
- Loop detection
- Stricter JSON prompts
- Better error recovery
- Auth state loading
"""

from __future__ import annotations

import base64
import json
import time
import re
import logging
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright, Page
from anthropic import Anthropic

from core.config import Config
from utils.helpers import slugify


logger = logging.getLogger(__name__)


class PlaywrightCapture:
    """Capture workflows using Playwright + Claude vision."""

    def __init__(self) -> None:
        self.anthropic = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def capture_workflow(
        self,
        task: str,
        app_url: str,
        app_name: str,
        max_steps: int | None = None,
    ) -> Dict[str, Any]:
        """Capture a complete workflow with loop prevention and auth loading."""

        max_steps = max_steps or Config.MAX_STEPS

        print("\n" + "=" * 70)
        print("🎬 STARTING WORKFLOW CAPTURE")
        print("=" * 70)
        print(f"Task: {task}")
        print(f"App: {app_name}")
        print(f"URL: {app_url}")
        print("=" * 70 + "\n")

        screenshots: List[Dict[str, Any]] = []
        action_history: List[Dict[str, Any]] = []
        step_count = 0

        with sync_playwright() as playwright:
            profile_root = Path("auth_states")
            profile_name = slugify(app_name) or app_name.lower()
            profile_dir = profile_root / profile_name
            profile_dir.mkdir(parents=True, exist_ok=True)

            lock_file = profile_dir / "SingletonLock"
            if lock_file.exists():
                lock_file.unlink(missing_ok=True)

            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel="chrome",
                    headless=False,
                    args=["--start-maximized"],
                )
            except Exception:
                logger.warning("Falling back to bundled Chromium", extra={"profile": str(profile_dir)})
                print("⚠️  Could not launch Chrome channel; falling back to bundled Chromium.")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    args=["--start-maximized"],
                )

            if any(profile_dir.iterdir()):
                logger.info("Using persisted Chrome profile", extra={"profile": str(profile_dir)})
                print(f"✅ Using persisted Chrome profile for {profile_name}\n")
            else:
                logger.warning("No saved auth profile found", extra={"profile": str(profile_dir)})
                print("⚠️  No saved auth profile found. Browser will open for manual login.")
                print("   Run: python scripts/setup_auth.py for best results.\n")

            pages = context.pages
            page = pages[0] if pages else context.new_page()

            try:
                logger.info("Navigating", extra={"url": app_url})
                print(f"🌐 Navigating to: {app_url}")
                page.goto(app_url, wait_until="networkidle", timeout=30000)
                time.sleep(2)
                print("✅ Page loaded\n")

                for step in range(1, max_steps + 1):
                    step_count = step
                    print("─" * 70)
                    print(f"Step {step}/{max_steps}")
                    print("─" * 70)

                    screenshot_bytes = page.screenshot(type="png", full_page=False)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                    screenshots.append(
                        {
                            "step": step,
                            "data": screenshot_b64,
                            "url": page.url,
                            "timestamp": time.time(),
                            "title": page.title(),
                        }
                    )

                    decision = self._ask_claude(
                        screenshot_b64,
                        task,
                        page.url,
                        step,
                        action_history,
                    )

                    print(f"🎯 Action: {decision['action']}")
                    print(f"💭 {decision.get('description', 'No description')}")

                    if decision["action"] == "done":
                        print("\n✅ Task marked complete by AI!")
                        break

                    if self._is_looping(action_history, decision):
                        print("\n⚠️  LOOP DETECTED!")
                        print("   Same action repeated 3+ times — stopping to prevent infinite loop.")
                        print("   Possible causes: missing auth, unclear task, unexpected UI changes.\n")
                        break

                    success = self._execute_action(page, decision)

                    if not success:
                        print("⚠️  Action failed, continuing anyway...\n")
                    else:
                        print("✓ Action executed successfully\n")

                    action_history.append(
                        {
                            "step": step,
                            "action": decision.get("action"),
                            "target": decision.get("target", ""),
                            "text": decision.get("text", ""),
                            "description": decision.get("description", ""),
                        }
                    )

                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass

                    time.sleep(1)

                print("\n" + "=" * 70)
                print("✅ WORKFLOW COMPLETED")
                print("=" * 70)
                print(f"Total steps: {step_count}")
                print(f"Screenshots captured: {len(screenshots)}")
                print("=" * 70 + "\n")

                return {
                    "success": True,
                    "method": "playwright",
                    "app": app_name,
                    "task": task,
                    "starting_url": app_url,
                    "total_steps": step_count,
                    "screenshots": screenshots,
                    "action_history": action_history,
                }

            except Exception as exc:  # noqa: BLE001
                print("\n" + "=" * 70)
                print("❌ ERROR DURING WORKFLOW")
                print("=" * 70)
                print(f"Error: {exc}")
                print("=" * 70 + "\n")

                import traceback

                traceback.print_exc()
                return {
                    "success": False,
                    "method": "playwright",
                    "error": str(exc),
                    "app": app_name,
                    "task": task,
                    "starting_url": app_url,
                    "total_steps": step_count,
                    "screenshots": screenshots,
                    "action_history": action_history,
                }

            finally:
                context.close()
                print("🛑 Browser closed\n")

    def _is_looping(self, history: List[Dict[str, Any]], current: Dict[str, Any]) -> bool:
        if len(history) < 3:
            return False

        recent = history[-3:]
        current_action = current.get("action")
        current_target = current.get("target", "").lower().strip()

        return all(
            entry.get("action") == current_action
            and entry.get("target", "").lower().strip() == current_target
            for entry in recent
        )

    def _execute_action(self, page: Page, decision: Dict[str, Any]) -> bool:
        action = decision.get("action")
        target = decision.get("target", "")
        text = decision.get("text", "")

        try:
            if action == "click":
                return self._execute_click(page, target)
            if action == "type":
                return self._execute_type(page, target, text)
            if action == "navigate":
                page.goto(target, wait_until="networkidle", timeout=30000)
                print(f"   ✓ Navigated to: {target}")
                return True
            if action == "wait":
                duration = int(target) if target.isdigit() else 1000
                page.wait_for_timeout(duration)
                print(f"   ✓ Waited {duration}ms")
                return True

            logger.warning("Unknown action received", extra={"action": action})
            print(f"   ⚠️  Unknown action: {action}")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Action execution exception", extra={"action": action, "target": target, "error": str(exc)})
            print(f"   ✗ Action execution failed: {exc}")
            return False

    def _execute_click(self, page: Page, target: str) -> bool:
        strategies = [
            ("exact text", lambda: page.get_by_text(target, exact=True).first.click(timeout=5000)),
            ("partial text", lambda: page.get_by_text(target).first.click(timeout=5000)),
            ("button with text", lambda: page.locator(f"button:has-text('{target}')").first.click(timeout=5000)),
            (
                "link or button",
                lambda: page.locator(f"a:has-text('{target}'), button:has-text('{target}')").first.click(timeout=5000),
            ),
            ("CSS selector", lambda: page.locator(target).first.click(timeout=5000)),
            ("aria-label", lambda: page.locator(f"[aria-label*='{target}' i]").first.click(timeout=5000)),
            ("role button", lambda: page.get_by_role("button", name=target).first.click(timeout=5000)),
        ]

        for name, strategy in strategies:
            try:
                strategy()
                logger.info("Click success", extra={"strategy": name, "target": target})
                print(f"   ✓ Clicked via {name}: '{target}'")
                return True
            except Exception:
                continue

        logger.warning("Click strategies exhausted", extra={"target": target, "strategies": len(strategies)})
        print(f"   ✗ Could not click '{target}' (tried {len(strategies)} strategies)")
        return False

    def _execute_type(self, page: Page, target: str, text: str) -> bool:
        if not text and "|" in target:
            selector, value = target.split("|", 1)
            target = selector
            text = value

        if not text:
            logger.warning("Type action missing text; defaulting", extra={"target": target})
            text = "Test Project"

        css_like_prefixes = ("#", ".", "[", "input", "textarea", "select", "//")
        is_css_selector = target.startswith(css_like_prefixes)

        slug = slugify(target).replace("_", "-")
        selectors = []
        if is_css_selector:
            selectors.append(target)
        else:
            selectors.extend(
                [
                    f"[placeholder=\"{target}\"]",
                    f"[data-placeholder=\"{target}\"]",
                    f"[aria-label=\"{target}\"]",
                    f"[data-testid*=\"{slug}\"]",
                    f"[name*=\"{slug.replace('-', '')}\"]",
                    f"[id*=\"{slug}\"]",
                ]
            )

        attempts = []
        for sel in selectors:
            attempts.append(("css", sel))

        if not is_css_selector:
            attempts.extend(
                [
                    ("placeholder_api", target),
                    ("role", target),
                    ("label", target),
                ]
            )

        attempts.append(("textbox_any", "input[type='text'], input:not([type]), textarea"))
        attempts.append(("contenteditable", f"[data-placeholder=\"{target}\"][contenteditable='true']"))

        seen = set()
        ordered_attempts = []
        for strat, value in attempts:
            key = (strat, value)
            if key in seen or not value:
                continue
            seen.add(key)
            ordered_attempts.append((strat, value))

        last_error: Exception | None = None
        for strat, value in ordered_attempts:
            try:
                if strat == "css":
                    locator = page.locator(value).first
                elif strat == "placeholder_api":
                    locator = page.get_by_placeholder(value).first
                elif strat == "role":
                    locator = page.get_by_role("textbox", name=value).first
                elif strat == "label":
                    locator = page.get_by_label(value).first
                elif strat == "textbox_any":
                    locator = page.locator(value).first
                elif strat == "contenteditable":
                    locator = page.locator(value).first
                else:
                    continue

                locator.wait_for(state="attached", timeout=8000)
                try:
                    locator.fill(text, timeout=5000)
                except Exception:
                    try:
                        locator.click(timeout=3000)
                    except Exception:
                        pass
                    for combo in ("Meta+A", "Control+A"):
                        try:
                            page.keyboard.press(combo)
                            break
                        except Exception:
                            continue
                    page.keyboard.type(text, delay=40)

                logger.info(
                    "Type success",
                    extra={"strategy": strat, "target": target, "selector": value, "value": text},
                )
                print(f"   ✓ Typed '{text}' using {strat} locator")
                return True
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        logger.error(
            "Type action failed",
            extra={"target": target, "error": str(last_error) if last_error else None},
        )
        print(f"   ✗ Could not type: {last_error}")
        return False

    def _ask_claude(
        self,
        screenshot: str,
        task: str,
        current_url: str,
        step: int,
        action_history: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        response = self.anthropic.messages.create(
            model=Config.ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot,
                            },
                        },
                        {
                            "type": "text",
                            "text": self._build_prompt(task, current_url, step, action_history),
                        },
                    ],
                }
            ],
        )

        text = response.content[0].text
        return self._parse_decision(text)

    def _build_prompt(
        self,
        task: str,
        current_url: str,
        step: int,
        action_history: List[Dict[str, Any]] | None = None,
    ) -> str:
        history_text = ""
        if action_history:
            recent = action_history[-3:]
            if recent:
                history_text = "\n\n⚠️  ACTIONS ALREADY TAKEN (do NOT repeat unless necessary):\n"
                for idx, act in enumerate(recent, start=1):
                    action_desc = act.get("action", "")
                    target = act.get("target", "")
                    if target:
                        action_desc += f" → {target[:50]}"
                    text = act.get("text")
                    if text:
                        action_desc += f" (text: {text[:30]})"
                    history_text += f"  {idx}. {action_desc}\n"
                history_text += (
                    "\n🚫 CRITICAL: If you just TYPED in a field, your next action"
                    " should be CLICK the submit/next button!"
                    "\n🚫 DO NOT type the same thing into the same field multiple times!\n"
                )

        return f"""TASK TO ACCOMPLISH: {task}

CURRENT STATE:
- URL: {current_url}
- Step: {step}
{history_text}

INSTRUCTIONS:
Analyze the screenshot and decide the SINGLE next action to progress toward completing the task.

🔴 CRITICAL RULES:
1. Respond with ONLY valid JSON - no prose, no explanations, no markdown
2. If you see a login page, mark as "done" - we can't proceed without auth
3. If you just typed something, CLICK the submit/next button (don't type again!)
4. Only mark "done" when you see confirmation that the task succeeded
5. Use visible button text for clicks (e.g., "Create Project", "Next", "Submit")
6. When typing, always provide & enter a sensible placeholder value (e.g., "Test Project", "Demo") so the workflow can progress.

VALID ACTIONS:
- click: Click a button, link, or element (use visible text)
- type: Enter text into an input field (provide both target AND text)
- navigate: Go to a different URL
- wait: Wait for something (provide milliseconds)
- done: Task is complete (only when you see success confirmation!)

RESPONSE FORMAT (JSON only, no other text):
{{
    "action": "click|type|navigate|wait|done",
    "target": "visible button text or CSS selector",
    "text": "text to type (only for type action)",
    "description": "brief description of what this accomplishes"
}}

EXAMPLES:
✅ Good click: {{"action": "click", "target": "Create Project", "description": "..."}}
✅ Good type: {{"action": "type", "target": "input[name='title']", "text": "Test Project", "description": "..."}}
❌ Bad: Responding with prose instead of JSON
❌ Bad: Typing same field repeatedly
❌ Bad: Not clicking submit after typing

RESPOND WITH ONLY THE JSON (no markdown)."""

    def _parse_decision(self, text: str) -> Dict[str, Any]:
        text = text.strip()

        json_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        try:
            if "```json" in text:
                json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in text:
                json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
            else:
                json_str = text
            decision = json.loads(json_str)
        except Exception as exc:  # noqa: BLE001
            logger.error("Claude JSON parse error", extra={"error": str(exc), "raw": text[:200]})
            print(f"⚠️  JSON parse error: {exc}")
            print(f"   Raw response: {text[:200]}...")
            text_lower = text.lower()
            if any(word in text_lower for word in ["done", "complete", "success"]):
                decision = {"action": "done", "description": "Inferred completion from response"}
            elif any(word in text_lower for word in ["login", "sign in", "authenticate"]):
                decision = {"action": "done", "description": "Login required - stopping"}
            elif "click" in text_lower and "next" in text_lower:
                decision = {"action": "click", "target": "Next", "description": "Inferred from response"}
            elif "click" in text_lower and "submit" in text_lower:
                decision = {"action": "click", "target": "Submit", "description": "Inferred from response"}
            else:
                decision = {"action": "done", "description": "Parse error - stopping workflow"}

        decision.setdefault("action", "done")
        decision.setdefault("target", "")
        decision.setdefault("text", "")
        decision.setdefault("description", "Next step")
        return decision


__all__ = ["PlaywrightCapture"]
