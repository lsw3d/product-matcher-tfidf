import pytest

from app.matcher import ProductMatcher


@pytest.mark.parametrize(
    ("message", "expected_sku"),
    [
        (
            "дрель ударная prowerk pw-750 в наличии?",
            "INS-0008",
        ),
        (
            "дрел ударная prowerk pw750",
            "INS-0008",
        ),
        (
            "кабель шввп 2х0.5 сколько за метр",
            "KAB-0017",
        ),
        (
            "диск пильный 190 на 48 зубьев",
            "DSK-0034",
        ),
        (
            "уровень 1000 мм есть?",
            "RIN-0024",
        ),
        (
            "гайки м10 нужны",
            "KRP-0020",
        ),
        (
            "лента фум 12 мм",
            "RAS-0060",
        ),
        (
            "перчатки нитриловые есть?",
            "PER-0002",
        ),
        (
            "проф труба 20х20 стенка полтора",
            "TRB-0002",
        ),
        (
            "гкл 9.5 сколько лист",
            "GKL-0001",
        ),
        (
            "хомуты пластиковые 4.8х400",
            "RAS-0014",
        ),
        (
            "сдс бур 6 на 110",
            "BIT-0074",
        ),
        (
            "наждачка р120 листами",
            "RAS-0050",
        ),
        (
            "круг зачистной на 125",
            "DSK-0018",
        ),
        (
            "бита ph2 50 мм",
            "BIT-0005",
        ),
        (
            "саморезы по дереву 3.5х45 пачка 200",
            "SAM-0010",
        ),
        (
            "труба профильная 20х20х2",
            "TRB-0003",
        ),
        (
            "ввгнг лс 3х1.5",
            "KAB-0010",
        ),
        (
            "диск отрезной по металлу 115х1.2",
            "DSK-0002",
        ),
        (
            "бур sds 10х210",
            "BIT-0080",
        ),
        (
            "дюбель-гвоздь 6х60",
            "KRP-0048",
        ),
    ],
)
def test_known_product_is_matched(
    matcher: ProductMatcher,
    message: str,
    expected_sku: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "matched"
    assert result.candidates[0].sku == expected_sku


@pytest.mark.parametrize(
    "message",
    [
        "здравствуйте, есть саморезы гкл 3.5х25?",
        "саморезы по дереву 4.2 на 75, пачку",
        "шурик на 12в недорогой",
        "болгарка на 230 какая есть",
        "нужен кабель",
        "дайте дюбелей",
        "сверло нужно",
        "какие есть диски",
        "перфоратор посоветуйте",
        "шуруповерт как у макиты, только дешевле",
    ],
)
def test_underspecified_query_is_ambiguous(
    matcher: ProductMatcher,
    message: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "ambiguous"
    assert 2 <= len(result.candidates) <= 3


@pytest.mark.parametrize(
    "message",
    [
        "саморезы по металлу 4.2х70",
        "саморез по дереву 4.2х74",
        "труба профильная 35х35",
        "кабель ввгнг 4х2.5",
        "ушм на 150",
        "бита t50",
        "шпилька м16 метровая",
        "здравствуйте, вы до скольки работаете?",
        "можно оплатить картой при получении?",
        "где находится ваш магазин",
        "статус заказа 4512 подскажите",
        "спасибо, заказ получил, все отлично",
        "хочу вернуть дрель",
        "когда доставите кабель?",
        "дрель bosch 750 вт",
        "",
        "!!!",
    ],
)
def test_missing_or_non_product_is_not_found(
    matcher: ProductMatcher,
    message: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "not_found"
    assert result.candidates == []


def test_unknown_typo_not_overfit_to_examples(
    matcher: ProductMatcher,
) -> None:
    result = matcher.match(
        "самарез по дереву 3.5х45 пачка 200"
    )

    assert result.status == "matched"
    assert result.candidates[0].sku == "SAM-0010"


@pytest.mark.parametrize(
    ("message", "expected_sku"),
    [
        (
            "нужно 2 дрели prowerk pw-750",
            "INS-0008",
        ),
        (
            "нужно 10 метров кабеля шввп 2х0.5",
            "KAB-0017",
        ),
        (
            "кабель шввп 2х0.5 10 м",
            "KAB-0017",
        ),
        (
            "3 листа гкл 9.5",
            "GKL-0001",
        ),
        (
            "2 кг саморезов по дереву 4.2х75",
            "SAM-0024",
        ),
        (
            "бита ph2 50 мм 3 штуки",
            "BIT-0005",
        ),
        (
            "дрель prowerk pw-750 до 5000 рублей",
            "INS-0008",
        ),
        (
            "уровень 1000 mm",
            "RIN-0024",
        ),
        (
            "бита ph2 50 mm",
            "BIT-0005",
        ),
    ],
)
def test_order_noise_and_latin_units_do_not_break_matching(
    matcher: ProductMatcher,
    message: str,
    expected_sku: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "matched"
    assert result.candidates[0].sku == expected_sku


@pytest.mark.parametrize(
    "message",
    [
        "углошлифовальная машина 125 мм",
        "шлифовальная машина 230",
    ],
)
def test_grinder_wording_does_not_return_abrasives(
    matcher: ProductMatcher,
    message: str,
) -> None:
    result = matcher.match(message)

    assert result.status in {
        "matched",
        "ambiguous",
    }

    assert result.candidates

    assert all(
        candidate.sku.startswith("INS-")
        for candidate in result.candidates
    )