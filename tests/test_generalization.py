"""Held-out проверки: сообщения, по которым пороги не подбирались.

Кейсы в `test_matcher.py` писались вместе с правилами матчинга, поэтому по
ним нельзя судить о поведении на новых формулировках. Здесь собраны те виды
сообщений, которых в `messages.txt` нет: вежливые многословные обращения,
лишние слова, кириллические маркировки, словоформы и товар вместе с
вопросом про доставку.
"""

import pytest

from app.matcher import ProductMatcher


# Лишние слова не должны мешать: товар назван однозначно.
NOISE_TOLERANT_CASES = [
    ("дрель ударная prowerk pw-750 самовывоз", "INS-0008"),
    ("дрель ударная prowerk pw-750 в кредит", "INS-0008"),
    ("добрый день, а сколько стоит дрель prowerk pw-750?", "INS-0008"),
    ("кабель шввп 2х0.5 в бухте", "KAB-0017"),
    ("бита ph2 50 мм для дрели", "BIT-0005"),
    ("перчатки нитриловые с гарантией", "PER-0002"),
    ("дрель prowerk pw-750 есть доставка?", "INS-0008"),
]

# Разговорные синонимы расходников: в каталоге они называются дисками.
COLLOQUIAL_NAME_CASES = [
    ("лепестковый круг 125 p60", "DSK-0026"),
    ("круг лепестковый 115 мм p40", "DSK-0021"),
]

# Кириллица в маркировке: каталог хранит их латиницей.
CYRILLIC_CODE_CASES = [
    ("бита т30 25 мм", "BIT-0028"),
    ("отвертка рн2 100 мм", "RIN-0010"),
    ("дрель ПВ-750", "INS-0008"),
    ("шуруповерт пв-12л", "INS-0010"),
    ("дрель ТР-750", "INS-0001"),
]

# Словоформы, которых нет ни в каталоге, ни в messages.txt.
INFLECTION_CASES = [
    ("гайкам м10", "KRP-0020"),
    ("шпильками м8х1000", "KRP-0033"),
    ("дюбелем распорным 6х30", "KRP-0051"),
    ("трубе профильной 20х20х2", "TRB-0003"),
    ("уровнем 1000 мм", "RIN-0024"),
    ("саморезами по дереву 3.5х45 пачка 200", "SAM-0010"),
    ("кистью 50 мм", "RAS-0037"),
]

# Товар назван, поэтому вопрос о доставке не делает сообщение нетоварным.
PRODUCT_WITH_SERVICE_QUESTION = [
    "нужен кабель ввгнг 3х1.5 с доставкой",
    "кабель ввгнг 3х1.5 доставка возможна",
]

# Сомнительное лучше вернуть списком, чем угадывать.
AMBIGUOUS_CASES = [
    ("подскажите саморезы по дереву 4.2х75", "SAM-"),
    ("здравствуйте! подскажите пожалуйста есть ли у вас саморезы 4.2 на 75?", "SAM-"),
    ("нужны обычные саморезы по дереву 4.2х75", "SAM-"),
    ("сверло 10 мм", "BIT-"),
    ("нужен любой шуруповерт", "INS-"),
    # Тире вместо запятой — не отрицательное число.
    ("саморезы 3.5х45 - 200 шт", "SAM-"),
    # Родительный падеж множественного числа: `пачек`, а не `пачк\w*`.
    ("5 пачек саморезов по дереву 3.5х45", "SAM-"),
    ("10 упаковок саморезов 3.5х45", "SAM-"),
    # Названная маркировка важнее незнакомого слова рядом с семейством.
    ("отвертка крестовая ph2", "RIN-"),
    ("круг отрезной 125х1.2", "DSK-"),
    # Товар назван, вопрос про доставку не должен его прятать.
    ("здравствуйте! а есть саморезы по дереву 4.2х75 и когда доставите?", "SAM-"),
]

# Слово перед названием семейства — это вершина словосочетания. Если каталог
# её не знает, спрашивают о другом товаре, даже когда остаток строки похож.
UNKNOWN_HEAD_CASES = [
    "унитаз подвесной",
    "светильник подвесной",
    "потолок подвесной 600х600",
    "напильник круглый",
    "стол разделочный",
]

# Уточнение, которого нет в каталоге, — это другой товар, а не шум.
UNKNOWN_SUBTYPE_CASES = [
    "дюбель бабочка 6х40",
    "сверло форстнера 10 мм",
    "саморез кровельный 4.8х25",
    "диск алмазный 125 мм",
    "уровень гидравлический 1000 мм",
    "труба круглая 20х20",
    "розетка prowerk pw-750",
    "бита т50 25 мм",
    "дрель ПВ-999",
]

# Нетоварные сообщения без названия товара.
NON_PRODUCT_CASES = [
    "когда доставите кабель?",
    "верните деньги за заказ 4512",
    "гарантия на заказ 4512",
    "привет как дела",
    "а можно скидку?",
    "сколько стоит доставка до казани",
]


@pytest.mark.parametrize(
    ("message", "expected_sku"),
    [
        *NOISE_TOLERANT_CASES,
        *COLLOQUIAL_NAME_CASES,
        *CYRILLIC_CODE_CASES,
        *INFLECTION_CASES,
    ],
)
def test_matched_without_tuning(
    matcher: ProductMatcher,
    message: str,
    expected_sku: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "matched"
    assert [candidate.sku for candidate in result.candidates] == [expected_sku]


@pytest.mark.parametrize("message", PRODUCT_WITH_SERVICE_QUESTION)
def test_service_question_does_not_hide_named_product(
    matcher: ProductMatcher,
    message: str,
) -> None:
    result = matcher.match(message)

    assert result.status != "not_found"
    assert all(
        candidate.sku.startswith("KAB-") for candidate in result.candidates
    )


@pytest.mark.parametrize(("message", "expected_prefix"), AMBIGUOUS_CASES)
def test_ambiguous_without_tuning(
    matcher: ProductMatcher,
    message: str,
    expected_prefix: str,
) -> None:
    result = matcher.match(message)

    assert result.status == "ambiguous"
    assert 2 <= len(result.candidates) <= 3
    assert all(
        candidate.sku.startswith(expected_prefix) for candidate in result.candidates
    )


@pytest.mark.parametrize(
    "message",
    [*UNKNOWN_SUBTYPE_CASES, *UNKNOWN_HEAD_CASES, *NON_PRODUCT_CASES],
)
def test_not_found_without_tuning(matcher: ProductMatcher, message: str) -> None:
    result = matcher.match(message)

    assert result.status == "not_found"
    assert result.candidates == []


@pytest.mark.parametrize(
    "message",
    [
        "посмотрите дрель prowerk pw-750",
        "гляньте дрель prowerk pw-750",
    ],
)
def test_unlisted_polite_word_does_not_hide_named_product(
    matcher: ProductMatcher,
    message: str,
) -> None:
    """Слово перед семейством штрафует кандидата, но не отбрасывает его.

    Перечислить все вежливые обороты нельзя, поэтому незнакомое слово в
    позиции вершины должно лишь снижать уверенность.
    """
    result = matcher.match(message)

    assert result.status != "not_found"
    assert result.candidates[0].sku == "INS-0008"


def test_noise_never_beats_an_exact_message(matcher: ProductMatcher) -> None:
    clean = matcher.match("дрель ударная prowerk pw-750")
    noisy = matcher.match("здравствуйте, нужна дрель ударная prowerk pw-750, спасибо")

    assert clean.status == noisy.status == "matched"
    assert clean.candidates[0].sku == noisy.candidates[0].sku
    assert noisy.candidates[0].confidence <= clean.candidates[0].confidence
