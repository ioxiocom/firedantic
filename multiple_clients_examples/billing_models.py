from pydantic import BaseModel

from firedantic import Model


class BillingAccount(BaseModel):
    """Dummy billing account Pydantic model."""

    name: str
    billing_id: str
    owner: str


class BillingCompany(Model):
    """Dummy company Firedantic model."""

    __collection__ = "billing_companies"
    company_id: str
    billing_account: BillingAccount
