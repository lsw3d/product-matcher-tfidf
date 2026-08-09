from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path

from app.normalization import parse_item


@dataclass(frozen=True, slots=True)
class CatalogItem:
    # Храним рядом с исходными данными заранее извлечённые признаки товара,
    # чтобы не парсить название каталога заново при каждом поисковом запросе.
    sku: str
    name: str
    unit: str
    price: float
    normalized_name: str
    lexical_name: str
    dimensions: tuple[tuple[float, ...], ...]
    codes: frozenset[str]
    code_variants: frozenset[str]
    qualifiers: frozenset[str]
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

            missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(
                    f"Catalog is missing required columns: {sorted(missing)}"
                )

            for line_number, row in enumerate(reader, start=2):
                sku = (row.get("sku") or "").strip()
                name = (row.get("name") or "").strip()
                unit = (row.get("unit") or "").strip()
                raw_price = (row.get("price") or "").strip()

                if not sku or not name or not unit:
                    raise ValueError(
                        f"Empty sku/name/unit at CSV line {line_number}"
                    )

                if sku in seen_skus:
                    raise ValueError(
                        f"Duplicate sku {sku!r} at CSV line {line_number}"
                    )

                try:
                    price = float(raw_price)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid price at CSV line "
                        f"{line_number}: {raw_price!r}"
                    ) from exc

                if not math.isfinite(price) or price < 0:
                    raise ValueError(
                        f"Invalid price at CSV line "
                        f"{line_number}: {raw_price!r}"
                    )

                features = parse_item(name)
                items.append(
                    CatalogItem(
                        sku=sku,
                        name=name,
                        unit=unit,
                        price=price,
                        normalized_name=features.normalized,
                        lexical_name=features.lexical,
                        dimensions=features.dimensions,
                        codes=features.codes,
                        code_variants=features.code_variants,
                        qualifiers=features.qualifiers,
                        quantities=features.quantities,
                        numbers=features.numbers,
                        pack_count=features.pack_count,
                    )
                )

                seen_skus.add(sku)

        return cls(items)
