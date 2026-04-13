from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationSeverity(str, Enum):
    error = "error"
    warning = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: ValidationSeverity
    message: str
    source: Optional[str] = None
    context: Optional[str] = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        *,
        source: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=ValidationSeverity.error,
                message=message,
                source=source,
                context=context,
            )
        )

    def add_warning(
        self,
        message: str,
        *,
        source: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=ValidationSeverity.warning,
                message=message,
                source=source,
                context=context,
            )
        )

    def merge(self, other: ValidationResult) -> None:
        self.issues.extend(list(other.issues))

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is ValidationSeverity.error for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity is ValidationSeverity.warning for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity is ValidationSeverity.error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity is ValidationSeverity.warning]

    @property
    def error_summary(self) -> str | None:
        error_messages = [issue.message for issue in self.errors]
        if not error_messages:
            return None
        return "; ".join(error_messages)

    def warnings_as_dicts(self) -> list[dict[str, Optional[str]]]:
        return [
            {
                "message": issue.message,
                "source": issue.source,
                "context": issue.context,
            }
            for issue in self.warnings
        ]
