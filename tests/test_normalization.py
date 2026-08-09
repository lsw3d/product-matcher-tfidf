import pytest

from app.normalization import (
    code_variants,
    extract_codes,
    extract_dimensions,
    extract_numbers,
    extract_pack_count,
    extract_qualifiers,
    extract_quantities,
    extract_unit_hint,
    normalize_text,
)


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("Саморезы 4,2х75", "4.2x75"),
        ("болгарка на 230", "ушм"),
        ("углошлифовальная машина 125 мм", "ушм"),
        ("шлифовальная машина 230", "ушм"),
        ("ленточная шлифовальная машина 900 вт", "ленточная шлифмашина"),
        ("шурик на 12в", "шуруповерт"),
        ("проф труба 20х20", "труба профильная"),
        ("хомуты пластиковые 4.8х400", "стяжка нейлоновая"),
    ],
)
def test_normalization_aliases(source: str, fragment: str) -> None:
    assert fragment in normalize_text(source)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("уровень 1000 mm", "уровень 1000 мм"),
        ("дрель 750W", "дрель 750 вт"),
        ("шуруповерт 12V", "шуруповерт 12 в"),
    ],
)
def test_latin_units(source: str, expected: str) -> None:
    assert normalize_text(source) == expected


def test_specific_grinder_type_is_not_replaced_with_angle_grinder() -> None:
    assert "ушм" not in normalize_text("ленточная шлифовальная машина 900 вт")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("диск 115х1,2", ((115.0, 1.2),)),
        ("бур 6 на 110", ((6.0, 110.0),)),
        ("диск 190 на 48 зубьев", ()),
    ],
)
def test_dimensions(source: str, expected: tuple[tuple[float, ...], ...]) -> None:
    assert extract_dimensions(source) == expected


def test_codes() -> None:
    assert "pw750" in extract_codes("дрель Prowerk PW-750")
    assert "ph2" in extract_codes("бита PH2 50 мм")
    assert "m10" in extract_codes("гайка М10")
    assert "mm" not in extract_codes("бита PH2 50 mm")
    assert extract_codes("PW-12Л") == extract_codes("PW-12Li")


def _codes_are_equivalent(left: str, right: str) -> bool:
    return all(
        any(
            code_variants(left_code) & code_variants(right_code)
            for right_code in extract_codes(right)
        )
        for left_code in extract_codes(left)
    )


@pytest.mark.parametrize(
    ("cyrillic", "latin"),
    [
        ("ТР-750", "TR-750"),
        ("АРС-750", "ARS-750"),
        ("бита Т30 25 мм", "бита T30 25 мм"),
        ("отвертка РН2 100 мм", "отвертка PH2 100 мм"),
        ("дрель ПВ-750", "дрель PW-750"),
        ("шуруповерт ПВ-12Л", "шуруповерт PW-12Li"),
        ("шкурка Р120", "шкурка P120"),
    ],
)
def test_cyrillic_codes_are_equivalent_to_latin(cyrillic: str, latin: str) -> None:
    assert _codes_are_equivalent(cyrillic, latin)


def test_different_codes_stay_different() -> None:
    assert not _codes_are_equivalent("бита Т30 25 мм", "бита T25 25 мм")
    assert not _codes_are_equivalent("дрель ПВ-750", "дрель PW-900")


@pytest.mark.parametrize(
    ("value", "source"),
    [
        (2.0, "нужно 2 дрели prowerk pw-750"),
        (10.0, "нужно 10 метров кабеля шввп 2х0.5"),
        (3.0, "3 листа гкл 9.5"),
        (5000.0, "дрель prowerk pw-750 до 5000 рублей"),
        (5000.0, "дрель prowerk pw-750 цена 5000"),
        (5000.0, "дрель prowerk pw-750 5000 рублей"),
        (2.0, "2 дрели prowerk pw-750"),
        (20.0, "20 саморезов по дереву 3.5х45"),
        (10.0, "кабель шввп 2х0.5 метров 10"),
        (1.0, "1 дрель prowerk pw-750"),
        (2.0, "2 пары перчаток"),
    ],
)
def test_order_amounts_are_not_product_numbers(value: float, source: str) -> None:
    assert value not in extract_numbers(source)


def test_technical_numbers_are_preserved() -> None:
    assert 230.0 in extract_numbers("болгарка на 230")
    assert extract_numbers("диск пильный 190 на 48 зубьев") == frozenset({190.0, 48.0})
    assert 150.0 in extract_numbers("150 ушм")
    assert 125.0 in extract_numbers("125 диск отрезной")
    assert 98765.0 in extract_numbers("лист 98765")


def test_thread_size_is_both_code_and_dimension() -> None:
    assert "m10" in extract_codes("болт М10х60")
    assert (10.0, 60.0) in extract_dimensions("болт М10х60")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("диск пильный по металлу", frozenset({"application:metal"})),
        ("уровень лазерный", frozenset({"level:laser"})),
        ("гайка самоконтрящаяся", frozenset({"fastener:self_locking"})),
        ("ленточная шлифовальная машина", frozenset({"grinder:belt"})),
    ],
)
def test_semantic_qualifiers(source: str, expected: frozenset[str]) -> None:
    assert extract_qualifiers(source) == expected


def test_only_structured_latin_tokens_are_codes() -> None:
    codes = extract_codes("please дрель prowerk pw-750")
    assert "please" not in codes
    assert "prowerk" not in codes
    assert "pw750" in codes
    assert "pd12l" in extract_codes("шуруповерт PD-12Li")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("пачка по 200", 200),
        ("200 шт в упаковке", 200),
        ("упаковка 5", None),
        ("упаковка 5 шт", 5),
        ("5 шт в упаковке", 5),
    ],
)
def test_pack_count(source: str, expected: int | None) -> None:
    assert extract_pack_count(source) == expected


def test_sale_unit_hints() -> None:
    assert extract_unit_hint("саморезы 3.5х45 уп.") == "уп"
    assert extract_unit_hint("пару перчаток") == "пара"


def test_compound_codes_and_quantities() -> None:
    assert "ph2" in extract_codes("Отвёртка PH2х100 мм")
    assert "sl5.5" in extract_codes("Отвёртка SL5.5х100 мм")
    assert "ffp2" in extract_codes("Респиратор FFP2")
    assert (100.0, "мм") in extract_quantities("Отвёртка PH2х100 мм")


def test_structured_quantities() -> None:
    assert (12.0, "в") in extract_quantities("Шуруповерт 12 В")
    assert (750.0, "вт") in extract_quantities("Дрель 750 Вт")
    assert extract_quantities("Хомут 16-27 мм") == ((16.0, "мм"), (27.0, "мм"))
    assert extract_quantities("Саморез 3.5х25 (кг)") == ()
