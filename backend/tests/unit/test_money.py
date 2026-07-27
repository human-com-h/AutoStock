from app.core.money import cents_to_yuan, format_yuan, round_half_up, yuan_to_cents


def test_cents_to_yuan():
    assert cents_to_yuan(4500) == 45
    assert cents_to_yuan(1) == 0.01
    assert cents_to_yuan(0) == 0


def test_yuan_to_cents():
    assert yuan_to_cents(45) == 4500
    assert yuan_to_cents(0.01) == 1


def test_format_yuan():
    assert format_yuan(4500) == "45.00"
    assert format_yuan(1) == "0.01"


def test_round_half_up_matches_js_math_round():
    assert round_half_up(100.5) == 101
    assert round_half_up(-1.5) == -1
    assert round_half_up(-2.5) == -2
    assert round_half_up(2.4) == 2
