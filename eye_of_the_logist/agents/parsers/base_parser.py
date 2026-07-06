"""
BasePDFParser — общий класс для всех парсеров.
Работает с Vertex AI или Gemini API (по умолчанию gemini-2.5-flash-lite) через REST API.
Каждый наследник переопределяет: SCHEMA, SYSTEM_PROMPT, document_type.
"""
import asyncio
import base64
import json
import logging
import time
import requests
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# ── Vertex AI и Gemini endpoint templates ──────────────────────────
VERTEX_URL_TEMPLATE = (
    "https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}"
    "/locations/{region}/publishers/google/models/{model}:generateContent"
)
GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}"
    ":generateContent?key={api_key}"
)

# Переходим на gemini-2.5-flash-lite: она быстрая, дешевая и идеальна для извлечения JSON структур
DEFAULT_MODEL  = "gemini-2.5-flash-lite"
MAX_RETRIES    = 4
RETRY_DELAYS   = [1, 2, 4, 8]
REQUEST_TIMEOUT = 60


class ParserConfig:
    """Конфигурация подключения — Vertex AI или Gemini API."""
    def __init__(
        self,
        api_key: str | None = None,       # Gemini AI Studio key
        project_id: str | None = None,    # Vertex project
        region: str = "us-central1",
        access_token: str | None = None,  # Vertex OAuth token
        model: str = DEFAULT_MODEL,
    ):
        self.api_key      = api_key
        self.project_id   = project_id
        self.region       = region
        self.access_token = access_token
        self.model        = model

    def use_vertex(self) -> bool:
        return bool(self.project_id and self.access_token)

    def endpoint(self) -> str:
        if self.use_vertex():
            return VERTEX_URL_TEMPLATE.format(
                region=self.region,
                project_id=self.project_id,
                model=self.model,
            )
        return GEMINI_URL_TEMPLATE.format(
            model=self.model,
            api_key=self.api_key,
        )

    def headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.use_vertex():
            h["Authorization"] = f"Bearer {self.access_token}"
        return h


class BasePDFParser(ABC):
    """
    Базовый парсер. Наследники задают схему и промпт.
    Возвращает dict с распарсенными данными + confidence float.
    """

    # Глобальный "светофор" для предотвращения 429 ошибок на бесплатном тарифе
    _rate_limit_lock = asyncio.Lock()
    _last_request_time = 0.0

    document_type: str = "UNKNOWN"

    @property
    @abstractmethod
    def SCHEMA(self) -> dict:
        """Gemini responseSchema для этого типа документа."""
        ...

    @property
    @abstractmethod
    def SYSTEM_PROMPT(self) -> str:
        """Системный промпт — инструкции специфичные для документа."""
        ...

    def __init__(self, config: ParserConfig):
        self.config = config

    @classmethod
    async def _enforce_rate_limit(cls):
        """
        Гарантирует задержку не менее 4.2 секунд между любыми запросами к API.
        Защищает бесплатные ключи от блокировок RPM (Requests Per Minute).
        """
        async with cls._rate_limit_lock:
            now = time.time()
            elapsed = now - cls._last_request_time
            if elapsed < 4.2:
                await asyncio.sleep(4.2 - elapsed)
            cls._last_request_time = time.time()

    # ── Public API ────────────────────────────────────────────────
    async def parse(self, file_bytes: bytes, mime_type: str) -> tuple[dict, float]:
        """
        Парсит документ, возвращает (data_dict, confidence_score).
        """
        payload = self._build_payload(file_bytes, mime_type)
        raw     = await self._call_with_retry(payload)
        data    = self._extract_json(raw)
        conf    = self._estimate_confidence(data)
        return data, conf

    # ── Payload builder ───────────────────────────────────────────
    def _build_payload(self, file_bytes: bytes, mime_type: str) -> dict:
        parts: list[dict] = []

        # Документ: PDF или изображение
        if mime_type == "application/pdf":
            b64 = base64.b64encode(file_bytes).decode()
            parts.append({
                "inlineData": {
                    "mimeType": "application/pdf",
                    "data": b64,
                }
            })
        elif mime_type in ("image/png", "image/jpeg", "image/webp"):
            b64 = base64.b64encode(file_bytes).decode()
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": b64,
                }
            })

        parts.append({"text": self._user_instruction()})

        return {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {
                "parts": [{"text": self.SYSTEM_PROMPT}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.SCHEMA,
                "temperature": 0.0,   # детерминированный парсинг
            },
        }

    def _user_instruction(self) -> str:
        return (
            f"Analyze this {self.document_type} document carefully. "
            "Extract ALL fields according to the schema. "
            "For missing fields use empty string or 0. "
            "Translate all text to English. "
            "Do NOT hallucinate or guess values."
        )

    # ── HTTP call with exponential backoff ────────────────────────
    async def _call_with_retry(self, payload: dict) -> dict:
        url     = self.config.endpoint()
        headers = self.config.headers()

        last_error: Exception | None = None
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                # Встаем в очередь перед вызовом API
                await self._enforce_rate_limit()

                response = await asyncio.to_thread(
                    requests.post,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                if response.status_code == 200:
                    return response.json()

                # Ошибки, при которых имеет смысл повторить запрос
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"[{self.document_type}] HTTP {response.status_code} "
                        f"— retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Критические ошибки - не повторяем
                response.raise_for_status()

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"[{self.document_type}] Timeout on attempt {attempt + 1}")
                await asyncio.sleep(delay)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    continue
                break

        raise RuntimeError(
            f"[{self.document_type}] Parser failed after {MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    # ── Response parsing ──────────────────────────────────────────
    @staticmethod
    def _extract_json(response: dict) -> dict:
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to extract JSON from Gemini response: {e}")

    # ── Confidence estimation ─────────────────────────────────────
    def _estimate_confidence(self, data: dict) -> float:
        required = self.SCHEMA.get("required", [])
        if not required:
            return 1.0
        filled = sum(
            1 for f in required
            if data.get(f) not in (None, "", 0, 0.0, [])
        )
        return round(filled / len(required), 2)