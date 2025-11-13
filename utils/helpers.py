"""Helper utilities."""

import re
from urllib.parse import urlparse
from typing import Optional



def extract_app_name(url: str) -> str:
    """Pulls the likely app name from a URL, stripping www/app prefixes so we get 'linear' style names."""

    domain = urlparse(url).netloc
    domain = domain.replace("www.", "").replace("app.", "")
    name = domain.split(".")[0]
    return name or "unknown"


def slugify(text: str) -> str:
    """Turns free-form text into a filesystem-friendly slug we can use for folders and filenames."""

    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:50]


def detect_app_from_task(task: str, known_apps: dict) -> Optional[str]:
    """Looks inside the natural-language task for mentions of apps we know about and returns the best match."""

    if not task:
        return None

    task_lower = task.lower()

    # Pattern 1: exact app name matches (word boundaries)
    for app_name in known_apps.keys():
        pattern = r'\b' + re.escape(app_name.lower()) + r'\b'
        if re.search(pattern, task_lower):
            return app_name

    # Pattern 2: common variations / domains
    app_variations = {
        'linear': [r'\blinear\b', r'\blinear\.app\b'],
        'notion': [r'\bnotion\b', r'\bnotion\.so\b'],
        'asana': [r'\basana\b', r'\basana\.com\b'],
    }

    for app_name, patterns in app_variations.items():
        if app_name in known_apps:
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    return app_name

    return None
