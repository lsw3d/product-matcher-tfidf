from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app.catalog import Catalog
from app.matcher import ProductMatcher
from app.schemas import MatchRequest, MatchResponse


BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "data" / "catalog_excel.csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Каталог и поисковый индекс создаём один раз при старте сервиса,
    # а не на каждый запрос. Для каталога из ~500 позиций хранение в памяти
    # проще и быстрее, чем добавление БД, которая по ТЗ здесь не требуется.
    app.state.matcher = ProductMatcher(Catalog.from_csv(CATALOG_PATH))
    yield


app = FastAPI(title="Product Matcher", lifespan=lifespan)


@app.post("/match", response_model=MatchResponse)
async def match_products(payload: MatchRequest, request: Request) -> MatchResponse:
    matcher: ProductMatcher = request.app.state.matcher
    return MatchResponse(results=matcher.match_many(payload.messages))
