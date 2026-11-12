import pytest
from pydantic import ValidationError

from triage.models import Dispute


def test_valid(request_data):
    assert Dispute(**request_data).connected_load_kw == 3


@pytest.mark.parametrize("changes", [
    {"connected_load_kw": -1}, {"connected_load_kw": float("nan")},
    {"connection_type": "INVALID"}, {"billed_category": "free"},
    {"description": "short"}, {"premises_use": "mixed"},
    {"business_area_sqm": 50}, {"business_area_sqm": 50, "total_area_sqm": 20},
    {"billing_date": "2099-01-01"}, {"unexpected": "field"}
])
def test_rejects_bad_boundary_values(request_data, changes):
    with pytest.raises(ValidationError):
        Dispute(**{**request_data, **changes})


def test_load_exceedance_is_a_valid_dispute(request_data):
    # A real load violation must reach triage rather than being treated as malformed.
    assert Dispute(**{**request_data, "connected_load_kw": 7}).connected_load_kw == 7
