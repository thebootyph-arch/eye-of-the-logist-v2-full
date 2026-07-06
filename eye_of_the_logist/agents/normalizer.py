"""
Normalizer — приводит данные из трёх парсеров к единому виду.
Проблема: "Germany" = "DE" = "Federal Republic of Germany" = "Deutschland"
Решение: нормализация в PipelineState.normalized (NormalizedData)
"""
import re
from datetime import datetime
from state.pipeline_state import PipelineState, NormalizedData

# ── Справочники ────────────────────────────────────────────────────────────

COUNTRY_MAP: dict[str, str] = {
    # Полные названия → ISO alpha-2
    "germany": "DE", "deutschland": "DE", "federal republic of germany": "DE",
    "turkey": "TR", "turkiye": "TR", "türkiye": "TR", "republic of turkey": "TR",
    "france": "FR", "republic of france": "FR", "frankreich": "FR",
    "poland": "PL", "polska": "PL", "republic of poland": "PL",
    "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "belgium": "BE", "belgique": "BE", "belgië": "BE",
    "austria": "AT", "österreich": "AT", "republic of austria": "AT",
    "czech republic": "CZ", "czechia": "CZ", "czech": "CZ",
    "hungary": "HU", "magyarország": "HU",
    "romania": "RO", "românia": "RO",
    "bulgaria": "BG", "republic of bulgaria": "BG",
    "slovakia": "SK", "slovak republic": "SK",
    "italy": "IT", "italia": "IT", "italian republic": "IT",
    "spain": "ES", "españa": "ES", "kingdom of spain": "ES",
    "ukraine": "UA", "україна": "UA",
    "russia": "RU", "russian federation": "RU", "россия": "RU",
    "belarus": "BY", "republic of belarus": "BY",
    "georgia": "GE", "საქართველო": "GE",
    "azerbaijan": "AZ", "republic of azerbaijan": "AZ",
    "kazakhstan": "KZ", "republic of kazakhstan": "KZ",
    "uzbekistan": "UZ", "republic of uzbekistan": "UZ",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "united states": "US", "usa": "US", "united states of america": "US",
    "china": "CN", "people's republic of china": "CN", "prc": "CN",
    "india": "IN", "republic of india": "IN",
    "iran": "IR", "islamic republic of iran": "IR",
    "north korea": "KP", "democratic people's republic of korea": "KP",
    "syria": "SY", "syrian arab republic": "SY",
    "cuba": "CU", "republic of cuba": "CU",
    "venezuela": "VE", "bolivarian republic of venezuela": "VE",
}

INCOTERMS_MAP: dict[str, str] = {
    "exw": "EXW", "ex works": "EXW", "ex-works": "EXW",
    "fca": "FCA", "free carrier": "FCA",
    "fas": "FAS", "free alongside ship": "FAS",
    "fob": "FOB", "free on board": "FOB",
    "cfr": "CFR", "cost and freight": "CFR", "c&f": "CFR", "cnf": "CFR",
    "cif": "CIF", "cost insurance freight": "CIF",
    "cpt": "CPT", "carriage paid to": "CPT",
    "cip": "CIP", "carriage and insurance paid": "CIP",
    "dap": "DAP", "delivered at place": "DAP",
    "dpu": "DPU", "delivered at place unloaded": "DPU",
    "dat": "DPU",  # старый термин DAT = новый DPU
    "ddp": "DDP", "delivered duty paid": "DDP",
    "ddu": "DAP",  # устаревший DDU ≈ DAP
}

CURRENCY_MAP: dict[str, str] = {
    "euro": "EUR", "euros": "EUR", "eur": "EUR", "€": "EUR",
    "dollar": "USD", "dollars": "USD", "usd": "USD", "$": "USD",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "£": "GBP",
    "lira": "TRY", "turkish lira": "TRY", "try": "TRY", "tl": "TRY",
    "ruble": "RUB", "rubles": "RUB", "rub": "RUB", "руб": "RUB",
    "zloty": "PLN", "pln": "PLN", "zł": "PLN",
    "yuan": "CNY", "renminbi": "CNY", "cny": "CNY", "rmb": "CNY",
    "hryvnia": "UAH", "uah": "UAH",
}

DATE_FORMATS = [
    "%Y-%m-%d",   # ISO: 2024-01-15
    "%d.%m.%Y",   # EU:  15.01.2024
    "%d/%m/%Y",   # UK:  15/01/2024
    "%m/%d/%Y",   # US:  01/15/2024
    "%d-%m-%Y",   # dashed: 15-01-2024
    "%B %d, %Y",  # January 15, 2024
    "%d %B %Y",   # 15 January 2024
    "%b %d, %Y",  # Jan 15, 2024
    "%d %b %Y",   # 15 Jan 2024
]


# ── Normalizer class ───────────────────────────────────────────────────────

class Normalizer:

    def normalize(self, state: PipelineState) -> NormalizedData:
        """
        Читает raw dicts из state, заполняет NormalizedData.
        Приоритет: если поле есть в нескольких документах,
        берём наиболее полное/надёжное значение.
        """
        cmr = state.cmr_raw
        inv = state.invoice_raw
        pl  = state.packing_list_raw

        n = NormalizedData()

        # ── Стороны ───────────────────────────────────────────────
        n.shipper_name    = self._str(cmr.get("shipper_name"))
        n.shipper_country = self._country(cmr.get("shipper_country"))
        n.shipper_tax_id  = self._str(cmr.get("shipper_tax_id"))

        n.consignee_name    = self._str(cmr.get("consignee_name"))
        n.consignee_country = self._country(cmr.get("consignee_country"))
        n.consignee_tax_id  = self._str(cmr.get("consignee_tax_id"))

        n.seller_name    = self._str(inv.get("seller_name"))
        n.seller_country = self._country(inv.get("seller_country"))
        n.seller_vat_id  = self._str(inv.get("seller_vat_id"))

        n.buyer_name    = self._str(inv.get("buyer_name"))
        n.buyer_country = self._country(inv.get("buyer_country"))
        n.buyer_tax_id  = self._str(inv.get("buyer_tax_id"))

        # ── Маршрут ───────────────────────────────────────────────
        n.loading_country     = self._country(cmr.get("loading_country"))
        n.destination_country = self._country(cmr.get("destination_country"))
        n.transit_countries   = [
            self._country(c)
            for c in cmr.get("transit_countries", [])
            if c
        ]

        # ── Груз: приоритет PL > CMR для физических параметров ───
        n.cargo_description = (
            self._str(inv.get("line_items", [{}])[0].get("description"))
            or self._str(cmr.get("cargo_description"))
        )
        n.hs_code = self._hs_code(
            inv.get("hs_code")
            or cmr.get("hs_code")
            or pl.get("hs_code")
        )
        n.packages_count  = self._int(pl.get("total_packages") or cmr.get("packages_count"))
        n.gross_weight_kg = self._weight(
            pl.get("total_gross_weight_kg") or cmr.get("gross_weight_kg")
        )
        n.net_weight_kg   = self._weight(
            pl.get("total_net_weight_kg") or inv.get("net_weight_kg")
        )
        n.volume_cbm      = self._float(
            pl.get("total_volume_cbm") or cmr.get("volume_cbm")
        )

        # ── Финансы ───────────────────────────────────────────────
        fin = inv.get("financials", {})
        n.total_value  = self._float(fin.get("total_value") or inv.get("total_value"))
        n.currency     = self._currency(fin.get("currency") or inv.get("currency"))
        n.incoterms    = self._incoterms(
            inv.get("incoterms")
            or fin.get("incoterms")
            or cmr.get("incoterms")
        )

        if n.gross_weight_kg > 0 and n.total_value > 0:
            n.price_per_kg = round(n.total_value / n.gross_weight_kg, 4)

        # ── Даты ──────────────────────────────────────────────────
        n.cmr_date     = self._date(cmr.get("date"))
        n.invoice_date = self._date(inv.get("date"))

        # ── Ссылка на инвойс в CMR ────────────────────────────────
        inv_num       = self._str(inv.get("document_number"))
        docs_attached = cmr.get("documents_attached", [])
        n.invoice_number_in_cmr = bool(
            inv_num and any(inv_num.lower() in d.lower() for d in docs_attached)
        )

        # ── Транспорт ─────────────────────────────────────────────
        n.carrier_name   = self._str(cmr.get("carrier_name"))
        n.vehicle_number = self._str(cmr.get("vehicle_number"))

        n.all_documents_present = (
            bool(state.cmr_raw) and
            bool(state.invoice_raw) and
            bool(state.packing_list_raw)
        )

        return n

    # ── Конвертеры ────────────────────────────────────────────────────────

    @staticmethod
    def _str(val) -> str:
        if val is None:
            return ""
        return str(val).strip()

    @staticmethod
    def _int(val) -> int:
        try:
            return int(float(str(val).replace(",", ".")))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _float(val) -> float:
        try:
            return float(str(val).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    def _weight(self, val) -> float:
        """Всегда в кг. Автоопределяет тонны если значение < 100."""
        raw = self._float(val)
        # Эвристика: если вес < 100, скорее всего тонны
        if 0 < raw < 100:
            return raw * 1000
        return raw

    def _country(self, val) -> str:
        """Нормализует страну в ISO alpha-2."""
        if not val:
            return ""
        s = str(val).strip()
        # Уже ISO alpha-2
        if len(s) == 2 and s.isalpha():
            return s.upper()
        # Ищем в справочнике
        key = s.lower()
        if key in COUNTRY_MAP:
            return COUNTRY_MAP[key]
        # Пробуем убрать лишнее и найти подстроку
        for k, v in COUNTRY_MAP.items():
            if k in key or key in k:
                return v
        # Fallback: первые 2 буквы заглавными
        return s[:2].upper()

    def _hs_code(self, val) -> str:
        """Только цифры, минимум 6."""
        if not val:
            return ""
        digits = re.sub(r"[^0-9]", "", str(val))
        return digits

    def _date(self, val) -> str:
        """Нормализует дату в ISO YYYY-MM-DD."""
        if not val:
            return ""
        s = str(val).strip()
        # Уже ISO
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s  # вернём как есть если не распознали

    def _currency(self, val) -> str:
        """Нормализует валюту в ISO 4217."""
        if not val:
            return ""
        s = str(val).strip()
        key = s.lower()
        if key in CURRENCY_MAP:
            return CURRENCY_MAP[key]
        # Уже ISO (3 буквы)
        if len(s) == 3 and s.isalpha():
            return s.upper()
        return s.upper()

    def _incoterms(self, val) -> str:
        """Нормализует Incoterms в официальный 3-буквенный код."""
        if not val:
            return ""
        s = str(val).strip()
        key = s.lower()
        if key in INCOTERMS_MAP:
            return INCOTERMS_MAP[key]
        # Уже 3 буквы
        if len(s) == 3 and s.isalpha():
            return s.upper()
        return s.upper()
