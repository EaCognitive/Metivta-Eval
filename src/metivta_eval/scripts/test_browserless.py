#!/usr/bin/env python3
"""Manual Browserless smoke script for debugging rendered citation content."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

TEST_URL = "https://www.sefaria.org/Shabbat.31a?lang=bi"
TEST_ANSWER = "The Talmud in Shabbat 31a discusses Hillel's response to the convert"
CONTENT_OUTPUT = Path("browserless_raw_response.html")
TEXT_OUTPUT = Path("browserless_extracted_text.txt")
SCRAPE_OUTPUT = Path("browserless_scrape_response.json")


def test_browserless_content_api() -> None:
    """Test the Browserless content endpoint with one rendered page."""
    token = _load_browserless_token()
    if token is None:
        return

    print(f"\n📍 Testing URL: {TEST_URL}")
    print(f"📝 Test answer: {TEST_ANSWER}")
    print("\n🔄 Calling Browserless.io content API...")

    response = _post_json(
        f"https://production-sfo.browserless.io/content?token={token}",
        payload={"url": TEST_URL},
    )
    if response is None:
        return

    print(f"📊 Response status: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ API error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return

    raw_content = response.text
    print(f"📏 Raw content length: {len(raw_content)} characters")
    _write_text(CONTENT_OUTPUT, raw_content)
    print(f"💾 Saved raw response to {CONTENT_OUTPUT}")

    text_content = _extract_text(raw_content)
    print(f"📏 Extracted text length: {len(text_content)} characters")
    _write_text(TEXT_OUTPUT, text_content)
    print(f"💾 Saved extracted text to {TEXT_OUTPUT}")
    print("\n📄 First 500 chars of extracted text:")
    print(text_content[:500])

    _report_keyword_match(TEST_ANSWER, text_content)


def test_browserless_scrape_api() -> None:
    """Test the Browserless scrape endpoint as an alternative."""
    token = _load_browserless_token()
    if token is None:
        return

    print("\n\n🔄 Testing Browserless.io scrape API...")
    response = _post_json(
        f"https://production-sfo.browserless.io/scrape?token={token}",
        payload={
            "url": TEST_URL,
            "elements": [{"selector": "body"}],
            "waitForSelector": {"selector": ".contentText", "timeout": 10000},
        },
    )
    if response is None:
        return

    print(f"📊 Response status: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ API error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return

    payload = response.json()
    print(f"📦 Response structure: {json.dumps(payload, indent=2)[:500]}")
    SCRAPE_OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Saved scrape response to {SCRAPE_OUTPUT}")


def _load_browserless_token() -> str | None:
    """Load and print the Browserless token prefix."""
    token = os.getenv("BROWSERLESS_TOKEN")
    if not token:
        print("❌ No BROWSERLESS_TOKEN found in environment")
        return None
    print(f"✅ Found BROWSERLESS_TOKEN: {token[:10]}...")
    return token


def _post_json(url: str, *, payload: dict[str, object]) -> requests.Response | None:
    """POST JSON to Browserless and handle request failures."""
    try:
        return requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"❌ Browserless request failed: {exc}")
        return None


def _write_text(path: Path, content: str) -> None:
    """Write a UTF-8 text artifact to disk."""
    path.write_text(content, encoding="utf-8")


def _extract_text(raw_content: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(raw_content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text_content = html.unescape(soup.get_text(" "))
    return " ".join(text_content.split())


def _report_keyword_match(answer: str, text_content: str) -> None:
    """Print keyword overlap diagnostics for a rendered page."""
    print("\n🔍 Testing keyword matching...")
    answer_words = _extract_answer_keywords(answer)
    found_words = sorted(word for word in answer_words if word in text_content)
    missing_words = sorted(answer_words - set(found_words))
    threshold = _matching_threshold(len(answer_words))
    matching_words = len(found_words)

    print(f"📝 Answer keywords: {answer_words}")
    print(f"✅ Found keywords ({len(found_words)}): {found_words}")
    print(f"❌ Missing keywords ({len(missing_words)}): {missing_words}")
    print(f"\n📊 Matching: {matching_words}/{len(answer_words)} words")
    print(f"📏 Threshold: {threshold}")
    print(f"✨ Result: {'PASS' if matching_words >= threshold else 'FAIL'}")


def _extract_answer_keywords(answer: str) -> set[str]:
    """Normalize answer text into comparable keywords."""
    answer_text = re.sub(r"https?://[^\s]+", "", answer)
    answer_text = re.sub(r"[^\w\s\u0590-\u05FF]", " ", answer_text)
    return {word for word in answer_text.split() if len(word) > 1}


def _matching_threshold(total_words: int) -> float:
    """Return the Browserless keyword-match threshold."""
    if total_words < 10:
        return max(2, total_words * 0.15)
    return max(3, total_words * 0.1)


if __name__ == "__main__":
    print("🧪 Testing Browserless.io Web Validation\n")
    test_browserless_content_api()
    test_browserless_scrape_api()
