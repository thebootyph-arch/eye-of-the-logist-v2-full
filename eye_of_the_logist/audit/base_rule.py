"""
Base classes for all audit rules.
Every rule returns an AuditResult. Nothing else.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    INFO     = "INFO"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"   # документ отсутствует или поле не применимо


SEVERITY_SCORE: dict[Severity, int] = {
    Severity.CRITICAL : -25,
    Severity.HIGH     : -10,
    Severity.MEDIUM   :  -5,
    Severity.LOW      :  -2,
    Severity.INFO     :   0,
}


@dataclass
class AuditResult:
    rule_id     : str                    # "B004"
    rule_name   : str                    # "Gross Weight Match"
    group       : str                    # "B"
    status      : Status
    severity    : Severity
    score_impact: int                    # 0 если PASS или SKIP
    message     : str                    # человекочитаемое объяснение
    documents   : list[str] = field(default_factory=list)  # ["CMR","INVOICE"]
    detail      : Optional[dict] = None  # сырые значения для дебага

    @classmethod
    def passed(cls, rule_id: str, rule_name: str, group: str,
               message: str, documents: list[str]) -> "AuditResult":
        return cls(
            rule_id=rule_id, rule_name=rule_name, group=group,
            status=Status.PASS, severity=Severity.INFO,
            score_impact=0, message=message, documents=documents,
        )

    @classmethod
    def failed(cls, rule_id: str, rule_name: str, group: str,
               severity: Severity, message: str,
               documents: list[str], detail: Optional[dict] = None) -> "AuditResult":
        return cls(
            rule_id=rule_id, rule_name=rule_name, group=group,
            status=Status.FAIL, severity=severity,
            score_impact=SEVERITY_SCORE[severity],
            message=message, documents=documents, detail=detail,
        )

    @classmethod
    def skipped(cls, rule_id: str, rule_name: str, group: str,
                message: str) -> "AuditResult":
        return cls(
            rule_id=rule_id, rule_name=rule_name, group=group,
            status=Status.SKIP, severity=Severity.INFO,
            score_impact=0, message=message, documents=[],
        )


class BaseRule:
    """
    Наследуй этот класс для каждого правила.
    Переопредели только метод check().
    """
    rule_id  : str = "X000"
    rule_name: str = "Unnamed Rule"
    group    : str = "X"

    def check(self, state: "PipelineState") -> AuditResult:  # noqa: F821
        raise NotImplementedError
