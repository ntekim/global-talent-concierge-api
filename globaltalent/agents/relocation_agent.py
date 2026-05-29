import os
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
from prompts import relocation_system_prompt, relocation_prompt
from logger import get_logger
from agents.agent_cache import get_embeddings, AgentCache

load_dotenv(dotenv_path=cfg.ENV_PATH)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=cfg.OPENAI_TIMEOUT)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
log = get_logger("relocation_agent")

PROJ = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(PROJ / "chroma_db")

_db = None


def _search_rag_sync(city: str) -> str:
    global _db
    try:
        if _db is None:
            embeddings = get_embeddings()
            _db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        docs = _db.similarity_search(city, k=cfg.RAG_SEARCH_K)
        return "\n\n".join(d.page_content for d in docs)
    except Exception:
        return ""


@retry(
    stop=stop_after_attempt(cfg.RETRY_BRAVE_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
)
def _search_brave_sync(city: str) -> str:
    if not BRAVE_API_KEY:
        return ""
    year = datetime.now().year
    query = f"best neighbourhoods for expat families in {city} {year}"
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


async def _search_rag_async(city: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _search_rag_sync, city)


async def _search_brave_async(city: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _search_brave_sync, city)


@retry(
    stop=stop_after_attempt(cfg.RETRY_OPENAI_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
    retry=retry_if_exception_type(Exception),
)
def _stream_openai(prompt: str) -> str:
    log.info("Streaming relocation guide...")
    stream = client.chat.completions.create(
        model=cfg.MODEL_NAME,
        messages=[
            {"role": "system", "content": relocation_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg.RELOCATION_TEMPERATURE,
        max_tokens=cfg.RELOCATION_MAX_TOKENS,
        stream=True,
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


async def _run_async(hire_profile: dict) -> str:
    cache = AgentCache()
    city = hire_profile.get("destination_city", "unknown")
    family_size = hire_profile.get("family_size", 1)
    cache_key = cache.make_key("relocation", city, family_size)

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    rag_context = ""
    brave_context = ""
    context_warnings = []

    try:
        rag_task = asyncio.create_task(_search_rag_async(city))
        brave_task = asyncio.create_task(_search_brave_async(city))
        rag_context, brave_context = await asyncio.gather(rag_task, brave_task)
    except Exception:
        context_warnings.append("RAG database unavailable")

    if not rag_context.strip():
        context_warnings.append("No local guide found in database")

    combined_context = rag_context or ""
    if brave_context and "[Brave Search unavailable" not in brave_context:
        combined_context += "\n\n--- Brave Search Results ---\n\n" + brave_context
    elif brave_context and "[Brave Search unavailable" in brave_context:
        context_warnings.append("Web search unavailable")

    context_note = ""
    if context_warnings:
        context_note = "\nNote: " + "; ".join(context_warnings) + ". Use general knowledge to fill gaps."

    instruction = relocation_prompt(hire_profile, combined_context, context_note)

    guide = await _stream_openai_async(instruction)
    cache.set(cache_key, guide)
    return guide


def run(hire_profile: dict) -> str:
    t0 = time.perf_counter()
    result = asyncio.run(_run_async(hire_profile))
    elapsed = int((time.perf_counter() - t0) * 1000)
    log.info("Completed in %dms", elapsed)
    return result


async def async_run(hire_profile: dict) -> str:
    t0 = time.perf_counter()
    result = await _run_async(hire_profile)
    elapsed = int((time.perf_counter() - t0) * 1000)
    log.info("Completed in %dms", elapsed)
    return result
