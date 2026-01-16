from datetime import date, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.db import SessionLocal


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def parse_date_range(start: Optional[date], end: Optional[date]) -> Tuple[date, date]:
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=30)
    if start > end:
        raise HTTPException(status_code=400, detail="from date must be <= to date")
    return start, end
