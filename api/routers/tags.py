from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api import crud
from api.deps import get_session, parse_date_range
from api.schemas import GroupedCostResponse, TagCoverageByProviderResponse, TagHygieneResponse
from api.services.tag_hygiene import (
    build_tag_hygiene,
    build_tag_hygiene_by_provider,
    build_untagged_breakdown,
    required_tags_for_provider,
)

router = APIRouter()


@router.get("/costs/tag-hygiene", response_model=TagHygieneResponse)
def tag_hygiene(
    required: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    provider: Optional[str] = None,
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = required_tags_for_provider(provider, required)
    entries = crud.get_entries_in_range(session, start, end)
    if provider:
        entries = [entry for entry in entries if entry.provider == provider]
    return build_tag_hygiene(entries, required_tags)


@router.get("/costs/tag-hygiene/by-provider", response_model=List[TagCoverageByProviderResponse])
def tag_hygiene_by_provider(
    required: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    entries = crud.get_entries_in_range(session, start, end)
    return build_tag_hygiene_by_provider(entries, required)


@router.get("/costs/tag-hygiene/untagged", response_model=List[GroupedCostResponse])
def untagged_breakdown(
    group: str = "service",
    required: Optional[str] = None,
    provider: Optional[str] = None,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
):
    start, end = parse_date_range(from_date, to_date)
    required_tags = required_tags_for_provider(provider, required)
    entries = crud.get_entries_in_range(session, start, end)
    if provider:
        entries = [entry for entry in entries if entry.provider == provider]
    return build_untagged_breakdown(entries, required_tags, group)
