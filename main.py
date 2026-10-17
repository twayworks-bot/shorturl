from datetime import datetime, timedelta, timezone
import os
import secrets
import string
from typing import List, Optional
from fastapi import APIRouter, FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import DEFAULT_DB_FILE, DEFAULT_RETENTION_DAYS, ShortURL, get_db, init_db
from metadata_scraper import fetch_url_metadata
from schemas import (
    RESERVED_CODES,
    ShortURLCreate,
    ShortURLResponse,
    ShortURLUpdateDescription,
)


def normalize_prefix(raw_prefix: Optional[str]) -> str:
    if raw_prefix is None:
        raw_prefix = "/shorturl"
    cleaned = raw_prefix.strip()
    if not cleaned or cleaned == "/":
        return ""
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    return cleaned.rstrip("/")


RAW_ENV_PREFIX = os.getenv("DEFAULT_PREFIX", os.getenv("DEFAUL_PREFIX", "/shorturl"))
BASE_PREFIX = normalize_prefix(RAW_ENV_PREFIX)

app = FastAPI(
    title="ShortURL Service",
    description="긴 URL을 단축 링크로 변환하고 프리뷰 메타정보(OG 태그 및 사용자 설명) 제공과 동시에 즉시 타겟 링크로 전환하는 서비스",
    version="2.3.0",
    docs_url=f"{BASE_PREFIX}/docs" if BASE_PREFIX else "/docs",
    redoc_url=f"{BASE_PREFIX}/redoc" if BASE_PREFIX else "/redoc",
    openapi_url=f"{BASE_PREFIX}/openapi.json" if BASE_PREFIX else "/openapi.json",
)

init_db()

templates = Jinja2Templates(directory="templates")
static_mount_path = f"{BASE_PREFIX}/static" if BASE_PREFIX else "/static"
app.mount(static_mount_path, StaticFiles(directory="static"), name="static")
if BASE_PREFIX:
    # Also mount at /static as fallback
    app.mount("/static", StaticFiles(directory="static"), name="static_root")

ALPHABET = string.ascii_letters + string.digits
prefix_segment = BASE_PREFIX.lstrip("/").lower()


def generate_unique_code(db: Session, length: int = 6) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if code.lower() in RESERVED_CODES or (prefix_segment and code.lower() == prefix_segment):
            continue
        exists = db.query(ShortURL).filter(ShortURL.short_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="단축 코드 생성에 실패했습니다. 다시 시도해 주세요.")


def check_is_expired(item: ShortURL) -> bool:
    if not item.expires_at:
        return False
    exp = item.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc)


def resolve_effective_description(custom_desc: Optional[str], scraped_desc: Optional[str]) -> Optional[str]:
    if custom_desc and custom_desc.strip():
        return custom_desc.strip()
    return scraped_desc


def to_response(item: ShortURL, request: Request) -> ShortURLResponse:
    base_url = str(request.base_url).rstrip("/")
    created = item.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    expires = item.expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    meta_updated = item.meta_updated_at
    if meta_updated and meta_updated.tzinfo is None:
        meta_updated = meta_updated.replace(tzinfo=timezone.utc)

    effective_desc = resolve_effective_description(item.custom_description, item.meta_description)

    return ShortURLResponse(
        id=item.id,
        short_code=item.short_code,
        short_url=f"{base_url}{BASE_PREFIX}/{item.short_code}",
        original_url=item.original_url,
        custom_description=item.custom_description,
        clicks=item.clicks,
        created_at=created,
        expires_at=expires,
        is_expired=check_is_expired(item),
        meta_title=item.meta_title,
        meta_description=effective_desc,
        meta_image=item.meta_image,
        favicon_url=item.favicon_url,
        meta_updated_at=meta_updated,
    )


router = APIRouter(prefix=BASE_PREFIX)


@router.get("/api/status")
def get_api_status():
    return {
        "status": "ok",
        "service": "ShortURL Service",
        "prefix": BASE_PREFIX or "/",
        "db_file": DEFAULT_DB_FILE,
    }


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def read_dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"base_prefix": BASE_PREFIX},
    )


@router.post("/api/urls", response_model=ShortURLResponse, status_code=status.HTTP_201_CREATED)
def create_short_url(payload: ShortURLCreate, request: Request, db: Session = Depends(get_db)):
    if payload.custom_alias:
        if prefix_segment and payload.custom_alias.lower() == prefix_segment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{payload.custom_alias}'는 기본 프리픽스 경로와 동일하여 사용할 수 없습니다.",
            )
        existing = db.query(ShortURL).filter(ShortURL.short_code == payload.custom_alias).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"이미 사용 중인 단축 코드입니다: '{payload.custom_alias}'",
            )
        short_code = payload.custom_alias
    else:
        short_code = generate_unique_code(db)

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at or (now + timedelta(days=DEFAULT_RETENTION_DAYS))
    original_url_str = str(payload.original_url)

    meta = fetch_url_metadata(original_url_str)
    effective_desc = resolve_effective_description(
        payload.custom_description, meta.get("meta_description")
    )

    db_obj = ShortURL(
        short_code=short_code,
        original_url=original_url_str,
        custom_description=payload.custom_description,
        created_at=now,
        expires_at=expires_at,
        meta_title=meta.get("meta_title"),
        meta_description=effective_desc,
        meta_image=meta.get("meta_image"),
        favicon_url=meta.get("favicon_url"),
        meta_updated_at=meta.get("meta_updated_at"),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return to_response(db_obj, request)


@router.get("/api/urls", response_model=List[ShortURLResponse])
def list_short_urls(
    request: Request,
    q: Optional[str] = Query(default=None, description="단축 코드, 원본 URL, 사용자 설명, 메타 제목/설명 검색어"),
    db: Session = Depends(get_db),
):
    query = db.query(ShortURL)
    if q and q.strip():
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ShortURL.short_code.ilike(keyword),
                ShortURL.original_url.ilike(keyword),
                ShortURL.custom_description.ilike(keyword),
                ShortURL.meta_title.ilike(keyword),
                ShortURL.meta_description.ilike(keyword),
            )
        )
    items = query.order_by(ShortURL.created_at.desc(), ShortURL.id.desc()).all()
    return [to_response(item, request) for item in items]


@router.get("/api/urls/{short_code}", response_model=ShortURLResponse)
def get_short_url_info(short_code: str, request: Request, db: Session = Depends(get_db)):
    item = db.query(ShortURL).filter(ShortURL.short_code == short_code).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단축 링크를 찾을 수 없습니다.")
    return to_response(item, request)


@router.patch("/api/urls/{short_code}/description", response_model=ShortURLResponse)
def update_short_url_description(
    short_code: str,
    payload: ShortURLUpdateDescription,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(ShortURL).filter(ShortURL.short_code == short_code).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단축 링크를 찾을 수 없습니다.")

    item.custom_description = payload.custom_description
    if payload.custom_description:
        item.meta_description = payload.custom_description
    else:
        meta = fetch_url_metadata(item.original_url)
        item.meta_description = meta.get("meta_description")

    item.meta_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return to_response(item, request)


@router.post("/api/urls/{short_code}/refresh-meta", response_model=ShortURLResponse)
def refresh_short_url_metadata(short_code: str, request: Request, db: Session = Depends(get_db)):
    item = db.query(ShortURL).filter(ShortURL.short_code == short_code).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단축 링크를 찾을 수 없습니다.")

    meta = fetch_url_metadata(item.original_url)
    item.meta_title = meta.get("meta_title")
    item.meta_description = resolve_effective_description(
        item.custom_description, meta.get("meta_description")
    )
    item.meta_image = meta.get("meta_image")
    item.favicon_url = meta.get("favicon_url")
    item.meta_updated_at = meta.get("meta_updated_at")

    db.commit()
    db.refresh(item)
    return to_response(item, request)


@router.delete("/api/urls/expired/purge")
def purge_expired_short_urls(db: Session = Depends(get_db)):
    items = db.query(ShortURL).all()
    purged_count = 0
    for item in items:
        if check_is_expired(item):
            db.delete(item)
            purged_count += 1
    db.commit()
    return {"purged_count": purged_count, "message": f"만료된 링크 {purged_count}건이 소멸(삭제)되었습니다."}


@router.delete("/api/urls/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_short_url(short_code: str, db: Session = Depends(get_db)):
    item = db.query(ShortURL).filter(ShortURL.short_code == short_code).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단축 링크를 찾을 수 없습니다.")
    db.delete(item)
    db.commit()
    return None


@router.get("/{short_code}", response_class=HTMLResponse, include_in_schema=False)
def handle_short_url(
    short_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(ShortURL).filter(ShortURL.short_code == short_code).first()
    if not item:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": 404,
                "title": "존재하지 않는 단축 링크입니다",
                "message": f"요청하신 '{BASE_PREFIX}/{short_code}' 링크를 찾을 수 없거나 삭제되었습니다.",
                "base_prefix": BASE_PREFIX,
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if check_is_expired(item):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": 410,
                "title": "유효기간(1년)이 만료되어 소멸된 링크입니다",
                "message": f"요청하신 '{BASE_PREFIX}/{short_code}' 링크는 유효기간이 경과하여 더 이상 접속할 수 없습니다.",
                "base_prefix": BASE_PREFIX,
            },
            status_code=status.HTTP_410_GONE,
        )

    # Backfill metadata if missing
    if not item.meta_title:
        meta = fetch_url_metadata(item.original_url)
        item.meta_title = meta.get("meta_title")
        item.meta_description = resolve_effective_description(
            item.custom_description, meta.get("meta_description")
        )
        item.meta_image = meta.get("meta_image")
        item.favicon_url = meta.get("favicon_url")
        item.meta_updated_at = meta.get("meta_updated_at")

    item.clicks += 1
    db.commit()
    db.refresh(item)

    resp_data = to_response(item, request)
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "link": resp_data,
            "base_prefix": BASE_PREFIX,
        },
    )


app.include_router(router)

if BASE_PREFIX:
    @app.get("/api/status", include_in_schema=False)
    def get_root_api_status():
        return get_api_status()

    @app.get("/", include_in_schema=False)
    def redirect_root_to_prefix():
        return RedirectResponse(url=f"{BASE_PREFIX}/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


DEFAULT_PORT = int(os.getenv("PORT", "5000"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=DEFAULT_PORT, reload=True)
