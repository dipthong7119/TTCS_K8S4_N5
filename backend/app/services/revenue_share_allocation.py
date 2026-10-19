"""Integer currency allocation under versioned revenue-share contracts."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.subscription_usage import SubscriptionUsage
from app.services.revenue_share_contracts import (
    _contract_at,
    _effective_contracts,
    _utc_naive,
)


def allocate_station_owner_pool(amount_vnd: int, energy_wh_by_owner: dict[int, int]) -> dict[int, int]:
    """Split integer VND proportionally by Wh using largest-remainder rounding."""
    weights = {key: value for key, value in energy_wh_by_owner.items() if value > 0}
    total = sum(weights.values())
    if amount_vnd <= 0 or total <= 0:
        return {key: 0 for key in energy_wh_by_owner}
    amounts = {key: amount_vnd * value // total for key, value in weights.items()}
    remainders = {key: amount_vnd * value % total for key, value in weights.items()}
    remaining = amount_vnd - sum(amounts.values())
    for key in sorted(weights, key=lambda item: (-remainders[item], item))[:remaining]:
        amounts[key] += 1
    return {key: amounts.get(key, 0) for key in energy_wh_by_owner}


def _percent_amount(amount_vnd: int, percent: Decimal) -> int:
    return int(
        (Decimal(amount_vnd) * percent / Decimal(100)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def _allocate_by_contract(
    db: Session, usage_rows: list[SubscriptionUsage], base_revenue_vnd: int
) -> dict[tuple[int, int | None], dict]:
    """Distribute base VND to usage records, then apply each effective contract."""
    owner_weights: dict[int, int] = {}
    rows_by_owner: dict[int, list[SubscriptionUsage]] = {}
    for usage in usage_rows:
        owner_id = usage.station_owner_id
        owner_weights[owner_id] = owner_weights.get(owner_id, 0) + int(usage.energy_wh)
        rows_by_owner.setdefault(owner_id, []).append(usage)
    owner_base = allocate_station_owner_pool(base_revenue_vnd, owner_weights)
    contracts_by_owner = _effective_contracts(db, set(owner_weights))
    groups: dict[tuple[int, int | None], dict] = {}
    for owner_id, owner_rows in rows_by_owner.items():
        usage_base = allocate_station_owner_pool(
            owner_base.get(owner_id, 0),
            {row.id: int(row.energy_wh) for row in owner_rows},
        )
        contracts = contracts_by_owner.get(owner_id, [])
        for usage in owner_rows:
            contract = _contract_at(contracts, _utc_naive(usage.created_at))
            contract_id = contract.id if contract else None
            key = (owner_id, contract_id)
            group = groups.setdefault(
                key,
                {
                    "station_owner_id": owner_id,
                    "contract_id": contract_id,
                    "partner_share_percent": contract.partner_share_percent
                    if contract
                    else Decimal(0),
                    "platform_share_percent": contract.platform_share_percent
                    if contract
                    else Decimal(100),
                    "effective_from": contract.effective_from if contract else None,
                    "effective_to": contract.effective_to if contract else None,
                    "energy_wh": 0,
                    "base_revenue_vnd": 0,
                    "shared_amount_vnd": 0,
                },
            )
            base = usage_base.get(usage.id, 0)
            group["energy_wh"] += int(usage.energy_wh)
            group["base_revenue_vnd"] += base
            group["shared_amount_vnd"] += _percent_amount(
                base, Decimal(group["partner_share_percent"])
            )
    return groups

