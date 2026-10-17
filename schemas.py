from datetime import datetime, timezone
import re
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


RESERVED_CODES = {"api", "docs", "redoc", "openapi.json", "static", "favicon.ico", "health"}


class ShortURLCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = None
    custom_description: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) < 3 or len(v) > 32:
            raise ValueError("사용자 지정 코드는 3자 이상 32자 이하로 입력해 주세요.")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("사용자 지정 코드는 영문, 숫자, 하이픈(-), 언더바(_)만 사용할 수 있습니다.")
        if v.lower() in RESERVED_CODES:
            raise ValueError(f"'{v}'는 시스템 예약어로 사용할 수 없습니다.")
        return v

    @field_validator("custom_description")
    @classmethod
    def validate_custom_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v[:2000] if v else None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("만료 일시는 현재 시각 이후여야 합니다.")
        return v


class ShortURLUpdateDescription(BaseModel):
    custom_description: Optional[str] = None

    @field_validator("custom_description")
    @classmethod
    def validate_custom_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v[:2000] if v else None


class ShortURLResponse(BaseModel):
    id: int
    short_code: str
    short_url: str
    original_url: str
    custom_description: Optional[str] = None
    clicks: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_expired: bool
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_image: Optional[str] = None
    favicon_url: Optional[str] = None
    meta_updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
