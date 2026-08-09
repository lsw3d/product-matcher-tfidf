from fastapi.testclient import TestClient


def test_api_contract(client: TestClient) -> None:
    response = client.post(
        "/match",
        json={
            "messages": [
                "дрель ударная prowerk pw-750 в наличии?",
                "нужен кабель",
                "где находится ваш магазин",
            ]
        },
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


def test_api_preserves_order_and_candidate_contract(client: TestClient) -> None:
    messages = [
        "где находится ваш магазин",
        "дрель ударная prowerk pw-750 в наличии?",
        "нужен кабель",
    ]

    response = client.post(
        "/match",
        json={"messages": messages},
    )

    assert response.status_code == 200

    results = response.json()["results"]

    # Результаты должны идти в том же порядке, что и сообщения в запросе.
    assert [result["message"] for result in results] == messages

    assert results[0]["status"] == "not_found"
    assert results[0]["candidates"] == []

    assert results[1]["status"] == "matched"
    assert len(results[1]["candidates"]) == 1

    assert results[2]["status"] == "ambiguous"
    assert 2 <= len(results[2]["candidates"]) <= 3

    # Проверяем контракт каждого результата и каждого кандидата.
    for result in results:
        assert set(result) == {"message", "status", "candidates"}
        assert result["status"] in {"matched", "ambiguous", "not_found"}

        for candidate in result["candidates"]:
            assert set(candidate) == {"sku", "confidence"}
            assert isinstance(candidate["sku"], str)
            assert isinstance(candidate["confidence"], (int, float))
            assert 0 <= candidate["confidence"] <= 1


def test_empty_batch(client: TestClient) -> None:
    response = client.post(
        "/match",
        json={"messages": []},
    )

    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_invalid_contract_returns_422(client: TestClient) -> None:
    assert client.post("/match", json={}).status_code == 422
    assert client.post("/match", json={"messages": "oops"}).status_code == 422
    assert client.post("/match", json={"messages": [123]}).status_code == 422
    assert client.post("/match", json={"messages": [None]}).status_code == 422
