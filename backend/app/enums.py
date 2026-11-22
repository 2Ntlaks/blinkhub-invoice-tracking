"""Fixed vocabularies shared by the rules, the database models and the API schemas.

They are `StrEnum`s so the value stored in the database and sent over JSON is the
same plain string the API contract uses (for example ``"SUBMITTED"``).
"""

from enum import StrEnum


class Role(StrEnum):
    SUPPLIER = "SUPPLIER"
    FINANCE = "FINANCE"
    MANAGER = "MANAGER"


class SupplierType(StrEnum):
    SMME = "SMME"
    LARGE = "LARGE"


class SupplierStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class InvoiceStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    PAID = "PAID"
    REJECTED = "REJECTED"


class InvoiceAction(StrEnum):
    """The three things a finance officer can do to an invoice."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    PAY = "PAY"


class FlagRule(StrEnum):
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    PO_OVER_INVOICED = "PO_OVER_INVOICED"


class FlagStatus(StrEnum):
    OPEN = "OPEN"
    CLEARED = "CLEARED"
    CONFIRMED = "CONFIRMED"


class AuditAction(StrEnum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    FLAG_RAISED = "FLAG_RAISED"
    FLAG_CLEARED = "FLAG_CLEARED"
    FLAG_CONFIRMED = "FLAG_CONFIRMED"


class ErrorCode(StrEnum):
    """Error codes from section 2 of the API contract."""

    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PO_NOT_FOUND = "PO_NOT_FOUND"
    PO_SUPPLIER_MISMATCH = "PO_SUPPLIER_MISMATCH"
    SUPPLIER_INACTIVE = "SUPPLIER_INACTIVE"
    AMOUNT_EXCEEDS_PO = "AMOUNT_EXCEEDS_PO"
    DUPLICATE_INVOICE_NUMBER = "DUPLICATE_INVOICE_NUMBER"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    FLAGS_UNRESOLVED = "FLAGS_UNRESOLVED"
    FLAG_ALREADY_RESOLVED = "FLAG_ALREADY_RESOLVED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# HTTP status for each error code. Kept next to the codes so the mapping in the
# contract table (section 2) can be checked against one place.
HTTP_STATUS_FOR_CODE: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.PO_NOT_FOUND: 422,
    ErrorCode.PO_SUPPLIER_MISMATCH: 422,
    ErrorCode.SUPPLIER_INACTIVE: 422,
    ErrorCode.AMOUNT_EXCEEDS_PO: 422,
    ErrorCode.DUPLICATE_INVOICE_NUMBER: 409,
    ErrorCode.INVALID_STATUS_TRANSITION: 409,
    ErrorCode.FLAGS_UNRESOLVED: 409,
    ErrorCode.FLAG_ALREADY_RESOLVED: 409,
    ErrorCode.INTERNAL_ERROR: 500,
}
