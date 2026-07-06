"""
Packing List Parser Agent.
Ключевое отличие от Invoice: здесь НЕТ цен.
Фокус на физических параметрах и упаковке.
"""
from agents.parsers.base_parser import BasePDFParser, ParserConfig


class PackingListParser(BasePDFParser):
    document_type = "PACKING_LIST"

    @property
    def SCHEMA(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                # Реквизиты
                "document_number":    {"type": "STRING"},
                "date":               {"type": "STRING"},
                "invoice_reference":  {"type": "STRING"},

                # Стороны
                "seller_name":        {"type": "STRING"},
                "seller_country":     {"type": "STRING"},
                "seller_vat_id":      {"type": "STRING"},
                "buyer_name":         {"type": "STRING"},
                "buyer_country":      {"type": "STRING"},

                # Маршрут
                "origin_place":       {"type": "STRING"},
                "origin_country":     {"type": "STRING"},
                "destination_place":  {"type": "STRING"},
                "destination_country": {"type": "STRING"},
                "incoterms":          {"type": "STRING"},

                # Позиции
                "line_items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "position":         {"type": "INTEGER"},
                            "description":      {"type": "STRING"},
                            "hs_code":          {"type": "STRING"},
                            "quantity_units":   {"type": "NUMBER"},
                            "unit":             {"type": "STRING"},
                            "packages_count":   {"type": "INTEGER"},
                            "packaging_type":   {"type": "STRING"},
                            "length_cm":        {"type": "NUMBER"},
                            "width_cm":         {"type": "NUMBER"},
                            "height_cm":        {"type": "NUMBER"},
                            "volume_cbm":       {"type": "NUMBER"},
                            "net_weight_kg":    {"type": "NUMBER"},
                            "gross_weight_kg":  {"type": "NUMBER"},
                        },
                    },
                },

                # Итого
                "total_packages":       {"type": "INTEGER"},
                "total_units":          {"type": "NUMBER"},
                "total_net_weight_kg":  {"type": "NUMBER"},
                "total_gross_weight_kg": {"type": "NUMBER"},
                "total_volume_cbm":     {"type": "NUMBER"},

                # Маркировка
                "shipping_marks":       {"type": "STRING"},

                # Сводный HS
                "hs_code":              {"type": "STRING"},
            },
            "required": [
                "document_number", "date",
                "seller_name", "seller_country",
                "buyer_name", "buyer_country",
                "total_packages",
                "total_gross_weight_kg",
                "total_volume_cbm",
            ],
        }

    @property
    def SYSTEM_PROMPT(self) -> str:
        return """You are an expert auditor of Packing Lists for international shipments.

CRITICAL RULE: Packing Lists do NOT contain prices or monetary values.
If you see prices, you are looking at an Invoice, not a Packing List.

EXTRACTION RULES:
1. Translate ALL text to English.
2. Countries: ISO 3166-1 alpha-2 (DE, TR, etc.)
3. HS codes: digits ONLY — remove dots, spaces, dashes.
4. Dates: ISO format YYYY-MM-DD.
5. invoice_reference: find the Invoice number this Packing List belongs to.
   Look for: "Invoice No.", "Ref:", "As per Invoice", "Invoice #"
6. Dimensions: always in CM. Convert if needed (1m = 100cm, 1inch = 2.54cm).
7. Weights: always in KG. Convert tonnes (1t = 1000kg).
8. Volume: always in CBM (cubic meters). 
   Calculate from dimensions if not stated: (L×W×H) / 1,000,000
9. packaging_type: cartons / pallets / bags / drums / rolls / crates / etc.
10. shipping_marks: extract box/pallet numbers and any reference codes.
11. total_* fields: use the SUMMARY row at bottom of the document.
    If no summary row, sum up the line items yourself.
12. hs_code at root level: the MAIN hs_code for the shipment.
13. If a field is not found → return "" or 0. NEVER guess."""
