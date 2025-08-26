from pydantic import BaseModel

from firedantic import Model


class Owner(BaseModel):
    """Dummy owner Pydantic model."""

    first_name: str
    last_name: str


class Company(Model):
    """Dummy company Firedantic model."""

    __collection__ = "companies"
    company_id: str
    owner: Owner
