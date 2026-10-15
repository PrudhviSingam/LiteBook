import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.modules.reconciliation.schemas import (
    CorrectionProposalSchema,
    CorrectionStatusEnum,
)
from app.modules.reconciliation.workbook_inspector import (
    format_indian_currency,
    parse_indian_currency,
)


class CorrectionProposalFactory:
    """Creates standardized CorrectionProposal objects for accountant review."""

    @staticmethod
    def create(
        session_id: int,
        sheet_name: str,
        row_reference: Any,
        field: str,
        original_value: Any,
        proposed_value: Any,
        reason_category: str,
        explanation: str,
        evidence: Optional[List[str]] = None,
        recommended_verification: Optional[List[str]] = None,
        confidence: str = "HIGH",
        document_id: Optional[int] = None,
        correction_id: Optional[str] = None,
    ) -> CorrectionProposalSchema:
        orig_num = parse_indian_currency(original_value) or 0.0
        prop_num = parse_indian_currency(proposed_value) or 0.0
        diff = round(prop_num - orig_num, 2)

        cid = correction_id or f"COR-{uuid.uuid4().hex[:6].upper()}"

        return CorrectionProposalSchema(
            correction_id=cid,
            session_id=session_id,
            document_id=document_id,
            sheet_name=sheet_name,
            row_reference=row_reference,
            field=field,
            original_value=orig_num,
            proposed_value=prop_num,
            difference=diff,
            reason_category=reason_category,
            explanation=explanation,
            evidence=evidence or [],
            recommended_verification=recommended_verification or [],
            confidence=confidence,
            status=CorrectionStatusEnum.PROPOSED.value,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
