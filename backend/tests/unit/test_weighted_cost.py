import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.stock_service import weighted_average_cost_after_in

_REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = _REPO_ROOT / "packages" / "shared" / "tests" / "fixtures" / "weighted-cost-cases.json"
CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_weighted_average_cost_matches_shared_fixture(case):
    result = weighted_average_cost_after_in(
        current_quantity=Decimal(str(case["currentQuantity"])),
        current_avg_cost=case["currentAvgCost"],
        in_quantity=Decimal(str(case["inQuantity"])),
        in_unit_cost=case["inUnitCost"],
    )
    assert result == case["expected"]


def test_rejects_non_positive_in_quantity():
    with pytest.raises(ValueError):
        weighted_average_cost_after_in(
            current_quantity=Decimal("10"),
            current_avg_cost=500,
            in_quantity=Decimal("0"),
            in_unit_cost=500,
        )
