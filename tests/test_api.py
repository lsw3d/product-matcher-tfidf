from fastapi.testclient import TestClient


def test_api_contract(client: TestClient) -> None:
    response = client.post(
        "/match",
        json={"messages": ["дрель ударная prowerk pw-750 в наличии?", "нужен кабель", "где находится ваш магазин"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["status"] == "matched"
    assert body["results"][0]["candidates"][0]["sku"] == "INS-0008"
    assert body["results"][1]["status"] == "ambiguous"
    assert body["results"][2] == {
        "message": "где находится ваш магазин",
        "status": "not_found",
        "candidates": [],
    }


def test_empty_batch(client: TestClient) -> None:
    response = client.post("/match", json={"messages": []})
    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_invalid_contract_returns_422(client: TestClient) -> None:
    assert client.post("/match", json={}).status_code == 422
    assert client.post("/match", json={"messages": "oops"}).status_code == 422
