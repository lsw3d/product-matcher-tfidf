from app.normalization import extract_codes, extract_dimensions, normalize_text


def test_char_friendly_normalization() -> None:
    assert "4.2x75" in normalize_text("Саморезы 4,2х75")


def test_only_domain_aliases_are_normalized() -> None:
    assert "ушм" in normalize_text("болгарка на 230")
    assert "шуруповерт" in normalize_text("шурик на 12в")
    assert "труба профильная" in normalize_text("проф труба 20х20")
    assert "стяжка нейлоновая" in normalize_text("хомуты пластиковые 4.8х400")


def test_dimensions() -> None:
    assert extract_dimensions("диск 115х1,2") == ((115.0, 1.2),)
    assert extract_dimensions("бур 6 на 110") == ((6.0, 110.0),)
    assert extract_dimensions("диск 190 на 48 зубьев") == ()


def test_codes() -> None:
    assert "pw750" in extract_codes("дрель Prowerk PW-750")
    assert "ph2" in extract_codes("бита PH2 50 мм")
    assert "m10" in extract_codes("гайка М10")
