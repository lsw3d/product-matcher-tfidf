from app.normalization import (
    extract_codes,
    extract_dimensions,
    extract_numbers,
    normalize_text,
)


def test_char_friendly_normalization() -> None:
    assert "4.2x75" in normalize_text(
        "Саморезы 4,2х75"
    )


def test_only_domain_aliases_are_normalized() -> None:
    assert "ушм" in normalize_text(
        "болгарка на 230"
    )
    assert "ушм" in normalize_text(
        "углошлифовальная машина 125 мм"
    )
    assert "ушм" in normalize_text(
        "шлифовальная машина 230"
    )
    assert "шуруповерт" in normalize_text(
        "шурик на 12в"
    )
    assert "труба профильная" in normalize_text(
        "проф труба 20х20"
    )
    assert "стяжка нейлоновая" in normalize_text(
        "хомуты пластиковые 4.8х400"
    )


def test_latin_units_are_normalized() -> None:
    assert (
        normalize_text("уровень 1000 mm")
        == "уровень 1000 мм"
    )
    assert (
        normalize_text("дрель 750W")
        == "дрель 750 вт"
    )
    assert (
        normalize_text("шуруповерт 12V")
        == "шуруповерт 12 в"
    )


def test_dimensions() -> None:
    assert (
        extract_dimensions("диск 115х1,2")
        == ((115.0, 1.2),)
    )

    assert (
        extract_dimensions("бур 6 на 110")
        == ((6.0, 110.0),)
    )

    assert (
        extract_dimensions(
            "диск 190 на 48 зубьев"
        )
        == ()
    )


def test_codes() -> None:
    assert "pw750" in extract_codes(
        "дрель Prowerk PW-750"
    )

    assert "ph2" in extract_codes(
        "бита PH2 50 мм"
    )

    assert "m10" in extract_codes(
        "гайка М10"
    )

    assert "mm" not in extract_codes(
        "бита PH2 50 mm"
    )


def test_order_amounts_are_not_product_numbers() -> None:
    assert 2.0 not in extract_numbers(
        "нужно 2 дрели prowerk pw-750"
    )

    assert 10.0 not in extract_numbers(
        "нужно 10 метров кабеля шввп 2х0.5"
    )

    assert 3.0 not in extract_numbers(
        "3 листа гкл 9.5"
    )

    assert 5000.0 not in extract_numbers(
        "дрель prowerk pw-750 до 5000 рублей"
    )


def test_technical_numbers_are_preserved() -> None:
    assert 230.0 in extract_numbers(
        "болгарка на 230"
    )

    assert extract_numbers(
        "диск пильный 190 на 48 зубьев"
    ) == frozenset({
        190.0,
        48.0,
    })