from pathlib import Path

import pytest

from app.catalog import Catalog


def _write_catalog(path: Path, rows: str) -> Path:
    path.write_text(rows, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "rows",
    [
        "sku,name,price\nSKU-1,Товар,10\n",
        "sku,name,unit,price\nSKU-1,Товар,,10\n",
        "sku,name,unit,price\nSKU-1,Товар,шт,nan\n",
        "sku,name,unit,price\nSKU-1,Товар,шт,-1\n",
    ],
)
def test_invalid_catalog_data_is_rejected(
    tmp_path: Path,
    rows: str,
) -> None:
    path = _write_catalog(tmp_path / "catalog.csv", rows)

    with pytest.raises(ValueError):
        Catalog.from_csv(path)


def test_duplicate_sku_is_rejected(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "catalog.csv",
        "sku,name,unit,price\n"
        "SKU-1,Первый,шт,10\n"
        "SKU-1,Второй,шт,20\n",
    )

    with pytest.raises(ValueError, match="Duplicate sku"):
        Catalog.from_csv(path)


def test_empty_catalog_is_rejected(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "catalog.csv",
        "sku,name,unit,price\n",
    )

    with pytest.raises(ValueError, match="Catalog is empty"):
        Catalog.from_csv(path)
