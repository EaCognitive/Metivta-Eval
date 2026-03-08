"""Remote web validation for cited URLs using Browserless or direct HTTP fetches."""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langsmith.schemas import Example, Run

load_dotenv(override=True)
if not os.getenv("BROWSERLESS_TOKEN"):
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

_MAX_URLS = 5
_BROWSER_TIMEOUT = 30
_HTTP_TIMEOUT = 8
_URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+(?:[/?#][^\s<>"{}|\\^`\[\]]*)?')
_HEBREW_PATTERN = re.compile(r"[\u0590-\u05FF]+")
_TEXT_CLEAN_PATTERN = re.compile(r"[^\w\s\u0590-\u05FF]")
_URL_CLEAN_PATTERN = re.compile(r"https?://[^\s]+")
_USER_AGENT = {"User-Agent": "Mozilla/5.0"}
_BROWSERLESS_ENDPOINT = "https://production-sfo.browserless.io/content"


@dataclass(frozen=True, slots=True)
class ValidationTerms:
    """Normalized answer tokens used for URL relevance checks."""

    answer_words: set[str]
    hebrew_words: set[str]


@dataclass(frozen=True, slots=True)
class ValidationAttempt:
    """Result of validating a single cited URL."""

    url: str
    valid: bool


class RemoteWebValidator:
    """Validate citation URLs against the answer text."""

    def __init__(self) -> None:
        self.browser_url = os.getenv("BROWSERLESS_URL", _BROWSERLESS_ENDPOINT)
        self.browser_token = os.getenv("BROWSERLESS_TOKEN", "")
        self.__name__ = "web_validation_evaluator"

    def validate_url(self, url: str, terms: ValidationTerms) -> bool:
        """Validate one URL with Browserless first and HTTP fallback second."""
        if self.browser_token and _validate_with_browserless(url, terms, self.browser_token):
            return True
        return _validate_with_http(url, terms)

    def evaluate_run(self, run: Run, example: Example | None = None) -> dict[str, Any]:
        """Check whether answer citations are live and content-relevant."""
        del example
        answer = str((run.outputs or {}).get("answer", ""))
        urls = _extract_urls(answer)
        if not urls:
            return {"key": "web_validation", "score": 1.0, "comment": "No URLs to validate"}

        if not self.browser_token:
            return _http_only_result(urls)

        terms = _extract_validation_terms(answer)
        attempts = [ValidationAttempt(url=url, valid=self.validate_url(url, terms)) for url in urls]
        valid_count = sum(1 for attempt in attempts if attempt.valid)
        score = valid_count / len(attempts)
        failed_urls = [attempt.url for attempt in attempts if not attempt.valid]
        comment = _build_comment(valid_count, len(attempts), failed_urls)
        return {"key": "web_validation", "score": score, "comment": comment}


def _extract_urls(answer: str) -> list[str]:
    """Extract up to the configured maximum number of citation URLs."""
    return _URL_PATTERN.findall(answer)[:_MAX_URLS]


def _extract_validation_terms(answer: str) -> ValidationTerms:
    """Build normalized word sets from the answer text."""
    answer_text = _URL_CLEAN_PATTERN.sub("", answer)
    answer_text = _TEXT_CLEAN_PATTERN.sub(" ", answer_text)
    answer_words = {word for word in answer_text.split() if len(word) > 1}
    hebrew_words = set(_HEBREW_PATTERN.findall(answer))
    return ValidationTerms(answer_words=answer_words, hebrew_words=hebrew_words)


def _http_only_result(urls: list[str]) -> dict[str, Any]:
    """Fallback validation when Browserless is not configured."""
    valid_count = 0
    for url in urls:
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code < 400:
            valid_count += 1

    checked = len(urls)
    score = valid_count / checked if checked else 0.0
    return {
        "key": "web_validation",
        "score": score,
        "comment": f"HTTP validation: {valid_count}/{checked} URLs valid",
    }


def _validate_with_browserless(url: str, terms: ValidationTerms, browser_token: str) -> bool:
    """Use Browserless-rendered content to validate a citation."""
    browserless_url = f"{_BROWSERLESS_ENDPOINT}?token={browser_token}"
    try:
        response = requests.post(
            browserless_url,
            json={"url": url},
            headers={"Content-Type": "application/json"},
            timeout=_BROWSER_TIMEOUT,
        )
    except requests.RequestException:
        return False

    if response.status_code != 200:
        return False
    return _content_supports_answer(
        response.text,
        terms,
        short_ratio=0.15,
        long_ratio=0.10,
    )


def _validate_with_http(url: str, terms: ValidationTerms) -> bool:
    """Fetch a URL directly and validate whether its content supports the answer."""
    try:
        response = requests.get(
            url,
            timeout=_HTTP_TIMEOUT,
            allow_redirects=True,
            headers=_USER_AGENT,
        )
    except requests.RequestException:
        return False

    if response.status_code >= 400:
        return False
    return _content_supports_answer(
        response.text,
        terms,
        short_ratio=0.20,
        long_ratio=0.15,
    )


def _content_supports_answer(
    content: str,
    terms: ValidationTerms,
    *,
    short_ratio: float,
    long_ratio: float,
) -> bool:
    """Return whether the fetched content materially overlaps with the answer."""
    url_text = _extract_text(content)
    if not url_text:
        return False

    if any(word in url_text for word in terms.hebrew_words):
        return True

    matching_words = sum(1 for word in terms.answer_words if word in url_text)
    threshold = _matching_threshold(
        len(terms.answer_words),
        short_ratio=short_ratio,
        long_ratio=long_ratio,
    )
    return matching_words >= threshold


def _extract_text(content: str) -> str:
    """Strip markup and normalize whitespace for a fetched page."""
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    extracted = soup.get_text(" ")
    return " ".join(html.unescape(extracted).split())


def _matching_threshold(
    total_words: int,
    *,
    short_ratio: float,
    long_ratio: float,
) -> float:
    """Compute the minimum keyword overlap needed to treat content as supporting."""
    if total_words < 10:
        return max(2, total_words * short_ratio)
    return max(3, total_words * long_ratio)


def _build_comment(valid_count: int, total_checked: int, failed_urls: list[str]) -> str:
    """Build the evaluator comment string."""
    if failed_urls:
        return f"Web validation: {valid_count}/{total_checked} URLs valid (some used HTTP fallback)"
    return f"Web validation: {valid_count}/{total_checked} URLs valid"


def web_validation_evaluator(run: Run, example: Example) -> dict[str, Any]:
    """Adapter used by the evaluator registry."""
    validator = RemoteWebValidator()
    return validator.evaluate_run(run, example)


METIVTA_WEB_VALIDATORS = {"web_validation": web_validation_evaluator}
