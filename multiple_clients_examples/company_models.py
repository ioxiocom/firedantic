from pydantic import BaseModel

from firedantic import Model


class Owner(BaseModel):
    """Dummy owner Pydantic model."""
    __db_config__ = "owners"
    __collection__ = "owners"
    first_name: str
    last_name: str


class Company(Model):
    """Dummy company Firedantic model."""
    __db_config__ = "companies"
    __collection__ = "companies"
    company_id: str
    owner: Owner
