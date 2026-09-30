from fastapi import FastAPI, HTTPException, Header, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
import hmac
import secrets
import logging

import jwt as pyjwt
from pydantic_settings import BaseSettings, SettingsConfigDict

from db import (
    count_articles,
    count_articles_by_source,
    get_articles,
    get_article_by_id,
    get_attrition_summary,
    get_attrition_by_department,
    get_attrition_by_overtime,
    get_attrition_by_tenure,
    get_top_earners_by_department,
    search_articles, get_department_detail, get_attrition_risk_profile,
)

log = logging.getLogger(__name__)

class Settings(BaseSettings):
    database_url: str
    student_name: str
    internal_api_key: str
    jwt_secret: str
    jwt_expiry_minutes: int = 30
    client_id: str
    client_secret: str

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

settings = Settings()

app = FastAPI(
    title="News & HR Analytics API",
    description=(
        "Session 10 — Dua data pipeline, satu API.\n\n"
        "**Path A (ETL):** Scraped articles (RSS, books, quotes) "
        "cleaned di Pandas, loaded ke PostgreSQL.\n\n"
        "**Path B (ELT):** IBM HR Attrition CSV di-load mentah, "
        "di-transform dengan SQL saat query."
    ),
    version="1.0",
)
security_scheme = HTTPBearer(auto_error=False)

class Article(BaseModel):
    """Model untuk satu artikel dari tabel articles."""
    id: int
    title: str
    url: str
    source: str
    content: Optional[str] = None
    published_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None


class ArticleStats(BaseModel):
    total_articles: int
    by_source: Dict[str, int]


class TokenRequest(BaseModel):
    """Request body untuk POST /token."""
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    """Response dari POST /token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AttritionSummary(BaseModel):
    total_employees: int
    attrition_yes: int
    attrition_no: int
    attrition_rate: float


class DepartmentAttrition(BaseModel):
    """Attrition per department."""
    Department: str
    total: int
    attrition_count: int
    attrition_rate: float
    avg_income: float


class OvertimeAttrition(BaseModel):
    """Attrition per overtime status."""
    OverTime: str
    total: int
    attrition_count: int
    attrition_rate: float


class TenureAttrition(BaseModel):
    """Attrition per tenure bucket."""
    tenure_bucket: str
    total: int
    attrition_count: int
    attrition_rate: float


class TopEarner(BaseModel):
    """Top earner dalam satu department."""
    EmployeeNumber: int
    Department: str
    JobRole: str
    MonthlyIncome: int
    Attrition: str
    income_rank: int



def create_access_token(client_id: str) -> str:
    now = datetime.now(timezone.utc)
    return pyjwt.encode({"sub": client_id, "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
        "jti": secrets.token_hex(16)}, settings.jwt_secret, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """Decode dan validasi JWT token. Raise HTTPException jika invalid."""
    try:
        return pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token sudah expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key is None:
        return None
    if hmac.compare_digest(x_api_key.encode(), settings.internal_api_key.encode()):
        return {"auth_method": "api_key"}
    raise HTTPException(401, "Invalid API key")


def get_current_client(
    api_key_result=Depends(verify_api_key),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
):
    if api_key_result is not None:
        return api_key_result
    if credentials is not None:
        payload = verify_jwt_token(credentials.credentials)
        if not payload.get("sub"):
            raise HTTPException(401, "Invalid token subject")
        return {"auth_method": "bearer", "client_id": payload["sub"]}
    raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})

@app.get("/", tags=["Public"])
def read_root():
    return {
        "message": "News & HR Analytics API — Session 10",
        "student": settings.student_name,
        "paths": {
            "etl_articles": "/articles",
            "elt_attrition": "/attrition",
            "docs": "/docs",
        },
    }

@app.get("/health", tags=["Public"])
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/token", response_model=TokenResponse, tags=["Auth"])
def login_for_token(req: TokenRequest):
    valid_id = hmac.compare_digest(req.client_id.encode(), settings.client_id.encode())
    valid_secret = hmac.compare_digest(req.client_secret.encode(), settings.client_secret.encode())
    if not (valid_id and valid_secret):
        raise HTTPException(401, "Invalid client credentials")
    return TokenResponse(access_token=create_access_token(req.client_id),
                         expires_in=settings.jwt_expiry_minutes * 60)

@app.get("/articles", response_model=List[Article], tags=["Articles (ETL)"])
def list_articles(
    source: Optional[str] = Query(None), title: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100), auth=Depends(get_current_client),
):
    return get_articles(source=source, title=title, limit=limit)





class ArticlePage(BaseModel):
    data: List[Article]
    page: int
    per_page: int
    total_items: int
    total_pages: int

class DepartmentEarner(BaseModel):
    EmployeeNumber: int
    JobRole: str
    MonthlyIncome: int

class DepartmentDetail(BaseModel):
    department: str
    total_employees: int
    attrition_count: int
    attrition_rate: float
    avg_income: float
    min_income: int
    max_income: int
    top_earners: List[DepartmentEarner]

@app.get("/articles/search", response_model=ArticlePage, tags=["Articles (ETL)"])
def article_search(
    source: Optional[str] = Query(None), title: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=50),
    auth=Depends(get_current_client),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be <= date_to")
    return search_articles(source, title, date_from, date_to, page, per_page)

@app.get("/articles/stats", response_model=ArticleStats, tags=["Articles (ETL)"])
def article_stats(auth=Depends(get_current_client)):
    # Satu GROUP BY agar total dan breakdown berasal dari hasil yang sama.
    by_source = count_articles_by_source()
    return ArticleStats(total_articles=sum(by_source.values()), by_source=by_source)

@app.get("/attrition/department/{dept_name}", response_model=DepartmentDetail, tags=["Attrition (ELT)"])
def department_detail(dept_name: str, auth=Depends(get_current_client)):
    result = get_department_detail(dept_name)
    if result is None:
        raise HTTPException(404, "Department not found")
    return result

@app.get("/attrition/risk-profile", response_model=List[Dict], tags=["Attrition (ELT)"])
def risk_profile(limit: int = Query(20, ge=1, le=100), auth=Depends(get_current_client)):
    return get_attrition_risk_profile(limit)

@app.get("/attrition/by-department", response_model=List[DepartmentAttrition], tags=["Attrition (ELT)"])
def attrition_by_department(auth=Depends(get_current_client)):
    return get_attrition_by_department()

@app.get("/articles/{article_id}", response_model=Article, tags=["Articles (ETL)"])
def get_single_article(
    article_id: int,
    auth=Depends(get_current_client),
):
    """Get single article by database ID."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.get("/attrition/summary", response_model=AttritionSummary, tags=["Attrition (ELT)"])
def attrition_summary(auth=Depends(get_current_client)):
    return get_attrition_summary()


@app.get(
    "/attrition/by-overtime",
    response_model=List[OvertimeAttrition],
    tags=["Attrition (ELT)"],
)
def attrition_by_overtime(auth=Depends(get_current_client)):
    """Attrition by overtime status (SQL cross-tab)."""
    return get_attrition_by_overtime()

@app.get(
    "/attrition/by-tenure",
    response_model=List[TenureAttrition],
    tags=["Attrition (ELT)"],
)
def attrition_by_tenure(auth=Depends(get_current_client)):
    """Attrition by tenure bucket (SQL CASE WHEN)."""
    return get_attrition_by_tenure()

@app.get(
    "/attrition/top-earners",
    response_model=List[TopEarner],
    tags=["Attrition (ELT)"],
)
def top_earners(
    limit_per_dept: int = Query(5, le=20, ge=1, description="Top N per department"),
    auth=Depends(get_current_client),
):
    """Top earners per department (SQL RANK window function)."""
    return get_top_earners_by_department(limit_per_dept=limit_per_dept)
