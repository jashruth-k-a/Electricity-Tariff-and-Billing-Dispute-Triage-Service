from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    domestic = "domestic"
    commercial = "commercial"
    industrial = "industrial"
    agricultural = "agricultural"
    unknown = "unknown"


class Dispute(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    state: str = Field(default="Karnataka", min_length=2, max_length=60)
    connection_type: Literal["LT", "HT", "EHT"] = "LT"
    billed_category: Category
    premises_use: Literal["residential", "commercial", "industrial", "agricultural", "mixed", "unknown"]
    description: str = Field(min_length=15, max_length=4000)
    connected_load_kw: float = Field(gt=0, le=10000, allow_inf_nan=False)
    sanctioned_load_kw: float = Field(gt=0, le=10000, allow_inf_nan=False)
    billing_date: date
    business_activity: str | None = Field(default=None, min_length=2, max_length=200)
    business_area_sqm: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    total_area_sqm: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    separate_meter: bool | None = None

    @model_validator(mode="after")
    def consistency(self):
        if self.premises_use == "mixed" and not self.business_activity:
            raise ValueError("business_activity is required for mixed premises")
        if self.business_area_sqm is not None and self.total_area_sqm is None:
            raise ValueError("total_area_sqm is required with business_area_sqm")
        if (self.business_area_sqm is not None and self.total_area_sqm is not None
                and self.business_area_sqm > self.total_area_sqm):
            raise ValueError("business_area_sqm cannot exceed total_area_sqm")
        if self.billing_date > date.today():
            raise ValueError("billing_date cannot be in the future")
        return self


class Citation(BaseModel):
    chunk_id: str
    quote: str = Field(min_length=10)
    document: str
    clause: str
    page: int
    source_url: str


class Claim(BaseModel):
    statement: str = Field(min_length=5, max_length=2000)
    chunk_ids: list[str] = Field(min_length=1, max_length=8)


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: Literal["bill-stands-with-reason", "revision-recommended", "site-inspection-required"]
    tariff_position: str = Field(min_length=10, max_length=4000)
    claims: list[Claim] = Field(min_length=1, max_length=8)
    citations: list[Citation] = Field(min_length=1, max_length=12)
    escalation_required: bool
    escalation_reason: str = Field(max_length=2000)
    issue_type: Literal["tariff-category", "meter-accuracy", "load-violation", "arrears", "disconnection"]


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    satisfactory: bool
    reason: str = Field(min_length=3, max_length=1000)


class VerifyRequest(BaseModel):
    run_id: str
    request: dict
    candidate: dict
    passages: list[dict]
    prompt_version: str
    deadline: float
    steps_remaining: int = Field(ge=1, le=20)


class Verification(BaseModel):
    supported: bool
    reasons: list[str]
    retry_query: str = ""
