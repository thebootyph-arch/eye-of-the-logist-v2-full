"""
PipelineState — единственный объект который путешествует через весь пайплайн.
Каждый агент читает из него и пишет в него.
"""
from dataclasses import dataclass, field
from typing import Optional
from audit.base_rule import AuditResult


@dataclass
class NormalizedData:
    """Результат работы Normalizer — всё приведено к единому виду."""
    # Стороны
    shipper_name   : str = ""
    shipper_country: str = ""   # ISO 2-letter: "DE"
    shipper_tax_id : str = ""

    consignee_name   : str = ""
    consignee_country: str = ""
    consignee_tax_id : str = ""

    seller_name   : str = ""
    seller_country: str = ""
    seller_vat_id : str = ""

    buyer_name   : str = ""
    buyer_country: str = ""
    buyer_tax_id : str = ""

    # Маршрут
    loading_country    : str = ""
    destination_country: str = ""
    transit_countries  : list[str] = field(default_factory=list)

    # Груз
    hs_code          : str   = ""   # только цифры, без точек
    cargo_description: str   = ""
    packages_count   : int   = 0
    gross_weight_kg  : float = 0.0
    net_weight_kg    : float = 0.0
    volume_cbm       : float = 0.0

    # Финансы
    total_value: float = 0.0
    currency   : str   = ""         # ISO: "EUR"
    incoterms  : str   = ""         # "DAP", "FOB" и т.д.
    price_per_kg: float = 0.0

    # Документы
    cmr_date    : str = ""          # ISO: "2024-01-15"
    invoice_date: str = ""
    invoice_number_in_cmr: bool = False

    # Транспорт
    carrier_name  : str = ""
    vehicle_number: str = ""

    # Флаги
    all_documents_present: bool = False


@dataclass
class PipelineState:
    # ── 1. Input ──────────────────────────────────────────────────
    raw_files: dict[str, bytes] = field(default_factory=dict)
    # {"cmr": b"...", "invoice": b"...", "packing_list": b"..."}

    # ── 2. После парсеров (сырые dict от Gemini) ──────────────────
    cmr_raw         : dict = field(default_factory=dict)
    invoice_raw     : dict = field(default_factory=dict)
    packing_list_raw: dict = field(default_factory=dict)

    # Confidence scores от каждого парсера
    cmr_confidence         : float = 0.0
    invoice_confidence     : float = 0.0
    packing_list_confidence: float = 0.0

    # ── 3. После Normalizer ───────────────────────────────────────
    normalized: NormalizedData = field(default_factory=NormalizedData)

    # ── 4. После Auditor ──────────────────────────────────────────
    audit_results: list[AuditResult] = field(default_factory=list)

    # ── 5. После Risk Engine ──────────────────────────────────────
    risk_score: int = 100

    # ── 6. После Decision Engine ──────────────────────────────────
    decision        : str       = ""   # "APPROVED" / "CONDITIONAL" / "REJECTED"
    rejection_reasons: list[str] = field(default_factory=list)

    # ── Мета ──────────────────────────────────────────────────────
    pipeline_version: str = "2.0"
    errors          : list[str] = field(default_factory=list)

    # ── Хелперы ───────────────────────────────────────────────────
    def add_error(self, msg: str):
        self.errors.append(msg)

    def has_cmr(self) -> bool:
        return bool(self.cmr_raw)

    def has_invoice(self) -> bool:
        return bool(self.invoice_raw)

    def has_packing_list(self) -> bool:
        return bool(self.packing_list_raw)

    def failed_rules(self) -> list[AuditResult]:
        from audit.base_rule import Status
        return [r for r in self.audit_results if r.status == Status.FAIL]

    def critical_failures(self) -> list[AuditResult]:
        from audit.base_rule import Status, Severity
        return [r for r in self.audit_results
                if r.status == Status.FAIL and r.severity == Severity.CRITICAL]
