"""
JSON Report + ERP Export (SAP-совместимый формат).
"""
import json
from datetime import datetime
from audit.base_rule import Status
from state.pipeline_state import PipelineState


class JSONReportGenerator:
    def generate(self, state: PipelineState) -> str:
        n = state.normalized
        report = {
            "meta": {
                "generated_at":     datetime.utcnow().isoformat() + "Z",
                "pipeline_version": state.pipeline_version,
                "decision":         state.decision,
                "risk_score":       state.risk_score,
            },
            "shipment": {
                "shipper":     {"name": n.shipper_name, "country": n.shipper_country,
                                "tax_id": n.shipper_tax_id},
                "consignee":   {"name": n.consignee_name, "country": n.consignee_country,
                                "tax_id": n.consignee_tax_id},
                "route":       {"from": n.loading_country, "to": n.destination_country,
                                "transit": n.transit_countries},
                "cargo":       {"description": n.cargo_description, "hs_code": n.hs_code,
                                "packages": n.packages_count,
                                "gross_weight_kg": n.gross_weight_kg,
                                "net_weight_kg":   n.net_weight_kg,
                                "volume_cbm":      n.volume_cbm},
                "financials":  {"total_value": n.total_value, "currency": n.currency,
                                "incoterms": n.incoterms, "price_per_kg": n.price_per_kg},
                "dates":       {"cmr": n.cmr_date, "invoice": n.invoice_date},
            },
            "audit": {
                "total_rules": len(state.audit_results),
                "passed":  sum(1 for r in state.audit_results if r.status == Status.PASS),
                "failed":  sum(1 for r in state.audit_results if r.status == Status.FAIL),
                "skipped": sum(1 for r in state.audit_results if r.status == Status.SKIP),
                "results": [
                    {
                        "rule_id":   r.rule_id,
                        "name":      r.rule_name,
                        "group":     r.group,
                        "status":    r.status.value,
                        "severity":  r.severity.value,
                        "score":     r.score_impact,
                        "message":   r.message,
                        "documents": r.documents,
                    }
                    for r in state.audit_results
                ],
            },
            "rejection_reasons": state.rejection_reasons,
            "errors":            state.errors,
        }
        return json.dumps(report, indent=2, ensure_ascii=False)


class ERPExportGenerator:
    """
    Экспорт в SAP-совместимый формат (IDOC-подобная структура).
    Готов к интеграции через RFC/API.
    """
    def generate(self, state: PipelineState) -> str:
        n = state.normalized
        erp = {
            "ZLOGIST_AUDIT": {
                "E1HEADER": {
                    "MANDT":      "100",
                    "AUDIT_DATE": datetime.utcnow().strftime("%Y%m%d"),
                    "AUDIT_TIME": datetime.utcnow().strftime("%H%M%S"),
                    "STATUS":     self._sap_status(state.decision),
                    "RISK_SCORE": str(state.risk_score),
                },
                "E1SHIPMENT": {
                    "SHIP_NAME":    n.shipper_name,
                    "SHIP_CTRY":    n.shipper_country,
                    "SHIP_TAX":     n.shipper_tax_id,
                    "CONS_NAME":    n.consignee_name,
                    "CONS_CTRY":    n.consignee_country,
                    "CONS_TAX":     n.consignee_tax_id,
                    "LOAD_CTRY":    n.loading_country,
                    "DEST_CTRY":    n.destination_country,
                    "HS_CODE":      n.hs_code,
                    "GROSS_WT":     str(n.gross_weight_kg),
                    "NET_WT":       str(n.net_weight_kg),
                    "VOLUME":       str(n.volume_cbm),
                    "PACKAGES":     str(n.packages_count),
                    "TOTAL_VAL":    str(n.total_value),
                    "CURRENCY":     n.currency,
                    "INCOTERMS":    n.incoterms,
                    "CMR_DATE":     n.cmr_date.replace("-", "") if n.cmr_date else "",
                    "INV_DATE":     n.invoice_date.replace("-", "") if n.invoice_date else "",
                },
                "E1AUDIT_ITEMS": [
                    {
                        "RULE_ID":  r.rule_id,
                        "STATUS":   r.status.value,
                        "SEVERITY": r.severity.value,
                        "SCORE":    str(r.score_impact),
                        "MESSAGE":  r.message[:255],
                    }
                    for r in state.audit_results
                    if r.status == Status.FAIL
                ],
            }
        }
        return json.dumps(erp, indent=2, ensure_ascii=False)

    @staticmethod
    def _sap_status(decision: str) -> str:
        return {"APPROVED": "A", "CONDITIONAL_APPROVAL": "C", "REJECTED": "R"}.get(decision, "U")
