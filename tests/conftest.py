from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalog import Catalog
from app.main import app
from app.matcher import ProductMatcher


ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return Catalog.from_csv(ROOT_DIR / "data" / "catalog_excel.csv")


@pytest.fixture(scope="session")
def matcher(catalog: Catalog) -> ProductMatcher:
    return ProductMatcher(catalog)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
