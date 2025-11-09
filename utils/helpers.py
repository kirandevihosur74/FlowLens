"""Helper utilities."""

import re
from urllib.parse import urlparse


def extract_app_name(url: str) -> str:
    """Extract the app name from a URL."""

    domain = urlparse(url).netloc
    domain = domain.replace("www.", "").replace("app.", "")
    name = domain.split(".")[0]
    return name or "unknown"


def slugify(text: str) -> str:
    """Convert text to a slug."""

    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:50]
