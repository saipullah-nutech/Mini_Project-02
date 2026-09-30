"""Query PostgreSQL untuk Mini Project 2. Tidak mengubah DB saat import."""
import math
import re
from typing import Optional
from sqlalchemy import create_engine, text
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    database_url: str
    student_name: str = 'saipul_ai2'
    db_schema: str = 'ai_engineer'
    articles_table_name: Optional[str] = None
    attrition_table_name: Optional[str] = None
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


settings = DBSettings()


def quoted_identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError('Nama schema/tabel hanya boleh berisi huruf, angka, underscore')
    return '"' + value + '"'


SCHEMA = settings.db_schema
ARTICLES_TABLE_NAME = settings.articles_table_name or f'articles_{settings.student_name}'
ATTRITION_TABLE_NAME = settings.attrition_table_name or f'raw_attrition_{settings.student_name}'
ARTICLES_TABLE = f'{quoted_identifier(SCHEMA)}.{quoted_identifier(ARTICLES_TABLE_NAME)}'
ATTRITION_TABLE = f'{quoted_identifier(SCHEMA)}.{quoted_identifier(ATTRITION_TABLE_NAME)}'
engine = create_engine(settings.database_url, pool_pre_ping=True)


def rows(sql, params=None):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params or {}).mappings()]


def scalar(sql, params=None):
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).scalar_one()


def article_filters(source=None, title=None, date_from=None, date_to=None):
    clauses, params = [], {}
    if source is not None:
        clauses.append('source = :source')
        params['source'] = source
    if title is not None:
        clauses.append('title ILIKE :title')
        params['title'] = f'%{title}%'
    if date_from is not None:
        clauses.append('published_at >= CAST(:date_from AS DATE)')
        params['date_from'] = date_from
    if date_to is not None:
        clauses.append("published_at < CAST(:date_to AS DATE) + INTERVAL '1 day'")
        params['date_to'] = date_to
    return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params


def search_articles(source=None, title=None, date_from=None, date_to=None, page=1, per_page=10):
    where, params = article_filters(source, title, date_from, date_to)
    # Satu snapshot menjaga COUNT dan hasil halaman konsisten pada request ini.
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            total = conn.execute(text(f'SELECT COUNT(*) FROM {ARTICLES_TABLE}{where}'), params).scalar_one()
            data = conn.execute(text(f'''SELECT * FROM {ARTICLES_TABLE}{where}
                ORDER BY published_at DESC NULLS LAST, id DESC
                LIMIT :limit OFFSET :offset'''),
                {**params, 'limit': per_page, 'offset': (page - 1) * per_page}).mappings().all()
    return dict(data=[dict(r) for r in data], page=page, per_page=per_page,
                total_items=total, total_pages=math.ceil(total / per_page))


def count_articles():
    return scalar(f'SELECT COUNT(*) FROM {ARTICLES_TABLE}')


def count_articles_by_source():
    result = rows(f'SELECT source, COUNT(*) AS total FROM {ARTICLES_TABLE} GROUP BY source ORDER BY source')
    return {r['source']: r['total'] for r in result}


def get_articles(source=None, title=None, limit=20):
    where, params = article_filters(source, title)
    return rows(f'SELECT * FROM {ARTICLES_TABLE}{where} ORDER BY published_at DESC NULLS LAST, id DESC LIMIT :limit',
                {**params, 'limit': limit})


def get_article_by_id(article_id):
    result = rows(f'SELECT * FROM {ARTICLES_TABLE} WHERE id = :id', {'id': article_id})
    return result[0] if result else None


def get_attrition_summary():
    return rows(f'''SELECT COUNT(*) AS total_employees,
        COUNT(*) FILTER (WHERE "Attrition" = 'Yes') AS attrition_yes,
        COUNT(*) FILTER (WHERE "Attrition" = 'No') AS attrition_no,
        COALESCE(ROUND((COUNT(*) FILTER (WHERE "Attrition" = 'Yes'))::numeric
            / NULLIF(COUNT(*), 0), 4), 0) AS attrition_rate
        FROM {ATTRITION_TABLE}''')[0]


def get_department_detail(dept_name):
    params = {'dept': dept_name}
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            result = dict(conn.execute(text(f'''SELECT COUNT(*) AS total_employees,
                COUNT(*) FILTER (WHERE "Attrition" = 'Yes') AS attrition_count,
                ROUND((COUNT(*) FILTER (WHERE "Attrition" = 'Yes'))::numeric
                    / NULLIF(COUNT(*), 0), 4) AS attrition_rate,
                ROUND(AVG("MonthlyIncome")::numeric, 2) AS avg_income,
                MIN("MonthlyIncome") AS min_income, MAX("MonthlyIncome") AS max_income
                FROM {ATTRITION_TABLE} WHERE "Department" = :dept'''), params).mappings().one())
            if result['total_employees'] == 0:
                return None
            earners = conn.execute(text(f'''SELECT "EmployeeNumber", "JobRole", "MonthlyIncome"
                FROM (SELECT "EmployeeNumber", "JobRole", "MonthlyIncome",
                    RANK() OVER (ORDER BY "MonthlyIncome" DESC) AS income_rank
                    FROM {ATTRITION_TABLE} WHERE "Department" = :dept) ranked
                ORDER BY income_rank, "EmployeeNumber" LIMIT 3'''), params).mappings().all()
    return {'department': dept_name, **result, 'top_earners': [dict(r) for r in earners]}


def get_attrition_risk_profile(limit=20):
    return rows(f'''WITH dept_avg AS (
        SELECT "Department", AVG("MonthlyIncome") AS avg_income
        FROM {ATTRITION_TABLE} GROUP BY "Department"
    ) SELECT e.* FROM {ATTRITION_TABLE} e
    JOIN dept_avg d ON e."Department" = d."Department"
    WHERE e."OverTime" = 'Yes' AND e."YearsAtCompany" < 3
        AND e."MonthlyIncome" < d.avg_income
    ORDER BY e."EmployeeNumber" LIMIT :limit''', {'limit': limit})


def grouped_attrition(expression, alias, order):
    # expression/alias/order hanya konstanta internal, bukan input pengguna.
    return rows(f'''SELECT {expression} AS "{alias}", COUNT(*) AS total,
        COUNT(*) FILTER (WHERE "Attrition" = 'Yes') AS attrition_count,
        ROUND((COUNT(*) FILTER (WHERE "Attrition" = 'Yes'))::numeric / COUNT(*), 4) AS attrition_rate
        FROM {ATTRITION_TABLE} GROUP BY {expression} ORDER BY {order}''')


def get_attrition_by_department():
    return rows(f'''SELECT "Department", COUNT(*) AS total,
        COUNT(*) FILTER (WHERE "Attrition" = 'Yes') AS attrition_count,
        ROUND((COUNT(*) FILTER (WHERE "Attrition" = 'Yes'))::numeric / COUNT(*), 4) AS attrition_rate,
        ROUND(AVG("MonthlyIncome")::numeric, 2) AS avg_income
        FROM {ATTRITION_TABLE} GROUP BY "Department" ORDER BY "Department"''')


def get_attrition_by_overtime():
    return grouped_attrition('"OverTime"', 'OverTime', '"OverTime"')


def get_attrition_by_tenure():
    expr = '''CASE WHEN "YearsAtCompany" < 2 THEN 'new (<2y)'
        WHEN "YearsAtCompany" < 5 THEN 'mid (2-5y)' ELSE 'veteran (5y+)' END'''
    return grouped_attrition(expr, 'tenure_bucket', 'tenure_bucket')


def get_top_earners_by_department(limit_per_dept=5):
    return rows(f'''SELECT * FROM (
        SELECT "EmployeeNumber", "Department", "JobRole", "MonthlyIncome", "Attrition",
        RANK() OVER (PARTITION BY "Department" ORDER BY "MonthlyIncome" DESC) AS income_rank
        FROM {ATTRITION_TABLE}
    ) ranked WHERE income_rank <= :limit ORDER BY "Department", income_rank, "EmployeeNumber"''',
        {'limit': limit_per_dept})
