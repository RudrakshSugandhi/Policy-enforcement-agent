from uuid import UUID
from pydantic import BaseModel


class GetTransactionInput(BaseModel):
    transaction_id: UUID


class GetTransactionOutput(BaseModel):
    transaction_id: UUID
    tenant_id: str
    employee_id: str
    amount: str          # kept as string for JSON transport (Decimal serialises cleanly)
    currency: str
    merchant_name: str
    mcc_code: str
    timestamp: str
    vendor_id: str | None = None
    card_id: str
    description: str | None = None
