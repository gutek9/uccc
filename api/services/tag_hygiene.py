import os
from typing import Optional, List

from api.schemas import (
    GroupedCostResponse,
    TagCoverageByProviderResponse,
    TagCoverageResponse,
    TagHygieneResponse,
    UntaggedCostEntry,
)
from core.tag_hygiene import DEFAULT_REQUIRED_TAGS, evaluate_tags


def required_tags_for_provider(provider: Optional[str], required: Optional[str]) -> list[str]:
    if required:
        return [tag.strip() for tag in required.split(",") if tag.strip()]
    if provider:
        override = os.getenv(f"REQUIRED_TAGS_{provider.upper()}")
        if override:
            return [tag.strip() for tag in override.split(",") if tag.strip()]
    return DEFAULT_REQUIRED_TAGS


def build_tag_hygiene(entries, required_tags: list[str]) -> TagHygieneResponse:
    total_cost = 0.0
    fully_tagged = 0.0
    partially_tagged = 0.0
    untagged = 0.0
    untagged_entries = []

    for entry in entries:
        tags = entry.tags or {}
        total_cost += entry.cost
        has_all, missing = evaluate_tags(tags, required_tags)
        if has_all:
            fully_tagged += entry.cost
        elif len(tags) == 0:
            untagged += entry.cost
        else:
            partially_tagged += entry.cost
        if missing:
            untagged_entries.append(
                UntaggedCostEntry(
                    id=entry.id,
                    date=entry.date,
                    provider=entry.provider,
                    account_id=entry.account_id,
                    service=entry.service,
                    region=entry.region,
                    cost=entry.cost,
                    currency=entry.currency,
                    missing_tags=missing,
                )
            )

    coverage = TagCoverageResponse(
        required_tags=required_tags,
        total_cost=total_cost,
        fully_tagged_cost=fully_tagged,
        partially_tagged_cost=partially_tagged,
        untagged_cost=untagged,
    )

    return TagHygieneResponse(coverage=coverage, untagged_entries=untagged_entries)


def build_tag_hygiene_by_provider(entries, required: Optional[str]) -> List[TagCoverageByProviderResponse]:
    coverage_by_provider: dict[str, TagCoverageResponse] = {}
    for entry in entries:
        provider = entry.provider
        tags = entry.tags or {}
        required_tags = required_tags_for_provider(provider, required)
        coverage = coverage_by_provider.get(
            provider,
            TagCoverageResponse(
                required_tags=required_tags,
                total_cost=0.0,
                fully_tagged_cost=0.0,
                partially_tagged_cost=0.0,
                untagged_cost=0.0,
            ),
        )

        coverage.total_cost += entry.cost
        has_all, missing = evaluate_tags(tags, required_tags)
        if has_all:
            coverage.fully_tagged_cost += entry.cost
        elif len(tags) == 0:
            coverage.untagged_cost += entry.cost
        else:
            coverage.partially_tagged_cost += entry.cost
        coverage_by_provider[provider] = coverage

    return [
        TagCoverageByProviderResponse(provider=provider, coverage=coverage)
        for provider, coverage in sorted(coverage_by_provider.items())
    ]


def build_untagged_breakdown(entries, required_tags: list[str], group: str) -> List[GroupedCostResponse]:
    totals: dict[str, float] = {}
    for entry in entries:
        tags = entry.tags or {}
        has_all, _ = evaluate_tags(tags, required_tags)
        if has_all:
            continue
        key = entry.service if group == "service" else entry.account_id
        totals[key] = totals.get(key, 0.0) + entry.cost

    rows = [GroupedCostResponse(key=key, total_cost=total) for key, total in totals.items()]
    rows.sort(key=lambda item: item.total_cost, reverse=True)
    return rows
