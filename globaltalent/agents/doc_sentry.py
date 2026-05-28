import os
import json
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as cfg
from prompts import extraction_prompt
from logger import get_logger

load_dotenv(dotenv_path=cfg.ENV_PATH)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=cfg.OPENAI_TIMEOUT)
log = get_logger("doc_sentry")

FALLBACK_DICT = {
    "full_name": None,
    "document_type": None,
    "document_number": None,
    "issue_date": None,
    "expiry_date": None,
    "nationality": None,
    "issuing_country": None,
}

SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png"}
CRITICAL_FIELDS = ["full_name", "document_type", "document_number"]


def _clean_text(text: str) -> str:
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    text = re.sub(r"[|\|]", "I", text)
    text = re.sub(r"0", "O", text) if len(text) < 100 else text
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _ocr_image(image_path: str) -> str:
    return pytesseract.image_to_string(Image.open(image_path))


def _extract_pdf_text(pdf_path: str) -> str | None:
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        return text.strip() if text.strip() else None
    except Exception:
        return None


def _ocr_pdf(pdf_path: str) -> str:
    pages = convert_from_path(pdf_path)
    text_parts = []
    for page in pages:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            page.save(tmp.name, "PNG")
            text_parts.append(_ocr_image(tmp.name))
            os.unlink(tmp.name)
    return "\n".join(text_parts)


@retry(
    stop=stop_after_attempt(cfg.RETRY_OPENAI_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=cfg.RETRY_MIN_WAIT, max=cfg.RETRY_MAX_WAIT),
    retry=retry_if_exception_type(Exception),
)
def _parse_with_openai(raw_text: str) -> dict:
    resp = client.chat.completions.create(
        model=cfg.MODEL_NAME,
        messages=[{"role": "user", "content": extraction_prompt(raw_text)}],
        temperature=cfg.EXTRACTION_TEMPERATURE,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content.strip()
    return json.loads(content)


def _validate_result(result: dict) -> dict:
    missing = [f for f in CRITICAL_FIELDS if result.get(f) is None]
    if missing:
        result["_warnings"] = [f"Could not extract required field(s): {', '.join(missing)}"]
    return result


DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %B %Y",
]


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _validate_dates(result: dict) -> dict:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    six_months = today + timedelta(days=180)

    issue = _parse_date(result.get("issue_date"))
    expiry = _parse_date(result.get("expiry_date"))

    errors = []
    warnings = []

    if issue and issue > today:
        errors.append("Document issue date is in the future. This document is invalid.")
        log.warning("Date validation: issue_date %s is in the future", result["issue_date"])

    if expiry and expiry < today:
        errors.append("Document is expired.")
        log.warning("Date validation: expiry_date %s has passed", result["expiry_date"])

    if issue and expiry and expiry <= issue:
        errors.append("Document expiry date is before or equal to issue date. This document is invalid.")
        log.warning("Date validation: expiry %s <= issue %s", result["expiry_date"], result["issue_date"])

    if expiry and today <= expiry < six_months:
        warnings.append("Document expires in less than 6 months. May not meet destination country requirements.")
        log.warning("Date validation: expiry %s within 6 months", result["expiry_date"])

    if errors:
        result["date_errors"] = errors
    if warnings:
        result["date_warnings"] = warnings

    return result


def run(file_path: str) -> dict:
    t0 = time.perf_counter()
    result = dict(FALLBACK_DICT)

    try:
        ext = Path(file_path).suffix.lower()
        raw = None

        if ext == ".pdf":
            raw = _extract_pdf_text(file_path)
            if not raw:
                log.info("PDF text extraction empty, falling back to OCR...")
                raw = _ocr_pdf(file_path)
        elif ext in SUPPORTED_IMAGES:
            raw = _ocr_image(file_path)
        else:
            elapsed = int((time.perf_counter() - t0) * 1000)
            log.warning("Unsupported file type: %s (%dms)", ext, elapsed)
            return {**FALLBACK_DICT, "error": f"Unsupported file type: {ext}"}

        raw = _clean_text(raw)

        if not raw.strip():
            elapsed = int((time.perf_counter() - t0) * 1000)
            log.warning("No text extracted (%dms)", elapsed)
            return {**FALLBACK_DICT, "error": "No text extracted from document"}

        parsed = _parse_with_openai(raw)
        result = {k: parsed.get(k, None) for k in FALLBACK_DICT}
        result = _validate_result(result)
        result = _validate_dates(result)
    except Exception as e:
        result = {**FALLBACK_DICT, "error": str(e)}

    elapsed = int((time.perf_counter() - t0) * 1000)
    log.info("Completed in %dms", elapsed)
    return result
