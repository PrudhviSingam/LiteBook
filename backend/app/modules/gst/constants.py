from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

# Indian State Codes as defined by the GST Council
INDIAN_STATE_CODES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# Standard GST Tax Rates
VALID_GST_RATES = [
    Decimal("0.00"),
    Decimal("0.10"),
    Decimal("0.25"),
    Decimal("1.50"),
    Decimal("3.00"),
    Decimal("5.00"),
    Decimal("6.00"),
    Decimal("12.00"),
    Decimal("18.00"),
    Decimal("28.00"),
]

# Invoice Types for GSTR-1
GSTR1_INVOICE_TYPES = {
    "B2B": "Regular B2B Supply to Registered Taxpayer",
    "B2CL": "B2C Large (Inter-state supply > 2.5 Lakhs to unregistered person)",
    "B2CS": "B2C Small (Intra-state or Inter-state <= 2.5 Lakhs)",
    "EXPORT": "Zero-rated Export Supply (With or without payment of tax)",
    "CDNR": "Credit / Debit Note to Registered Recipient",
    "CDNUR": "Credit / Debit Note to Unregistered Recipient",
    "NIL_EXEMPT": "Nil Rated, Exempt, and Non-GST Supplies",
}

# Workflow status transitions
PERIOD_STATUSES = ["draft", "under_review", "approved", "filed", "locked"]

# Reconciliation match types
RECON_MATCH_TYPES = [
    "EXACT_MATCH",
    "PARTIAL_MATCH",
    "BOOKS_ONLY",
    "RETURN_ONLY",
    "EXCLUDED",
]


class PeriodStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    FILED = "filed"
    LOCKED = "locked"


class MatchStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    BOOKS_ONLY = "BOOKS_ONLY"
    RETURN_ONLY = "RETURN_ONLY"
    EXCLUDED = "EXCLUDED"


class DifferenceReason(str, Enum):
    ROUNDING_DIFFERENCE = "ROUNDING_DIFFERENCE"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TAX_RATE_MISMATCH = "TAX_RATE_MISMATCH"
    INVOICE_NUMBER_TYPO = "INVOICE_NUMBER_TYPO"
    DATE_OUT_OF_PERIOD = "DATE_OUT_OF_PERIOD"
    MISSING_IN_GSTR2B = "MISSING_IN_GSTR2B"
    MISSING_IN_BOOKS = "MISSING_IN_BOOKS"


class ReconciliationDecision(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FORCE_MATCH = "FORCE_MATCH"


def round_currency(val: Decimal) -> Decimal:
    """Rounds a Decimal value to 2 decimal places using Indian accounting ROUND_HALF_UP."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
