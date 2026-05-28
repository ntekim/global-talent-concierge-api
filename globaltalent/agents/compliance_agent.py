import os
import json
import sys
import asyncio
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from openai import OpenAI
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg
from prompts import compliance_system_prompt, compliance_prompt
from logger import get_logger
from agents.agent_cache import get_embeddings, AgentCache

load_dotenv(dotenv_path=cfg.ENV_PATH)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=cfg.OPENAI_TIMEOUT)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
log = get_logger("compliance_agent")

PROJ = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(PROJ / "chroma_db")

_db = None


def _search_rag_sync(country: str) -> str:
    global _db
    try:
        if _db is None:
            embeddings = get_embeddings()
            _db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        docs = _db.similarity_search(country, k=cfg.RAG_SEARCH_K)
        return "\n\n".join(d.page_content for d in docs)
    except Exception:
        return ""


@retry(
    stop=stop_after_attempt(cfg.RETRY_BRAVE_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
)
def _search_brave_sync(country: str) -> str:
    if not BRAVE_API_KEY:
        return ""
    year = datetime.now().year
    query = f"{country} work visa document requirements {year}"
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_API_KEY}
    params = {"q": query, "count": cfg.BRAVE_SEARCH_COUNT}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=cfg.BRAVE_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        return "\n\n".join(r.get("description", "") for r in results if r.get("description"))
    except Exception:
        return "[Brave Search unavailable - continuing with RAG context only]"


async def _search_rag_async(country: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _search_rag_sync, country)


async def _search_brave_async(country: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _search_brave_sync, country)


@retry(
    stop=stop_after_attempt(cfg.RETRY_OPENAI_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
    retry=retry_if_exception_type(Exception),
)
def _stream_openai(prompt: str) -> str:
    log.info("Streaming compliance verdict...")
    stream = client.chat.completions.create(
        model=cfg.MODEL_NAME,
        messages=[
            {"role": "system", "content": compliance_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg.COMPLIANCE_TEMPERATURE,
        max_tokens=cfg.COMPLIANCE_MAX_TOKENS,
        stream=True,
        response_format={"type": "json_object"},
    )
    full = ""
    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            print(token, end="", flush=True)
            full += token
    print()
    return full


async def _stream_openai_async(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _stream_openai, prompt)


def interpret_confidence(score: int) -> str:
    if score >= 90:
        return "VERY HIGH CONFIDENCE [PASS]"
    elif score >= 70:
        return "HIGH CONFIDENCE [PASS]"
    elif score >= 50:
        return "MODERATE CONFIDENCE [WARN] - Human review strongly advised"
    elif score >= 30:
        return "LOW CONFIDENCE [FAIL] - AI is unsure, human must decide"
    else:
        return "VERY LOW CONFIDENCE [FAIL] - Do not rely on this result"


def _apply_date_validations(result: dict, document_data: dict) -> dict:
    date_errors = document_data.get("date_errors", [])
    date_warnings = document_data.get("date_warnings", [])

    for err in date_errors:
        result.setdefault("reasons", []).insert(0, f"[DATE VALIDATION FAIL] {err}")
        result["status"] = "FAIL"
        result["confidence_score"] = min(result.get("confidence_score", 100), 10)

    for warn in date_warnings:
        result.setdefault("reasons", []).append(f"[DATE WARNING] {warn}")

    result["date_errors"] = date_errors
    result["date_warnings"] = date_warnings

    return result


async def _run_async(document_data: dict, destination_country: str) -> dict:
    cache = AgentCache()
    doc_type = document_data.get("document_type", "unknown")
    cache_key = cache.make_key("compliance", doc_type, destination_country)

    cached = cache.get(cache_key)
    if cached is not None:
        result = dict(cached)
        result = _apply_date_validations(result, document_data)
        return result

    rag_context = ""
    brave_context = ""
    context_warnings = []

    try:
        rag_task = asyncio.create_task(_search_rag_async(destination_country))
        brave_task = asyncio.create_task(_search_brave_async(destination_country))
        rag_context, brave_context = await asyncio.gather(rag_task, brave_task)
    except Exception:
        context_warnings.append("RAG database unavailable - relying on web search only")

    if not rag_context.strip() or rag_context == "No relevant documents found.":
        context_warnings.append("No relevant visa rules found in local database")

    combined_context = rag_context or ""
    if brave_context and "[Brave Search unavailable" not in brave_context:
        combined_context += "\n\n--- Brave Search Results ---\n\n" + brave_context
    elif brave_context and "[Brave Search unavailable" in brave_context:
        context_warnings.append("Web search unavailable")

    context_note = ""
    if context_warnings:
        context_note = "\nNote: " + "; ".join(context_warnings) + ". Be more conservative in your assessment."

    prompt = compliance_prompt(combined_context, context_note, document_data)

    content = await _stream_openai_async(prompt)

    if content.strip().startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(content)
    result = {
        "status": parsed.get("status", "FAIL"),
        "confidence_score": parsed.get("confidence_score", 0),
        "reasons": parsed.get("reasons", []),
        "missing_documents": parsed.get("missing_documents", []),
        "recommendation": parsed.get("recommendation", ""),
    }

    result = _apply_date_validations(result, document_data)

    score = result.get("confidence_score", 0)
    result["confidence_label"] = interpret_confidence(score)

    if score < 60:
        result.setdefault("reasons", []).append(
            "AI confidence is low. A human specialist should manually verify this document before making a decision."
        )

    cache.set(cache_key, result)
    return result


def run(document_data: dict, destination_country: str) -> dict:
    t0 = time.perf_counter()
    result = asyncio.run(_run_async(document_data, destination_country))
    elapsed = int((time.perf_counter() - t0) * 1000)
    log.info("Completed in %dms", elapsed)
    return result


async def async_run(document_data: dict, destination_country: str) -> dict:
    t0 = time.perf_counter()
    result = await _run_async(document_data, destination_country)
    elapsed = int((time.perf_counter() - t0) * 1000)
    log.info("Completed in %dms", elapsed)
    return result
