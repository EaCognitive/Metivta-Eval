"""Shared Anthropic and prompt helpers used across evaluators and targets."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from anthropic import AnthropicError
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from metivta_eval.config.config_loader import get_model

TORAH_SYSTEM_PROMPT = (
    "You are a Torah scholar assistant. "
    "Answer questions accurately, providing specific citations. "
    "Your response should be well-structured, including Hebrew text where appropriate, "
    "and follow scholarly conventions."
)


def ensure_anthropic_environment(logger: logging.Logger | None = None) -> bool:
    """Load environment files and report whether Anthropic credentials are present."""
    load_dotenv(override=True)
    if os.getenv("ANTHROPIC_API_KEY"):
        return True

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

    if not os.getenv("ANTHROPIC_API_KEY") and logger is not None:
        logger.warning(
            "ANTHROPIC_API_KEY not found. Env path checked: %s, exists: %s",
            env_path,
            env_path.exists(),
        )
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def build_chat_model(
    model_alias: str,
    *,
    temperature: float,
    max_tokens: int,
) -> ChatAnthropic:
    """Build a configured Anthropic chat model."""
    return ChatAnthropic(
        model_name=get_model(model_alias),
        temperature=temperature,
        max_tokens_to_sample=max_tokens,
        timeout=60,
        stop=None,
    )


def build_json_chain(template: str, *, model_alias: str = "fast") -> Any:
    """Build a prompt -> Anthropic -> JSON parser chain."""
    prompt = ChatPromptTemplate.from_template(template)
    parser = JsonOutputParser()
    return prompt | build_chat_model(model_alias, temperature=0, max_tokens=512) | parser


def build_torah_answer_chain() -> Any:
    """Build the standard Torah answer generation chain."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", TORAH_SYSTEM_PROMPT), ("user", "{question}")]
    )
    return prompt | build_chat_model("claude", temperature=0.1, max_tokens=2048) | StrOutputParser()


def generate_torah_answer(question: str) -> str:
    """Generate a Torah answer with the standard Anthropic chain."""
    chain = build_torah_answer_chain()
    return str(chain.invoke({"question": question}))


def anthro_error_types() -> tuple[type[BaseException], ...]:
    """Return the exception types expected from Anthropic-backed calls."""
    return (AnthropicError, OSError, TypeError, ValueError, KeyError)
