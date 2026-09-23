import pytest

def test_fresh_budget_has_full_capacity(provider_budget):
    assert provider_budget.remaining_rpm == 10
    assert provider_budget.can_accept() is True

def test_recording_reduces_remaining(provider_budget):
    for _ in range(3):
        provider_budget.record_request()
    assert provider_budget.remaining_rpm == 7
    assert provider_budget.can_accept() is True

def test_budget_exhaustion(provider_budget):
    for _ in range(10):
        provider_budget.record_request()
    assert provider_budget.remaining_rpm == 0
    assert provider_budget.can_accept() is False

def test_usage_fraction(provider_budget):
    for _ in range(5):
        provider_budget.record_request()
    assert provider_budget.usage_fraction == pytest.approx(0.5)

def test_over_budget_usage_fraction(provider_budget):
    for _ in range(15):
        provider_budget.record_request()
    assert provider_budget.usage_fraction == 1.0  # capped at 1.0

