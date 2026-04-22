"""Logging, LLM wrapper, retry, and run-id helpers."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from . import config
from .schemas import LLMCallRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("tad")

_RUN_DIR: Path | None = None


def new_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def get_run_dir(run_id: str) -> Path:
    d = config.OUTPUT_DIR / run_id
    d.mkdir(exist_ok=True, parents=True)
    return d


def set_active_run(run_id: str) -> Path:
    global _RUN_DIR
    _RUN_DIR = get_run_dir(run_id)
    return _RUN_DIR


def active_run_dir() -> Path:
    global _RUN_DIR
    if _RUN_DIR is None:
        _RUN_DIR = get_run_dir(new_run_id())
    return _RUN_DIR


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

_genai = None
_configured_key: str | None = None


def _lazy_genai():
    global _genai, _configured_key
    import google.generativeai as genai  # type: ignore

    if _configured_key != config.GOOGLE_API_KEY:
        genai.configure(api_key=config.GOOGLE_API_KEY)
        _configured_key = config.GOOGLE_API_KEY
    _genai = genai
    return genai


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Best-effort JSON extraction from an LLM response that may be wrapped in fences or prose."""
    if not text:
        raise ValueError("empty response")
    m = _CODE_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    # Find first { and last } or first [ and last ]
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        i = text.find(open_ch)
        j = text.rfind(close_ch)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i : j + 1])
            except Exception:
                continue
    # last resort — whole string
    return json.loads(text)


# ---------------------------------------------------------------------------
# LLM wrapper
# ---------------------------------------------------------------------------


class LLMError(Exception):
    pass


def _log_call(record: LLMCallRecord) -> None:
    try:
        path = active_run_dir() / "llm_calls.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
    except Exception as e:
        logger.warning("failed to log LLM call: %s", e)


def _log_dead_letter(stage: str, model: str, prompt: str, error: str) -> None:
    try:
        path = active_run_dir() / "dead_letters.jsonl"
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "stage": stage,
            "model": model,
            "prompt": prompt[:4000],
            "error": error,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        logger.warning("failed to log dead letter: %s", e)


@retry(
    retry=retry_if_exception_type((LLMError,)),
    stop=stop_after_attempt(config.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=config.LLM_RETRY_BASE_S, min=1, max=30),
    reraise=True,
)
def _do_generate(model_name: str, prompt: str, temperature: float) -> str:
    genai = _lazy_genai()
    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "response_mime_type": "text/plain"},
        )
        text = getattr(resp, "text", None) or ""
        if not text:
            # try parts
            try:
                text = "".join(p.text for p in resp.candidates[0].content.parts if hasattr(p, "text"))
            except Exception:
                text = ""
        if not text:
            raise LLMError("empty response from model")
        return text
    except LLMError:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "quota" in msg or "503" in msg or "rate" in msg or "unavailable" in msg:
            raise LLMError(str(e))
        raise


def call_llm(
    model: str,
    prompt: str,
    *,
    stage: str,
    response_schema: Type[BaseModel] | None = None,
    temperature: float = 0.0,
    max_retries: int | None = None,
) -> tuple[Any, LLMCallRecord]:
    """Single entry point for every LLM call. Logs, retries, validates."""
    call_id = uuid.uuid4().hex[:10]
    t0 = time.time()
    raw = ""
    try:
        raw = _do_generate(model, prompt, temperature)
        parsed: Any = raw
        parse_ok = True
        if response_schema is not None:
            try:
                data = extract_json(raw)
                parsed = response_schema.model_validate(data)
            except Exception as e:
                parse_ok = False
                record = LLMCallRecord(
                    call_id=call_id,
                    stage=stage,
                    model=model,
                    prompt=prompt,
                    response_raw=raw,
                    response_parsed=None,
                    parse_ok=False,
                    elapsed_ms=int((time.time() - t0) * 1000),
                    error=f"schema parse failure: {e}",
                )
                _log_call(record)
                _log_dead_letter(stage, model, prompt, f"parse: {e}")
                raise LLMError(f"Response failed schema validation: {e}") from e
        record = LLMCallRecord(
            call_id=call_id,
            stage=stage,
            model=model,
            prompt=prompt,
            response_raw=raw,
            response_parsed=parsed.model_dump() if isinstance(parsed, BaseModel) else (parsed if isinstance(parsed, (dict, list, str, int, float, bool)) else str(parsed)),
            parse_ok=parse_ok,
            elapsed_ms=int((time.time() - t0) * 1000),
        )
        _log_call(record)
        return parsed, record
    except Exception as e:
        _log_dead_letter(stage, model, prompt, str(e))
        record = LLMCallRecord(
            call_id=call_id,
            stage=stage,
            model=model,
            prompt=prompt,
            response_raw=raw,
            parse_ok=False,
            elapsed_ms=int((time.time() - t0) * 1000),
            error=str(e),
        )
        _log_call(record)
        raise


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {name} at {path}")
    return path.read_text(encoding="utf-8")


def render(name: str, **vars: Any) -> str:
    tmpl = load_prompt(name)
    out = tmpl
    for k, v in vars.items():
        out = out.replace("{" + k + "}", str(v))
    return out


# ---------------------------------------------------------------------------
# Span utilities (IoU over character spans)
# ---------------------------------------------------------------------------


def iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    a0, a1 = a
    b0, b1 = b
    if a1 <= a0 or b1 <= b0:
        return 0.0
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    if union <= 0:
        return 0.0
    return inter / union
