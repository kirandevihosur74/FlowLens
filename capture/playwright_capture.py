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
        """Drives the browser through the requested task, keeping screenshots and stopping if the run gets stuck."""

        max_steps = max_steps or Config.MAX_STEPS

        separator = "=" * 70
        logger.info("")
        logger.info(separator)
        logger.info("STARTING WORKFLOW CAPTURE")
        logger.info(separator)
        logger.info("Task: %s", task)
        logger.info("App: %s", app_name)
        logger.info("URL: %s", app_url)
        logger.info("%s", separator)
        logger.info("")

        screenshots: List[Dict[str, Any]] = []
        action_history: List[Dict[str, Any]] = []
        step_count = 0
        successful_actions = 0
        workflow_completed = False
        failure_reason = ""

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
                    args=["--start-maximized", "--start-fullscreen", "--window-position=0,0", "--window-size=1920,1200"],
                    viewport={"width": 1920, "height": 1080},
                )
            except Exception:
                logger.warning("Falling back to bundled Chromium", extra={"profile": str(profile_dir)})
                logger.info("WARNING: Could not launch Chrome channel; falling back to bundled Chromium.")
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    args=["--start-maximized", "--start-fullscreen", "--window-position=0,0", "--window-size=1920,1200"],
                    viewport={"width": 1920, "height": 1080},
                )

            if any(profile_dir.iterdir()):
                logger.info("Using persisted Chrome profile", extra={"profile": str(profile_dir)})
                logger.info("Using persisted Chrome profile for %s", profile_name)
                logger.info("")
            else:
                logger.warning("No saved auth profile found", extra={"profile": str(profile_dir)})
                logger.info("WARNING: No saved auth profile found. Browser will open for manual login.")
                logger.info("   Run: python scripts/setup_auth.py for best results.")
                logger.info("")

            pages = context.pages
            page = pages[0] if pages else context.new_page()

            try:
                logger.info("Navigating", extra={"url": app_url})
                logger.info("Navigating to: %s", app_url)
                page.goto(app_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
                logger.info("Page loaded")
                logger.info("")

                for step in range(1, max_steps + 1):
                    step_count = step
                    logger.info("%s", "─" * 70)
                    logger.info("Step %d/%d", step, max_steps)
                    logger.info("%s", "─" * 70)

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

                    logger.info("Action: %s", decision["action"])
                    logger.info("Notes: %s", decision.get("description", "No description"))

                    if decision["action"] == "done":
                        if successful_actions < Config.MIN_SUCCESSFUL_ACTIONS:
                            logger.info("")
                            logger.info(
                                "WARNING: Not enough confirmed actions yet. "
                                "Need at least %s, currently have %s.",
                                Config.MIN_SUCCESSFUL_ACTIONS,
                                successful_actions,
                            )
                            action_history.append(
                                {
                                    "step": step,
                                    "action": "done",
                                    "target": "",
                                    "text": "",
                                    "description": (
                                        "Attempted to mark done before completing the required number of actions."
                                    ),
                                    "status": "rejected",
                                }
                            )
                            continue

                        logger.info("")
                        logger.info("Task marked complete by AI!")
                        workflow_completed = True
                        break

                    if self._is_looping(action_history, decision):
                        logger.info("")
                        logger.info("WARNING: LOOP DETECTED!")
                        logger.info("   Same action repeated 3+ times — stopping to prevent infinite loop.")
                        logger.info("   Possible causes: missing auth, unclear task, unexpected UI changes.")
                        logger.info("")
                        failure_reason = "loop_detected"
                        break

                    success = self._execute_action(page, decision)

                    if not success:
                        logger.info("WARNING: Action failed, continuing anyway...")
                        logger.info("")
                        if not failure_reason:
                            failure_reason = "action_failed"
                    else:
                        logger.info("Action executed successfully")
                        logger.info("")
                        successful_actions += 1

                    action_history.append(
                        {
                            "step": step,
                            "action": decision.get("action"),
                            "target": decision.get("target", ""),
                            "text": decision.get("text", ""),
                            "description": decision.get("description", ""),
                            "status": "success" if success else "failed",
                        }
                    )

                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass

                    time.sleep(1)

                if not workflow_completed and not failure_reason:
                    failure_reason = "max_steps_reached"
                if successful_actions == 0 and not failure_reason:
                    failure_reason = "no_actions_executed"

                if not workflow_completed or successful_actions == 0:
                    if failure_reason == "no_actions_executed":
                        error_message = "No actions were executed before the workflow ended. Claude likely marked the task complete prematurely."
                    elif failure_reason == "loop_detected":
                        error_message = "Workflow stopped because Claude repeated the same action three times in a row."
                    elif failure_reason == "action_failed":
                        error_message = "A critical action failed and the workflow could not recover."
                    elif failure_reason == "max_steps_reached":
                        error_message = "Maximum step limit reached without confirming the task was finished."
                    else:
                        error_message = "Workflow ended without confirmation of success."

                    logger.info("")
                    logger.info(separator)
                    logger.info("WORKFLOW INCOMPLETE")
                    logger.info(separator)
                    logger.info("%s", error_message)
                    logger.info("")

                    return {
                        "success": False,
                        "error": error_message,
                        "reason": failure_reason,
                        "method": "playwright",
                        "app": app_name,
                        "task": task,
                        "starting_url": app_url,
                        "total_steps": step_count,
                        "screenshots": screenshots,
                        "action_history": action_history,
                        "successful_actions": successful_actions,
                    }

                logger.info("")
                logger.info(separator)
                logger.info("WORKFLOW COMPLETED")
                logger.info(separator)
                logger.info("Total steps: %d", step_count)
                logger.info("Screenshots captured: %d", len(screenshots))
                logger.info("%s", separator)
                logger.info("")

                return {
                    "success": True,
                    "method": "playwright",
                    "app": app_name,
                    "task": task,
                    "starting_url": app_url,
                    "total_steps": step_count,
                    "screenshots": screenshots,
                    "action_history": action_history,
                    "successful_actions": successful_actions,
                    "reason": "completed",
                }

            except Exception as exc:  # noqa: BLE001
                logger.info("")
                logger.info(separator)
                logger.info("ERROR DURING WORKFLOW")
                logger.info(separator)
                logger.error("Error: %s", exc, exc_info=True)
                logger.info("%s", separator)
                logger.info("")

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
                logger.info("Browser closed")
                logger.info("")

    def _is_looping(self, history: List[Dict[str, Any]], current: Dict[str, Any]) -> bool:
        """Checks if Claude is repeating the same move so we can bail out before wasting more steps."""
        if len(history) < 3:
            return False

        recent = history[-3:]
        current_action = current.get("action")
        current_target = current.get("target", "").lower().strip()

        same_action = all(
            entry.get("action") == current_action
            and entry.get("target", "").lower().strip() == current_target
            for entry in recent
        )
        if not same_action:
            return False

        all_succeeded = all(entry.get("status") == "success" for entry in recent)
        if all_succeeded:
            logger.info("   WARNING: Repeating successful actions without visible change")
            return True

        return True

    def _execute_action(self, page: Page, decision: Dict[str, Any]) -> bool:
        """Translates Claude's chosen action into real browser movements and reports whether it landed."""
        action = decision.get("action")
        target = decision.get("target", "")
        text = decision.get("text", "")

        previous_url = page.url

        try:
            if action == "click":
                success = self._execute_click(page, decision)
                if success:
                    self._wait_for_state_change(page, previous_url, timeout_ms=2000)
                return success
            if action == "type":
                return self._execute_type(page, target, text)
            if action == "navigate":
                page.goto(target, wait_until="networkidle", timeout=60000)
                logger.info("   Navigated to: %s", target)
                return True
            if action == "wait":
                duration = int(target) if target.isdigit() else 1000
                page.wait_for_timeout(duration)
                logger.info("   Waited %sms", duration)
                return True

            logger.warning("Unknown action received", extra={"action": action})
            logger.info("   WARNING: Unknown action: %s", action)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Action execution exception", extra={"action": action, "target": target, "error": str(exc)})
            logger.info("   Action execution failed: %s", exc)
            return False

    def _execute_click(self, page: Page, decision: Dict[str, Any]) -> bool:
        """Throws every click strategy we have at the target until something works."""
        target = (decision.get("target") or "").strip()
        description = decision.get("description", "")
        location_hint = decision.get("location") or {}

        if target:
            logger.info("   Target requested: '%s'", target)

        exact_strategies: list[tuple[str, callable]] = []
        if target:
            exact_strategies = [
                ("exact text", lambda: page.get_by_text(target, exact=True).first.click(timeout=3000)),
                ("exact aria-label", lambda: page.locator(f"[aria-label=\"{target}\"]").first.click(timeout=3000)),
                ("exact button text", lambda: page.locator(f"button:has-text('{target}')").first.click(timeout=3000)),
            ]

        for name, strategy in exact_strategies:
            try:
                strategy()
                logger.info("Click success", extra={"strategy": name, "target": target})
                logger.info("   Clicked via %s", name)
                return True
            except Exception:
                continue

        combined_text = " ".join(filter(None, [target, description]))
        keywords = self._extract_keywords(combined_text)
        logger.debug("Derived keywords for click: %s", keywords[:5])

        try:
            clickables = page.locator(
                "button:visible, [role='button']:visible, a:visible, [onclick]:visible"
            ).all()

            scored_matches: list[tuple[int, Any, str]] = []
            for element in clickables:
                try:
                    aria_label = element.get_attribute("aria-label") or ""
                    text_content = element.inner_text() or ""
                    title_attr = element.get_attribute("title") or ""
                    combined = " ".join(filter(None, [aria_label, text_content, title_attr]))
                    if not combined:
                        continue
                    score = self._score_element_match(combined, keywords)
                    if score > 0:
                        scored_matches.append((score, element, combined))
                except Exception:
                    continue

            if scored_matches:
                scored_matches.sort(key=lambda item: item[0], reverse=True)
                top_score, top_element, top_text = scored_matches[0]
                logger.debug("Top semantic match score=%s text='%s'", top_score, top_text[:80])
                if top_score >= 50:
                    top_element.click(timeout=3000)
                    logger.info(
                        "Click success",
                        extra={"strategy": "semantic match", "target": target, "score": top_score},
                    )
                    logger.info("   Clicked semantic match: '%s'", top_text[:80])
                    return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Semantic click matching failed: %s", exc)

        if location_hint:
            try:
                candidates = page.locator("button, [role='button'], [aria-role='button'], a").all()
                viewport = page.viewport_size or {}
                spatial_match = self._find_best_spatial_match(candidates, location_hint, viewport)
                if spatial_match:
                    spatial_match.click(timeout=3000)
                    logger.info(
                        "Click success",
                        extra={"strategy": "spatial match", "target": target, "location_hint": location_hint},
                    )
                    logger.info("   Clicked via spatial matching")
                    return True
            except Exception as exc:  # noqa: BLE001
                logger.debug("Spatial click attempt failed: %s", exc)

        for keyword in keywords[:3]:
            for strategy_name, selector_builder in (
                (f"aria-label contains '{keyword}'", lambda k=keyword: f"[aria-label*=\"{k}\" i]"),
                (f"text contains '{keyword}'", lambda k=keyword: k),
            ):
                try:
                    if strategy_name.startswith("aria-label"):
                        page.locator(selector_builder()).first.click(timeout=3000)
                    else:
                        page.get_by_text(selector_builder(), exact=False).first.click(timeout=3000)
                    logger.info(
                        "Click success",
                        extra={"strategy": strategy_name, "target": target, "keyword": keyword},
                    )
                    logger.info("   Clicked via %s", strategy_name)
                    return True
                except Exception:
                    continue

        fallback_strategies: list[tuple[str, callable]] = []
        if target:
            fallback_strategies = [
                ("partial text", lambda: page.get_by_text(target).first.click(timeout=5000)),
                (
                    "link or button",
                    lambda: page.locator(f"a:has-text('{target}'), button:has-text('{target}')").first.click(timeout=5000),
                ),
                ("CSS selector", lambda: page.locator(target).first.click(timeout=5000)),
                ("aria-label", lambda: page.locator(f"[aria-label*='{target}' i]").first.click(timeout=5000)),
                ("role button", lambda: page.get_by_role("button", name=target).first.click(timeout=5000)),
            ]

        for name, action in fallback_strategies:
            try:
                action()
                logger.info("Click success", extra={"strategy": name, "target": target})
                logger.info("   Clicked via %s: '%s'", name, target)
                return True
            except Exception:
                continue

        logger.warning(
            "Click strategies exhausted",
            extra={"target": target, "location_hint": location_hint, "keywords": keywords[:5]},
        )
        logger.info("   Could not click '%s'", target or description)
        return False

    def _extract_keywords(self, text: str) -> List[str]:
        """Picks out the juicy words Claude mentioned so we can match them to UI elements."""
        if not text:
            return []

        text = text.lower()
        words = text.split()

        stopwords = {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "button",
            "icon",
            "click",
            "menu",
            "section",
            "page",
        }

        keywords: list[str] = []

        for size in (3, 2):
            if len(words) < size:
                continue
            for idx in range(len(words) - size + 1):
                chunk = words[idx : idx + size]
                if all(word not in stopwords for word in chunk):
                    keywords.append(" ".join(chunk))

        individual_words = [
            word for word in words if word not in stopwords and len(word) > 2
        ]
        individual_words.sort(key=len, reverse=True)
        keywords.extend(individual_words)

        seen: set[str] = set()
        ordered_keywords: list[str] = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                ordered_keywords.append(keyword)

        return ordered_keywords

    def _score_element_match(self, element_text: str, keywords: List[str]) -> int:
        """Gives a rough relevance score so we can choose the click target that feels most on-topic."""
        element_text = element_text.lower()
        score = 0

        for keyword in keywords:
            if keyword in element_text:
                word_count = len(keyword.split())
                if word_count >= 3:
                    score += 100
                elif word_count == 2:
                    score += 50
                else:
                    score += 10

                if keyword == element_text.strip():
                    score += 200

        return score

    def _find_best_spatial_match(
        self,
        elements: List[Any],
        location_hint: Dict[str, Any],
        viewport: Dict[str, int] | None,
    ) -> Any:
        """Uses Claude's rough location hint (top, bottom, etc.) to guess which element they meant."""
        if not elements or not viewport:
            return None

        position_hint = (location_hint.get("position") or "").lower()
        if not position_hint:
            return None

        width = viewport.get("width") or 0
        height = viewport.get("height") or 0
        if not width or not height:
            return None

        scored: List[tuple[int, Any]] = []

        for element in elements:
            try:
                box = element.bounding_box()
            except Exception:  # noqa: BLE001
                continue

            if not box:
                continue

            score = 0
            if "top" in position_hint and box["y"] <= height * 0.2:
                score += 10
            if "bottom" in position_hint and box["y"] >= height * 0.7:
                score += 10
            if "left" in position_hint and box["x"] <= width * 0.3:
                score += 10
            if "right" in position_hint and box["x"] >= width * 0.7:
                score += 10
            if "center" in position_hint and width * 0.3 < box["x"] < width * 0.7:
                score += 5
            if "toolbar" in position_hint and box["y"] <= 100:
                score += 15

            if score > 0:
                scored.append((score, element))

        if not scored:
            return None

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _wait_for_state_change(self, page: Page, previous_url: str, timeout_ms: int = 2000) -> bool:
        """Gives the page a moment to react after an action so we can detect when something actually changed."""
        timeout_s = timeout_ms / 1000
        start = time.time()
        while time.time() - start < timeout_s:
            if page.url != previous_url:
                logger.info("   URL changed to: %s", page.url)
                return True
            time.sleep(0.1)

        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            logger.info("   Page activity detected after action")
            return True
        except Exception:
            pass

        page.wait_for_timeout(300)
        return False

    def _execute_type(self, page: Page, target: str, text: str) -> bool:
        """Finds the best input field candidate and types in the text, falling back to keyboard events if needed."""
        if not text and "|" in target:
            selector, value = target.split("|", 1)
            target = selector
            text = value

        if not text:
            logger.warning("Type action missing text; defaulting", extra={"target": target})
            text = "Test Project"

        generic_keywords = {
            "input",
            "textarea",
            "text field",
            "field",
            "text box",
            "textbox",
            "text input",
            "name",
            "title",
            "description",
        }
        target_normalized = target.lower().strip()
        is_generic = target_normalized in generic_keywords

        css_like_prefixes = ("#", ".", "[", "input", "textarea", "select", "//", "div")
        is_css_selector = any(target.startswith(prefix) for prefix in css_like_prefixes)

        attempts: list[tuple[str, str | None]] = []

        if is_generic:
            attempts.extend(
                [
                    ("first visible input", "input[type='text']:visible, input:not([type]):visible"),
                    ("first visible textarea", "textarea:visible"),
                    ("first contenteditable", "[contenteditable='true']:visible"),
                    ("any input", "input[type='text'], input:not([type])"),
                    ("any textarea", "textarea"),
                    ("any contenteditable", "[contenteditable='true']"),
                    ("role textbox", None),
                ]
            )
        elif is_css_selector:
            attempts.append(("css selector", target))
        else:
            slug = slugify(target).replace("_", "-")
            attempts.extend(
                [
                    ("placeholder", f"[placeholder=\"{target}\"]"),
                    ("data-placeholder", f"[data-placeholder=\"{target}\"]"),
                    ("aria-label", f"[aria-label=\"{target}\"]"),
                    ("aria-label partial", f"[aria-label*=\"{target}\" i]"),
                    ("data-testid", f"[data-testid*=\"{slug}\"]"),
                    ("name attribute", f"[name*=\"{slug.replace('-', '')}\"]"),
                    ("id attribute", f"[id*=\"{slug}\"]"),
                    ("label text", None),
                ]
            )

        attempts.extend(
            [
                ("any visible input", "input:visible, textarea:visible, [contenteditable='true']:visible"),
                ("first input or textarea", "input[type='text'], input:not([type]), textarea"),
                ("contenteditable with placeholder", "[contenteditable='true'][placeholder]"),
                ("any contenteditable", "[contenteditable='true']"),
            ]
        )

        seen: set[tuple[str, str | None]] = set()
        ordered_attempts: list[tuple[str, str | None]] = []
        for strategy_name, selector in attempts:
            key = (strategy_name, selector)
            if key in seen:
                continue
            seen.add(key)
            ordered_attempts.append((strategy_name, selector))

        last_error: Exception | None = None

        for strategy_name, selector in ordered_attempts:
            try:
                if strategy_name == "role textbox":
                    locator = page.get_by_role("textbox").first
                elif strategy_name == "label text":
                    locator = page.get_by_label(target).first
                elif selector:
                    locator = page.locator(selector).first
                else:
                    continue

                locator.wait_for(state="attached", timeout=5000)

                try:
                    locator.fill(text, timeout=3000)
                    logger.info(
                        "Type success",
                        extra={
                            "strategy": strategy_name,
                            "target": target,
                            "selector": selector,
                            "value": text,
                        },
                    )
                    logger.info("   Typed '%s' using %s", text, strategy_name)
                    return True
                except Exception:
                    try:
                        locator.click(timeout=2000)
                    except Exception:
                        pass

                    for combo in ("Meta+A", "Control+A"):
                        try:
                            page.keyboard.press(combo)
                            break
                        except Exception:
                            continue

                    page.keyboard.type(text, delay=50)
                    logger.info(
                        "Type success (keyboard fallback)",
                        extra={
                            "strategy": strategy_name,
                            "target": target,
                            "selector": selector,
                            "value": text,
                        },
                    )
                    logger.info("   Typed '%s' using %s (keyboard fallback)", text, strategy_name)
                    return True
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        logger.error(
            "Type action failed - all strategies exhausted",
            extra={
                "target": target,
                "text": text,
                "strategies_tried": len(ordered_attempts),
                "error": str(last_error) if last_error else None,
            },
        )
        logger.info("   Could not type '%s' into '%s'", text, target)
        logger.info("   Tried %d strategies", len(ordered_attempts))
        if last_error:
            logger.info("   Last error: %s", last_error)

        return False

    def _ask_claude(
        self,
        screenshot: str,
        task: str,
        current_url: str,
        step: int,
        action_history: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Sends the latest screenshot and context to Claude and returns whatever action it wants to try next."""
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
        """Build improved prompt with better typing guidance."""

        history_text = ""
        if action_history:
            recent = action_history[-3:]
            if recent:
                lines = ["", "WARNING: ACTIONS ALREADY TAKEN (do NOT repeat unless necessary):"]
                for idx, act in enumerate(recent, start=1):
                    action_desc = act.get("action", "")
                    target = act.get("target", "")
                    if target:
                        action_desc += f" → {target[:50]}"
                    text_value = act.get("text")
                    if text_value:
                        action_desc += f" (text: {text_value[:30]})"
                    lines.append(f"  {idx}. {action_desc}")
                lines.extend(
                    [
                        "",
                        "CRITICAL: If you just TYPED in a field, your next action should be CLICK the submit/next button!",
                        "DO NOT type the same thing into the same field multiple times!",
                    ]
                )
                history_text = "\n".join(lines)

        prompt = f"""TASK TO ACCOMPLISH: {task}

CURRENT STATE:
- URL: {current_url}
- Step: {step}
{history_text}

INSTRUCTIONS:
Analyze the screenshot carefully and decide the SINGLE next action.

CRITICAL RULES:
1. Respond with ONLY valid JSON - no prose, no explanations, no markdown
2. Be SPECIFIC with your target description (button text + context/location)
3. If you just clicked something, confirm the UI changed before clicking again
4. Only mark \"done\" when you see clear confirmation the task succeeded
5. Do NOT mark \"done\" until you have completed at least {Config.MIN_SUCCESSFUL_ACTIONS} successful actions (clicks, typing, or navigation)

GUIDANCE FOR CLICKING:
- Use the full button text when possible: \"Create new project\", \"Submit\", \"Save\"
- For icon buttons, describe the function and location (e.g., \"filter button in top toolbar\")
- Include a \"location\" hint when needed: {{"position\": \"top right toolbar\"}}
- Avoid vague targets like \"new\" or \"button\" — be descriptive

GUIDANCE FOR TYPING (IMPORTANT!):
- Prefer selectors that point to interactive elements:
  • \"input\" or \"textarea\" for standard text controls
  • \"[contenteditable='true']\" for rich-text editors (Linear, Notion, etc.)
  • \"[placeholder='Project name']\" when the placeholder text is visible
- Do NOT use label text alone as the selector (e.g., not \"Project name\")
- ALWAYS provide the actual text to type (e.g., \"Test Project\", \"Demo Task\", \"Sample Name\")
- After typing, your next action should be clicking the submit button

VALID ACTIONS:
- click: Click a button, link, or element
- type: Enter text into an input field
- navigate: Go to a different URL
- wait: Wait for page load (provide milliseconds)
- done: Task is complete (only when you see success)

RESPONSE FORMAT (JSON only, no markdown, no extra text):
{{
    \"action\": \"click|type|navigate|wait|done\",
    \"target\": \"describe the element precisely\",
    \"text\": \"actual text to type (REQUIRED for type actions!)\",
    \"description\": \"brief description of why this action helps\",
    \"location\": {{\"position\": \"top right toolbar\"}}  // optional hint that helps locate the element
}}

GOOD EXAMPLES:
{{\"action\": \"click\", \"target\": \"create new project button\", \"description\": \"Open project creation form\"}}
{{\"action\": \"click\", \"target\": \"settings icon\", \"description\": \"Open board settings\", \"location\": {{\"position\": \"top right toolbar\"}}}}
{{\"action\": \"type\", \"target\": \"[contenteditable='true']\", \"text\": \"Test Project\", \"description\": \"Fill project name\"}}
{{\"action\": \"click\", \"target\": \"submit button in project modal\", \"description\": \"Create the project\"}}
{{\"action\": \"done\", \"description\": \"Project created successfully\"}}

BAD EXAMPLES:
{{\"action\": \"click\", \"target\": \"new\", \"description\": \"Click new\"}}  // too vague
{{\"action\": \"type\", \"target\": \"Project name\", \"text\": \"Test\"}}  // label text is not a selector
{{\"action\": \"click\", \"target\": \"#btn-123\"}}  // avoid internal CSS IDs

RESPOND WITH ONLY THE JSON:"""

        return prompt

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
            logger.info("WARNING: JSON parse error: %s", exc)
            logger.info("   Raw response: %s...", text[:200])
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
        decision.setdefault("location", {})
        return decision


__all__ = ["PlaywrightCapture"]
