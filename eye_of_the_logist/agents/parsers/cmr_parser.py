"""
CMR Parser Agent — специализирован под международные транспортные накладные.
Знает структуру CMR: Box 1 = Shipper, Box 2 = Consignee, Box 16 = Carrier.
"""
from agents.parsers.base_parser import BasePDFParser, ParserConfig


class CMRParser(BasePDFParser):
    document_type = "CMR"

    @property
    def SCHEMA(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                # Стороны
                "shipper_name":      {"type": "STRING"},
                "shipper_address":   {"type": "STRING"},
                "shipper_country":   {"type": "STRING"},
                "shipper_tax_id":    {"type": "STRING"},

                "consignee_name":    {"type": "STRING"},
                "consignee_address": {"type": "STRING"},
                "consignee_country": {"type": "STRING"},
                "consignee_tax_id":  {"type": "STRING"},

                "carrier_name":      {"type": "STRING"},
                "carrier_address":   {"type": "STRING"},
                "carrier_country":   {"type": "STRING"},

                # Транспорт
                "vehicle_number":    {"type": "STRING"},
                "trailer_number":    {"type": "STRING"},

                # Маршрут
                "loading_place":     {"type": "STRING"},
                "loading_country":   {"type": "STRING"},
                "destination_place": {"type": "STRING"},
                "destination_country": {"type": "STRING"},
                "transit_countries": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },

                # Груз
                "cargo_description": {"type": "STRING"},
                "packages_count":    {"type": "INTEGER"},
                "packaging_type":    {"type": "STRING"},
                "gross_weight_kg":   {"type": "NUMBER"},
                "volume_cbm":        {"type": "NUMBER"},
                "hs_code":           {"type": "STRING"},

                # Документы
                "document_number":   {"type": "STRING"},
                "date":              {"type": "STRING"},
                "documents_attached": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                },

                # Финансы
                "freight_cost":      {"type": "NUMBER"},
                "freight_currency":  {"type": "STRING"},
                "incoterms":         {"type": "STRING"},

                # Подписи
                "shipper_signed":    {"type": "BOOLEAN"},
                "carrier_signed":    {"type": "BOOLEAN"},
                "consignee_signed":  {"type": "BOOLEAN"},
            },
            "required": [
                "shipper_name", "shipper_country",
                "consignee_name", "consignee_country",
                "loading_country", "destination_country",
                "cargo_description", "gross_weight_kg",
                "packages_count", "date",
            ],
        }

    @property
    def SYSTEM_PROMPT(self) -> str:
        return """You are an expert auditor of CMR (Convention on the Contract for the
International Carriage of Goods by Road) documents.

CRITICAL CMR STRUCTURE RULES:
- Box 1  → ALWAYS the Sender/Shipper (отправитель)
- Box 2  → ALWAYS the Consignee/Recipient (получатель)
- Box 16 → ALWAYS the Carrier (перевозчик)
- Box 4  → Place of loading
- Box 5  → Place of delivery/destination
- Box 6  → Attached documents list

EXTRACTION RULES:
1. Translate ALL text to English.
2. Countries: extract as ISO 3166-1 alpha-2 code (DE, TR, PL, etc.)
   If you see "Germany" → "DE", "Turkey" → "TR", "Poland" → "PL"
3. HS codes: digits ONLY — remove all dots, spaces, dashes.
4. Tax IDs: look for VAT, EORI, KVK, INN, VOEN numbers near company names.
5. Dates: convert to ISO format YYYY-MM-DD.
6. Weights: always in KG. Convert tonnes (1t = 1000kg).
7. Vehicle numbers: extract tractor plate AND trailer plate separately.
8. Documents attached: list ALL mentioned documents (Invoice, EUR.1, T1, etc.)
9. If a field is not found → return empty string "" or 0. NEVER guess."""
