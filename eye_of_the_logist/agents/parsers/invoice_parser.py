"""
Invoice Parser Agent — специализирован под коммерческие инвойсы.
Извлекает все финансовые поля, line items, HS коды.
"""
from agents.parsers.base_parser import BasePDFParser, ParserConfig


class InvoiceParser(BasePDFParser):
    document_type = "INVOICE"

    @property
    def SCHEMA(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                # Реквизиты
                "document_number": {"type": "STRING"},
                "date":            {"type": "STRING"},

                # Продавец
                "seller_name":     {"type": "STRING"},
                "seller_address":  {"type": "STRING"},
                "seller_country":  {"type": "STRING"},
                "seller_vat_id":   {"type": "STRING"},
                "seller_eori":     {"type": "STRING"},

                # Покупатель
                "buyer_name":      {"type": "STRING"},
                "buyer_address":   {"type": "STRING"},
                "buyer_country":   {"type": "STRING"},
                "buyer_tax_id":    {"type": "STRING"},

                # Отгрузка
                "incoterms":           {"type": "STRING"},
                "origin_country":      {"type": "STRING"},
                "destination_country": {"type": "STRING"},
                "transport_mode":      {"type": "STRING"},

                # Позиции товара
                "line_items": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "position":       {"type": "INTEGER"},
                            "description":    {"type": "STRING"},
                            "hs_code":        {"type": "STRING"},
                            "quantity":       {"type": "NUMBER"},
                            "unit":           {"type": "STRING"},
                            "unit_price":     {"type": "NUMBER"},
                            "currency":       {"type": "STRING"},
                            "total_line":     {"type": "NUMBER"},
                            "origin_country": {"type": "STRING"},
                        },
                    },
                },

                # Финансы
                "subtotal":       {"type": "NUMBER"},
                "freight_charge": {"type": "NUMBER"},
                "insurance":      {"type": "NUMBER"},
                "discount":       {"type": "NUMBER"},
                "total_value":    {"type": "NUMBER"},
                "currency":       {"type": "STRING"},

                # Физические параметры
                "gross_weight_kg": {"type": "NUMBER"},
                "net_weight_kg":   {"type": "NUMBER"},

                # Платёж
                "payment_terms":  {"type": "STRING"},

                # Сводный HS (если один на весь инвойс)
                "hs_code":        {"type": "STRING"},
            },
            "required": [
                "document_number", "date",
                "seller_name", "seller_country", "seller_vat_id",
                "buyer_name", "buyer_country",
                "total_value", "currency",
                "incoterms", "origin_country",
                "gross_weight_kg",
            ],
        }

    @property
    def SYSTEM_PROMPT(self) -> str:
        return """You are an expert auditor of Commercial Invoices for international trade.

EXTRACTION RULES:
1. Translate ALL text to English.
2. Countries: extract as ISO 3166-1 alpha-2 code (DE, TR, PL, etc.)
3. HS codes: digits ONLY — remove dots, spaces, dashes.
   Example: "6109.10.00" → "61091000", "61 09 10" → "610910"
4. VAT IDs: look for patterns like DE123456789, GB123456789, TR1234567890
   Also look for: EIN, Tax ID, Company Reg Number, EORI
5. Dates: convert to ISO YYYY-MM-DD.
6. Currency: ISO 4217 code (EUR, USD, TRY, etc.)
7. Incoterms: use official 3-letter codes (EXW, FOB, CIF, DAP, DDP, etc.)
8. Transport mode: ROAD / SEA / AIR / RAIL
9. Line items: extract EVERY product line separately.
   If invoice has one product type, create one line item.
10. total_value: the FINAL amount after all charges/discounts.
11. gross_weight_kg: look for "Gross Weight", "Brutto", "G.W."
12. net_weight_kg:   look for "Net Weight", "Netto", "N.W."
13. hs_code at root level: use the FIRST or MAIN hs_code found.
14. If a field is not found → return "" or 0. NEVER guess or hallucinate."""
