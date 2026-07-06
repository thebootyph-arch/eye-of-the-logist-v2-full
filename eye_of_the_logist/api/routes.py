"""
FastAPI routes — REST API для B2B интеграции.
Клиент загружает 3 файла, получает JSON с результатами аудита.
"""
import asyncio
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from agents.classifier import DocumentClassifier
from agents.parsers.cmr_parser import CMRParser
from agents.parsers.invoice_parser import InvoiceParser
from agents.parsers.packing_list_parser import PackingListParser
from agents.parsers.base_parser import ParserConfig
from agents.normalizer import Normalizer
from audit.auditor import CrossDocumentAuditor
from engine.risk_engine import RiskEngine, DecisionEngine
from reports.json_report import JSONReportGenerator, ERPExportGenerator
from reports.pdf_report import PDFReportGenerator
from state.pipeline_state import PipelineState

app = FastAPI(
    title="Eye of the Logist API",
    description="AI-Powered Logistics Document Audit",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _make_config(api_key: str) -> ParserConfig:
    return ParserConfig(api_key=api_key.strip())


async def _run_pipeline(
    files: dict[str, tuple[bytes, str]],
    config: ParserConfig,
) -> PipelineState:
    """Запускает полный пайплайн, возвращает PipelineState."""
    state = PipelineState()

    # ── Classify + Parse (параллельно) ────────────────────────────
    classifier = DocumentClassifier(config)

    async def classify_and_parse(file_bytes: bytes, mime_type: str):
        doc_type = await classifier.classify(file_bytes, mime_type)
        if doc_type == "CMR":
            parser = CMRParser(config)
        elif doc_type == "INVOICE":
            parser = InvoiceParser(config)
        elif doc_type == "PACKING_LIST":
            parser = PackingListParser(config)
        else:
            return doc_type, {}, 0.0
        data, conf = await parser.parse(file_bytes, mime_type)
        return doc_type, data, conf

    tasks = [
        classify_and_parse(fb, mt)
        for fb, mt in files.values()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            state.add_error(str(result))
            continue
        doc_type, data, conf = result
        if doc_type == "CMR":
            state.cmr_raw = data
            state.cmr_confidence = conf
        elif doc_type == "INVOICE":
            state.invoice_raw = data
            state.invoice_confidence = conf
        elif doc_type == "PACKING_LIST":
            state.packing_list_raw = data
            state.packing_list_confidence = conf

    # ── Normalize ─────────────────────────────────────────────────
    state.normalized = Normalizer().normalize(state)

    # ── Audit ─────────────────────────────────────────────────────
    CrossDocumentAuditor().run(state)

    # ── Risk + Decision ───────────────────────────────────────────
    RiskEngine().calculate(state)
    DecisionEngine().decide(state)

    return state


# ── Endpoints ─────────────────────────────────────────────────────

@app.post("/audit", summary="Run full document audit")
async def audit_documents(
    files: list[UploadFile] = File(..., description="Upload 2-3 documents (CMR, Invoice, PL)"),
    x_api_key: str = Header(..., description="Gemini API Key"),
    format: str = "json",
):
    """
    Принимает до 3 файлов (PDF/PNG/JPG), запускает полный аудит.
    Возвращает JSON с результатами или PDF отчёт.
    """
    if not files:
        raise HTTPException(400, "No files uploaded.")
    if len(files) > 3:
        raise HTTPException(400, "Maximum 3 files allowed.")

    config = _make_config(x_api_key)
    file_dict = {}
    for i, f in enumerate(files):
        content   = await f.read()
        mime_type = f.content_type or "application/octet-stream"
        file_dict[str(i)] = (content, mime_type)

    state = await _run_pipeline(file_dict, config)

    if format == "pdf":
        pdf_bytes = PDFReportGenerator().generate(state)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=audit_report.pdf"},
        )
    if format == "erp":
        erp_json = ERPExportGenerator().generate(state)
        return Response(content=erp_json, media_type="application/json")

    return JSONResponse(content=json.loads(JSONReportGenerator().generate(state)))


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "version": "2.0.0"}
