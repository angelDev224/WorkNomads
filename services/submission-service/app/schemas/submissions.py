import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

VALID_GENDERS = {"male", "female", "non-binary", "prefer_not_to_say"}

# ISO 3166-1 alpha-2 (abbreviated set; extend as needed)
VALID_COUNTRIES = {
    "AD",
    "AE",
    "AF",
    "AG",
    "AL",
    "AM",
    "AO",
    "AR",
    "AT",
    "AU",
    "AZ",
    "BA",
    "BB",
    "BD",
    "BE",
    "BF",
    "BG",
    "BH",
    "BI",
    "BJ",
    "BN",
    "BO",
    "BR",
    "BS",
    "BT",
    "BW",
    "BY",
    "BZ",
    "CA",
    "CD",
    "CF",
    "CG",
    "CH",
    "CI",
    "CL",
    "CM",
    "CN",
    "CO",
    "CR",
    "CU",
    "CV",
    "CY",
    "CZ",
    "DE",
    "DJ",
    "DK",
    "DM",
    "DO",
    "DZ",
    "EC",
    "EE",
    "EG",
    "ER",
    "ES",
    "ET",
    "FI",
    "FJ",
    "FM",
    "FR",
    "GA",
    "GB",
    "GD",
    "GE",
    "GH",
    "GM",
    "GN",
    "GQ",
    "GR",
    "GT",
    "GW",
    "GY",
    "HN",
    "HR",
    "HT",
    "HU",
    "ID",
    "IE",
    "IL",
    "IN",
    "IQ",
    "IR",
    "IS",
    "IT",
    "JM",
    "JO",
    "JP",
    "KE",
    "KG",
    "KH",
    "KI",
    "KM",
    "KN",
    "KP",
    "KR",
    "KW",
    "KZ",
    "LA",
    "LB",
    "LC",
    "LI",
    "LK",
    "LR",
    "LS",
    "LT",
    "LU",
    "LV",
    "LY",
    "MA",
    "MC",
    "MD",
    "ME",
    "MG",
    "MH",
    "MK",
    "ML",
    "MM",
    "MN",
    "MR",
    "MT",
    "MU",
    "MV",
    "MW",
    "MX",
    "MY",
    "MZ",
    "NA",
    "NE",
    "NG",
    "NI",
    "NL",
    "NO",
    "NP",
    "NR",
    "NZ",
    "OM",
    "PA",
    "PE",
    "PG",
    "PH",
    "PK",
    "PL",
    "PT",
    "PW",
    "PY",
    "QA",
    "RO",
    "RS",
    "RU",
    "RW",
    "SA",
    "SB",
    "SC",
    "SD",
    "SE",
    "SG",
    "SI",
    "SK",
    "SL",
    "SM",
    "SN",
    "SO",
    "SR",
    "SS",
    "ST",
    "SV",
    "SY",
    "SZ",
    "TD",
    "TG",
    "TH",
    "TJ",
    "TL",
    "TM",
    "TN",
    "TO",
    "TR",
    "TT",
    "TV",
    "TZ",
    "UA",
    "UG",
    "US",
    "UY",
    "UZ",
    "VA",
    "VC",
    "VE",
    "VN",
    "VU",
    "WS",
    "YE",
    "ZA",
    "ZM",
    "ZW",
}


class SubmissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    age: int = Field(ge=18, le=120)
    place_of_living: str = Field(min_length=1, max_length=255)
    gender: str
    country_of_origin: str = Field(min_length=2, max_length=2)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in VALID_GENDERS:
            raise ValueError(f"gender must be one of {VALID_GENDERS}")
        return v

    @field_validator("country_of_origin")
    @classmethod
    def validate_country(cls, v: str) -> str:
        upper = v.upper()
        if upper not in VALID_COUNTRIES:
            raise ValueError(f"'{v}' is not a valid ISO 3166-1 alpha-2 country code")
        return upper


class ResultResponse(BaseModel):
    label: str
    confidence: Optional[float]
    classifier_version: str
    classified_at: datetime

    model_config = {"from_attributes": True}


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: int
    place_of_living: str
    gender: str
    country_of_origin: str
    description: Optional[str]
    photo_url: Optional[str] = None
    status: str
    result: Optional[ResultResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionListResponse(BaseModel):
    data: list[SubmissionResponse]
    total: int
    page: int
    per_page: int
