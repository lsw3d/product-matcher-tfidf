from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from app.normalization import extract_codes, extract_dimensions, extract_numbers, extract_quantities, normalize_text


_PACK_COUNT_RE = re.compile(r"\bуп\.?\s*(\d{2,5})\s*шт\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CatalogItem:
    # Храним рядом с исходными данными заранее извлечённые признаки товара,
    # чтобы не парсить название каталога заново при каждом поисковом запросе.
    sku: str
    name: str
    unit: str
    price: float
    normalized_name: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    quantities: tuple[tuple[float, str], ...]
    numbers: frozenset[float]
    pack_count: int | None


class Catalog:
    REQUIRED_COLUMNS = {"sku", "name", "unit", "price"}

    def __init__(self, items: list[CatalogItem]) -> None:
        if not items:
            raise ValueError("Catalog is empty")
        self.items = items

    @classmethod
    def from_csv(cls, path: str | Path) -> "Catalog":
        path = Path(path)
        items: list[CatalogItem] = []
        seen_skus: set[str] = set()

        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            # Проверяем структуру каталога сразу при загрузке:
            # matcher дальше может рассчитывать на корректный формат данных.
            missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Catalog is missing required columns: {sorted(missing)}")

            for line_number, row in enumerate(reader, start=2):
                sku = (row.get("sku") or "").strip()
                name = (row.get("name") or "").strip()
                unit = (row.get("unit") or "").strip()
                raw_price = (row.get("price") or "").strip()

                # SKU — идентификатор товара, поэтому дубликат означает
                # неоднозначность каталога и лучше должен сломать запуск,
                # чем привести к неправильному matched.
                if not sku or not name:
                    raise ValueError(f"Empty sku/name at CSV line {line_number}")
                if sku in seen_skus:
                    raise ValueError(f"Duplicate sku {sku!r} at CSV line {line_number}")

                try:
                    price = float(raw_price)
                except ValueError as exc:
                    raise ValueError(f"Invalid price at CSV line {line_number}: {raw_price!r}") from exc

                pack_match = _PACK_COUNT_RE.search(normalize_text(name))
                items.append(
                    CatalogItem(
                        sku=sku,
                        name=name,
                        unit=unit,
                        price=price,
                        normalized_name=normalize_text(name),
                        dimensions=extract_dimensions(name),
                        codes=extract_codes(name),
                        quantities=extract_quantities(name),
                        numbers=extract_numbers(name),
                        pack_count=int(pack_match.group(1)) if pack_match else None,
                    )
                )
                seen_skus.add(sku)

        return cls(items)
