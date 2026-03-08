"""Deterministic DAAT scoring implementation and optional explanation helpers."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from metivta_eval.config.config_loader import get_config_section
from metivta_eval.llm_support import anthro_error_types, build_json_chain

from .utils import extract_answer_text

_HAS_LLM = True

_URL_RE = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+(?:[/?#][^\s<>"{}|\\^`\[\]]*)?')
_HEB_LETTER = re.compile(r"[\u0590-\u05FF]")
_HEB_DIACRITICS = re.compile(r"[\u0591-\u05BD\u05BF-\u05C7]")
# "Substantial" Hebrew block (≥30 chars including spaces/maqaf/geresh/gershayim)
_HEB_BLOCK = re.compile(r"[\u0590-\u05FF][\u0590-\u05FF\s\"\'\-\u05BE\u05F3\u05F4]{29,}")

# In-answer marker cues that indicate attribution sites
_MARKERS = [r"\bsource\b", r"\bsee\b", r"\bcf\.\b", "מקור", "ראה", "עיין", "שם", 'עי"ש', "ועיין"]


@dataclass(frozen=True, slots=True)
class DaatCommentPayload:
    """Inputs needed to render the DAAT feedback comment."""

    score: float
    dai_score: float
    mla_score: float
    dai_breakdown: dict[str, float]
    mla_breakdown: dict[str, float]


def _strip_html(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content or "")
    return html.unescape(text)


def _normalize_hebrew(s: str) -> str:
    if not s:
        return ""
    s = _HEB_DIACRITICS.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_urls(answer: str) -> list[str]:
    return _URL_RE.findall(answer or "")


def _hebrew_fraction(answer: str) -> float:
    if not answer:
        return 0.0
    total = len(answer)
    heb = len(_HEB_LETTER.findall(answer))
    return heb / max(total, 1)


def _iter_spans(pattern: re.Pattern, text: str):
    for m in pattern.finditer(text or ""):
        yield m.start(), m.end(), m.group(0)


def _iter_marker_positions(answer: str):
    # URL positions
    for m in _URL_RE.finditer(answer or ""):
        yield m.start()
    # Lexical markers
    for pat in _MARKERS:
        for m in re.finditer(pat, answer or "", flags=re.IGNORECASE):
            yield m.start()


# -------------------------
# DAI: Digital Attribution
# -------------------------


def _score_attribution_tightness(answer: str, cfg: dict) -> float:
    if not answer:
        return 0.0
    spans = list(_iter_spans(_HEB_BLOCK, answer))
    markers = sorted(_iter_marker_positions(answer))
    if not spans or not markers:
        return 0.0

    distances = [_nearest_marker_distance(start, end, markers) for start, end, _ in spans]
    if not distances:
        return 0.0

    avg = sum(distances) / len(distances)
    for threshold, score in _tightness_thresholds(cfg):
        if avg <= threshold:
            return score
    return 0.0


def _compile_coordinate_patterns() -> list[re.Pattern]:
    # Deep link anchors and internal anchors
    p1 = re.compile(r"\?line=")
    p1b = re.compile(r"#")
    # Daf/amud: e.g., "ב ע\"א" or "ב ע\"ב"
    p2 = re.compile(r'[אבגדהוזחטיכלמנסעפצקרשת]{1,3}\s?ע"[אב]')
    # Chapter:Verse like 20:12
    p3 = re.compile(r"\b\d{1,3}\s*[:.]\s*\d{1,3}\b")
    # Dotted canonical locators (e.g., Exodus.20.12 or Divrei_Yoel...Vayakhel.1.5)
    p4 = re.compile(r"\b[A-Z][A-Za-z_]+(?:\.[A-Za-z_]+)*\.\d+(?:\.\d+)+\b")
    # Siman/Se'if
    p5 = re.compile(r"סימן\s*\S+")
    p6 = re.compile(r"סעיף\s*\S+")
    # Parsha marker
    p7 = re.compile(r"פרשת\s+\S+")
    return [p1, p1b, p2, p3, p4, p5, p6, p7]


_COORD_PATTERNS = _compile_coordinate_patterns()


def _has_any(patterns: list[re.Pattern], text: str) -> int:
    return sum(1 for p in patterns if p.search(text or ""))


def _score_coordinates_disambiguation(answer: str, cfg: dict) -> float:
    if not answer:
        return 0.0
    features = _has_any(_COORD_PATTERNS, answer)

    titles = cfg.get("title_cues", []) or []
    parsha_cue = cfg.get("parsha_cue", "פרשת")
    has_title = any(t in answer for t in titles)
    has_parsha = parsha_cue in answer

    bonus = 0
    if has_title:
        bonus += 1
    if has_parsha:
        bonus += 1

    total = features + bonus
    if total >= 2:
        return 1.0
    if total == 1:
        return 0.6
    return 0.0


def _score_layered_transmission(answer: str) -> float:
    if not answer:
        return 0.0

    primary_terms_he = [
        "בראשית",
        "שמות",
        "ויקרא",
        "במדבר",
        "דברים",
        "תהלים",
        "משלי",
        "ישעיה",
        "ירמיה",
        "יחזקאל",
        "ברכות",
        "שבת",
        "ביצה",
        "כתובות",
        "תענית",
        "מדרש",
        "שמות רבה",
        "ויקרא רבה",
        "ספרא",
        "ספרי",
    ]
    commentary_terms_he = [
        'רש"י',
        'רמב"ם',
        'רמב"ן',
        "תוספות",
        "טור",
        'שו"ע',
        "שולחן ערוך",
        "משנה ברורה",
        "מגן אברהם",
        "ערוך השולחן",
    ]
    chassidic_terms_he = [
        "דברי יואל",
        "תפארת שלמה",
        "נועם אלימלך",
        "שם משמואל",
        "שפת אמת",
        "ויואל משה",
    ]
    halacha_signals = ["להלכה", "הלכה למעשה", "פסק", "נפסק"]

    txt = answer
    found = set()
    if any(t in txt for t in primary_terms_he):
        found.add("primary")
    if any(t in txt for t in commentary_terms_he):
        found.add("commentary")
    if any(t in txt for t in chassidic_terms_he):
        found.add("chassidic")

    base = 0.0
    if len(found) >= 3:
        base = 1.0
    elif len(found) == 2:
        base = 0.7
    elif len(found) == 1:
        base = 0.3
    else:
        base = 0.0

    if any(sig in txt for sig in halacha_signals):
        base = min(1.0, base + 0.15)

    return base


def _score_dai(answer: str, cfg: dict) -> tuple[float, dict]:
    w = cfg.get("dai_weights", {}) or {}
    w_tight = float(w.get("attribution_tightness", 0.40))
    w_coord = float(w.get("coordinates_disambiguation", 0.35))
    w_layer = float(w.get("layered_transmission", 0.25))

    s_tight = _score_attribution_tightness(answer, cfg)
    s_coord = _score_coordinates_disambiguation(answer, cfg)
    s_layer = _score_layered_transmission(answer)

    score = (w_tight * s_tight) + (w_coord * s_coord) + (w_layer * s_layer)
    score = max(0.0, min(1.0, score))
    breakdown = {"tightness": s_tight, "coords": s_coord, "layers": s_layer}
    return score, breakdown


# -------------------------
# MLA: Agentic behavior
# -------------------------


def _score_stepwise_method(answer: str) -> float:
    cues = [
        r"\bplan\b",
        r"\bapproach\b",
        r"\bmethod\b",
        r"\bstep\s*\d+\b",
        r"\bfirst\b",
        r"\bsecond\b",
        r"\bthird\b",
        r"\bfinally\b",
        "ראשית",
        "תחילה",
        "לאחר מכן",
        "לבסוף",
        "שלב",
        "סעיף",
    ]
    hits = sum(1 for c in cues if re.search(c, answer or "", flags=re.IGNORECASE))
    if hits >= 3:
        return 1.0
    if hits == 2:
        return 0.7
    if hits == 1:
        return 0.4
    return 0.0


def _score_multi_source_corroboration(answer: str, urls: list[str]) -> float:
    domains = sorted({urlparse(u).netloc for u in urls}) if urls else []
    multi_domains = len(domains) >= 2
    cross_terms = [r"\bsee also\b", "ראה גם", "ועיין", "עיין"]
    has_terms = any(re.search(t, answer or "", flags=re.IGNORECASE) for t in cross_terms)
    if multi_domains and has_terms:
        return 1.0
    if multi_domains or has_terms:
        return 0.7
    return 0.0


def _score_perspective_handling(answer: str) -> float:
    contrast = [
        r"\bhowever\b",
        r"\bwhereas\b",
        "אמנם",
        "אך",
        "לעומת זאת",
        "מאידך",
        "יש אומרים",
        "ויש אומרים",
    ]
    hits = sum(1 for c in contrast if re.search(c, answer or "", flags=re.IGNORECASE))
    if hits >= 2:
        return 1.0
    if hits == 1:
        return 0.6
    return 0.0


def _score_practical_conclusion(answer: str) -> float:
    concl = [
        r"\btherefore\b",
        r"\bconclude\b",
        r"\bpractically\b",
        "לכן",
        "מסקנה",
        "להלכה למעשה",
        "הלכה למעשה",
    ]
    hits = sum(1 for c in concl if re.search(c, answer or "", flags=re.IGNORECASE))
    if hits >= 1:
        return 1.0
    return 0.0


def _score_mla(answer: str, urls: list[str], cfg: dict) -> tuple[float, dict]:
    w = cfg.get("mla_weights", {}) or {}
    w_step = float(w.get("stepwise_method", 0.30))
    w_multi = float(w.get("multi_source_corroboration", 0.30))
    w_persp = float(w.get("perspective_handling", 0.20))
    w_concl = float(w.get("practical_conclusion", 0.20))

    s_step = _score_stepwise_method(answer)
    s_multi = _score_multi_source_corroboration(answer, urls)
    s_persp = _score_perspective_handling(answer)
    s_concl = _score_practical_conclusion(answer)

    score = (w_step * s_step) + (w_multi * s_multi) + (w_persp * s_persp) + (w_concl * s_concl)
    score = max(0.0, min(1.0, score))
    breakdown = {
        "method": s_step,
        "corroboration": s_multi,
        "perspective": s_persp,
        "conclusion": s_concl,
    }
    return score, breakdown


# -------------------------
# LLM explanation (objective, non-scoring)
# -------------------------

_EXPLAINER_PROMPT = """
You are given a breakdown of subscores that were already computed deterministically.
Your task is ONLY to turn them into a short, objective explanation (2–4 sentences).
Do not change, infer, or re-score anything. Do not speculate about sources.

Inputs:
- Question (truncated): {question}
- Answer (truncated): {answer}
- DAI breakdown: tightness={tightness}, coords={coords}, layers={layers}
- MLA breakdown:
  method={method}, corroboration={corroboration},
  perspective={perspective}, conclusion={conclusion}
- Composite: DAAT={daat}

Return ONLY valid JSON: {{"explanation": "<short objective explanation>"}}
"""


def _llm_explanation(context: dict) -> str:
    if not _HAS_LLM:
        return ""
    try:
        chain = build_json_chain(_EXPLAINER_PROMPT, model_alias="fast")
        out = chain.invoke(context)
        return out.get("explanation", "") if isinstance(out, dict) else ""
    except anthro_error_types():
        return ""


# -------------------------
# Composite DAAT evaluator
# -------------------------


def daat_score_evaluator(run, example) -> dict[str, Any]:
    """Compute the composite DAAT score for a single evaluated answer."""
    cfg_all = get_config_section("evaluators") or {}
    cfg = cfg_all.get("daat_config", {}) or {}
    provide_comment = _should_provide_feedback(cfg_all)

    answer = extract_answer_text(run)
    if not answer:
        return _empty_daat_response(provide_comment)

    urls = _extract_urls(answer)
    dai_score, dai_bd = _score_dai(answer, cfg)
    mla_score, mla_bd = _score_mla(answer, urls, cfg)
    score = _composite_score(dai_score, mla_score, cfg)
    response = {"key": "daat_score", "score": score}

    if provide_comment:
        response["comment"] = _build_daat_comment(
            example=example,
            answer=answer,
            payload=DaatCommentPayload(
                score=score,
                dai_score=dai_score,
                mla_score=mla_score,
                dai_breakdown=dai_bd,
                mla_breakdown=mla_bd,
            ),
        )

    return response


DAAT_EVALUATORS = {
    "daat_score": daat_score_evaluator,
}


def _should_provide_feedback(cfg_all: dict[str, Any]) -> bool:
    """Return whether DAAT should attach a textual explanation."""
    enable_feedback = cfg_all.get("enable_llm_feedback", True)
    feedback_list = cfg_all.get("feedback_evaluators", []) or []
    return enable_feedback and ("daat_score" in feedback_list)


def _empty_daat_response(provide_comment: bool) -> dict[str, Any]:
    """Return the empty-answer DAAT response payload."""
    response = {"key": "daat_score", "score": 0.0}
    if provide_comment:
        response["comment"] = "No answer provided."
    return response


def _composite_score(dai_score: float, mla_score: float, cfg: dict[str, Any]) -> float:
    """Compute the weighted DAAT composite score."""
    weights = cfg.get("composite_weights", {}) or {}
    weighted = (
        float(weights.get("dai", 0.60)) * dai_score + float(weights.get("mla", 0.40)) * mla_score
    )
    return max(0.0, min(1.0, weighted))


def _nearest_marker_distance(start: int, end: int, markers: list[int]) -> int:
    """Return the closest marker distance for one Hebrew span."""
    center = (start + end) // 2
    return min(abs(center - marker) for marker in markers)


def _tightness_thresholds(cfg: dict[str, Any]) -> tuple[tuple[int, float], ...]:
    """Return configured attribution tightness thresholds."""
    threshold_config = cfg.get("tightness_thresholds", {})
    return (
        (int(threshold_config.get("best", 200)), 1.0),
        (int(threshold_config.get("good", 400)), 0.8),
        (int(threshold_config.get("fair", 800)), 0.5),
        (int(threshold_config.get("minimal", 1200)), 0.2),
    )


def _build_daat_comment(
    *,
    example: Any,
    answer: str,
    payload: DaatCommentPayload,
) -> str:
    """Build the DAAT feedback comment from deterministic subscores."""
    explain_ctx = _build_explanation_context(
        example,
        answer,
        payload.score,
        payload.dai_breakdown,
        payload.mla_breakdown,
    )
    explanation = _llm_explanation(explain_ctx) if _HAS_LLM else ""
    if explanation:
        return explanation
    return (
        f"DAAT={payload.score:.2f} (DAI={payload.dai_score:.2f}, MLA={payload.mla_score:.2f}). "
        "DAI["
        f"tight={payload.dai_breakdown['tightness']:.2f}, "
        f"coords={payload.dai_breakdown['coords']:.2f}, "
        f"layers={payload.dai_breakdown['layers']:.2f}] "
        "MLA["
        f"method={payload.mla_breakdown['method']:.2f}, "
        f"corroboration={payload.mla_breakdown['corroboration']:.2f}, "
        f"perspective={payload.mla_breakdown['perspective']:.2f}, "
        f"conclusion={payload.mla_breakdown['conclusion']:.2f}]"
    )


def _build_explanation_context(
    example: Any,
    answer: str,
    score: float,
    dai_breakdown: dict[str, float],
    mla_breakdown: dict[str, float],
) -> dict[str, str]:
    """Build the explainer payload for optional non-scoring LLM feedback."""
    question = str(example.inputs.get("question", "") or "")[:400]
    return {
        "question": question,
        "answer": answer[:800],
        "tightness": f"{dai_breakdown['tightness']:.2f}",
        "coords": f"{dai_breakdown['coords']:.2f}",
        "layers": f"{dai_breakdown['layers']:.2f}",
        "method": f"{mla_breakdown['method']:.2f}",
        "corroboration": f"{mla_breakdown['corroboration']:.2f}",
        "perspective": f"{mla_breakdown['perspective']:.2f}",
        "conclusion": f"{mla_breakdown['conclusion']:.2f}",
        "daat": f"{score:.2f}",
    }
