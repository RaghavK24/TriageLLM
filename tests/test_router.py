import pytest
from app.router import route, LoadSheddingError

def test_simple_query_routes_to_weak(mock_settings):
    decision = route(complexity=0.3, load=0.2)
    assert decision.tier == "weak"

def test_complex_query_routes_to_strong(mock_settings):
    decision = route(complexity=0.8, load=0.2)
    assert decision.tier == "strong"

def test_high_load_raises_complexity_bar(mock_settings):
    # complexity=0.60 normally routes to strong (> 0.55 threshold)
    # but at load=0.75 (HIGH), bar becomes 0.55+0.15=0.70, so 0.60 < 0.70 → weak
    decision = route(complexity=0.60, load=0.75)
    assert decision.tier == "weak"

def test_critical_load_raises_bar_further(mock_settings):
    # complexity=0.80 normally strong, but at critical load bar=0.55+0.30=0.85
    decision = route(complexity=0.80, load=0.95)
    assert decision.tier == "weak"

def test_groq_exhausted_spills_to_strong(mock_settings):
    decision = route(complexity=0.3, load=0.2, groq_usage=0.95)
    assert decision.tier == "strong"

def test_load_shedding_raises_error(mock_settings):
    with pytest.raises(LoadSheddingError):
        route(complexity=0.8, load=0.2, in_flight=40)  # 40 >= 35 threshold

