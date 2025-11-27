from pydantic import BaseModel

from firedantic import Model, AsyncModel


class MyModel(AsyncModel):
        pass


class BillingAccount(BaseModel):
    """Dummy billing account Pydantic model."""
    __db_config__ = "billing"
    __collection__ = "billing_accounts"
    name: str
    billing_id: int
    owner: str


class BillingCompany(Model):
    """Dummy company Firedantic model."""
    __db_config__ = "billing"
    __collection__ = "billing_companies"
    company_id: str
    billing_account: BillingAccount
