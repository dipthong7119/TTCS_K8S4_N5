"""SCRUM-65 / S-32: compare production prices with independently written answers."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.pricing import calculate_session_price

MANUAL_DATA = json.loads(
    (Path(__file__).resolve().parents[1] / "scrum65_pricing_cases.json").read_text(
        encoding="utf-8"
    )
)
MANUAL_CASES = MANUAL_DATA["cases"]


def _case_parameter(case):
    marks = [pytest.mark.skip(reason=case["blocked_by"])] if case.get("blocked_by") else []
    return pytest.param(case, id=case["case_id"], marks=marks)


def _assert_price_matches_manual_case(case, actual):
    """Collect discrepancies without calculating any expected price or energy."""
    expected = case["expected"]
    discrepancies = []

    def compare(location, key, wanted, received):
        if key in {"amount_vnd", "total_vnd", "price_vnd_per_kwh"}:
            if type(received) is not int:
                discrepancies.append(
                    f"{location}: {key} phải là số nguyên đồng, nhận {received!r}"
                )
            elif received != wanted:
                discrepancies.append(
                    f"{location}: {key}, mong đợi {wanted}, thực tế {received}, "
                    f"chênh {received - wanted:+d} đồng (thực tế - đáp án)"
                )
        elif key == "energy_kwh" and received is not None:
            delta = Decimal(str(received)) - Decimal(wanted)
            if delta:
                discrepancies.append(
                    f"{location}: {key}, mong đợi {wanted}, thực tế {received}, "
                    f"chênh {delta:+f} kWh (thực tế - đáp án)"
                )
        elif received != wanted:
            discrepancies.append(
                f"{location}: {key}, mong đợi {wanted!r}, thực tế {received!r}"
            )

    # A total mismatch must not hide which segment caused it.
    actual_segments = actual.get("segments", [])
    if len(actual_segments) != len(expected["segments"]):
        discrepancies.append(
            f"Số đoạn: mong đợi {len(expected['segments'])}, "
            f"thực tế {len(actual_segments)}"
        )
    for number, segment in enumerate(expected["segments"], start=1):
        if number > len(actual_segments):
            discrepancies.append(f"Đoạn {number}: thiếu đoạn {segment['from']} → {segment['to']}")
            continue
        for key, wanted in segment.items():
            compare(f"Đoạn {number}", key, wanted, actual_segments[number - 1].get(key))
    compare("Tổng phiên", "total_vnd", expected["total_vnd"], actual.get("total_vnd"))

    assert not discrepancies, (
        f"{case['case_id']} — {case['description']}\n"
        + "\n".join(discrepancies)
        + f"\nTính tay: {case['manual_calculation']}"
    )


def test_manual_dataset_has_required_scope_and_author():
    assert MANUAL_DATA["ticket"] == "SCRUM-65"
    assert "Trịnh Thanh Tùng" in MANUAL_DATA["calculated_by"]
    datetime.fromisoformat(MANUAL_DATA["calculated_on"])
    assert len(MANUAL_CASES) >= 12
    assert len({case["case_id"] for case in MANUAL_CASES}) == len(MANUAL_CASES)
    assert len([case for case in MANUAL_CASES if not case.get("blocked_by")]) >= 12
    assert {"single_band", "boundary", "midnight", "idle_fee", "sparse_readings"} <= {
        case["category"] for case in MANUAL_CASES
    }
    for case in MANUAL_CASES:
        assert case["manual_calculation"], case["case_id"]
        assert type(case["expected"]["total_vnd"]) is int, case["case_id"]
        assert case["tariff"] in MANUAL_DATA["tariffs"], case["case_id"]
        # Never silently run an unsupported case by discarding its extra inputs.
        if "idle_input" in case or "tariff_versions" in case:
            assert case.get("blocked_by"), f"{case['case_id']}: cần nối adapter trước khi bật"


@pytest.mark.parametrize("case", [_case_parameter(case) for case in MANUAL_CASES])
def test_session_price_matches_manual_answer(case):
    inputs = dict(case["input"])
    inputs["started_at"] = datetime.fromisoformat(inputs["started_at"].replace("Z", "+00:00"))
    inputs["ended_at"] = datetime.fromisoformat(inputs["ended_at"].replace("Z", "+00:00"))
    actual = calculate_session_price(
        **inputs,
        bands=MANUAL_DATA["tariffs"][case["tariff"]],
        timezone_name=MANUAL_DATA["timezone_name"],
    )
    _assert_price_matches_manual_case(case, actual)


def test_failure_reports_case_segment_and_exact_vnd_difference():
    case = MANUAL_CASES[0]
    # Intentionally wrong output; all expected values still come from the JSON.
    actual = {
        "total_vnd": 5999,
        "segments": [{**case["expected"]["segments"][0], "amount_vnd": 5999}],
    }
    with pytest.raises(AssertionError) as failure:
        _assert_price_matches_manual_case(case, actual)
    message = str(failure.value)
    assert "SCRUM65-01" in message
    assert "Đoạn 1: amount_vnd, mong đợi 6000, thực tế 5999, chênh -1 đồng" in message
    assert "Tổng phiên: total_vnd, mong đợi 6000, thực tế 5999, chênh -1 đồng" in message
    assert case["manual_calculation"] in message
