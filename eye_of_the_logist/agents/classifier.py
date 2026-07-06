"""
Document Classifier — определяет тип загруженного документа.
Использует лёгкий Gemini вызов без schema (просто текст).
Fallback: rule-based keyword matching по тексту PDF.
"""
import asyncio
import base64
import re
import requests
from agents.parsers.base_parser import ParserConfig, REQUEST_TIMEOUT, BasePDFParser, RETRY_DELAYS

VALID_TYPES = {"CMR", "INVOICE", "PACKING_LIST"}

# Ключевые слова для fallback классификации
KEYWORDS: dict[str, list[str]] = {
    "CMR": [
        "cmr", "convention on the contract", "international carriage",
        "sender", "consignee", "carrier", "place of loading",
        "place of delivery", "successive carriers",
    ],
    "INVOICE": [
        "commercial invoice", "invoice no", "invoice number",
        "unit price", "total amount", "payment terms",
        "vat number", "seller", "buyer", "subtotal",
    ],
    "PACKING_LIST": [
        "packing list", "packing slip",
        "net weight", "gross weight", "dimensions",
        "cartons", "pallets", "shipping marks",
        "packages", "total packages",
    ],
}

CLASSIFIER_PROMPT = """You are a logistics document classifier.
Analyze the document and respond with EXACTLY ONE of these words:
CMR
INVOICE
PACKING_LIST

Rules:
- CMR: International road transport waybill (Convention Marchandises Routières)
- INVOICE: Commercial invoice with prices and monetary values
- PACKING_LIST: Packing list with weights/dimensions but NO prices

Respond with ONLY the document type, nothing else."""


class DocumentClassifier:
    def __init__(self, config: ParserConfig):
        self.config = config

    async def classify(self, file_bytes: bytes, mime_type: str,
                       text_hint: str = "") -> str:
        """
        Определяет тип документа.
        Сначала пробует AI, fallback — keywords.
        Возвращает: "CMR" | "INVOICE" | "PACKING_LIST" | "UNKNOWN"
        """
        # Быстрый fallback по тексту (дешевле AI вызова)
        if text_hint:
            keyword_result = self._keyword_classify(text_hint)
            if keyword_result != "UNKNOWN":
                return keyword_result

        # AI классификация
        try:
            result = await self._ai_classify(file_bytes, mime_type)
            if result in VALID_TYPES:
                return result
        except Exception:
            pass

        # Финальный fallback по bytes (PDF метаданные)
        if text_hint:
            return self._keyword_classify(text_hint)

        return "UNKNOWN"

    def _keyword_classify(self, text: str) -> str:
        text_lower = text.lower()
        scores = {doc_type: 0 for doc_type in VALID_TYPES}
        for doc_type, keywords in KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[doc_type] += 1

        best_type  = max(scores, key=lambda k: scores[k])
        best_score = scores[best_type]

        # Минимум 2 совпадения для уверенной классификации
        if best_score < 2:
            return "UNKNOWN"
        return best_type

    async def _ai_classify(self, file_bytes: bytes, mime_type: str) -> str:
        parts: list[dict] = []

        if mime_type in ("application/pdf", "image/png", "image/jpeg", "image/webp"):
            b64 = base64.b64encode(file_bytes).decode()
            parts.append({"inlineData": {"mimeType": mime_type, "data": b64}})

        parts.append({"text": "What type of document is this? Reply with ONE word only."})

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": CLASSIFIER_PROMPT}]},
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 10,
            },
        }

        # ДОБАВЛЕНА ЗАЩИТА: Цикл перезапуска и ожидание в общей очереди
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                # Встаем в ту же самую очередь, что и парсеры (4.2 сек пауза)
                await BasePDFParser._enforce_rate_limit()

                response = await asyncio.to_thread(
                    requests.post,
                    self.config.endpoint(),
                    json=payload,
                    headers=self.config.headers(),
                    timeout=REQUEST_TIMEOUT,
                )
                
                if response.status_code == 200:
                    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return text.strip().upper().replace(" ", "_")

                # Если поймали лимит (429) или сбой сервера (50x) - ждем и пробуем снова
                if response.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(delay)
                    continue
                    
                response.raise_for_status()

            except Exception as e:
                # Если попытки еще остались - пробуем снова
                if attempt < len(RETRY_DELAYS) - 1:
                    await asyncio.sleep(delay)
                    continue
                # Если все сломалось - пробрасываем ошибку дальше
                raise RuntimeError(f"Classifier failed after {len(RETRY_DELAYS)} attempts: {str(e)}")

        return "UNKNOWN"