import pandas as pd
import pytest

from src import MovieStorage
from src.storage import MOVIE_COLUMNS
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    other_storage = MovieStorage(test_storage.db_path)
    df = other_storage.get()
    original = pd.read_csv("fixtures/sample_movies.csv")

    assert len(df) == 20
    assert other_storage.count_movies() == 20
    assert list(df.columns) == MOVIE_COLUMNS
    assert df["title"].tolist() == original["title"].tolist()

    storage_ids = [row["id"] for row in other_storage.select_columns(["title"], limit=100)]
    response = client.get("/movies", params={"limit": 100})
    api_ids = [row["id"] for row in response.json()["data"]]

    assert storage_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    responses = {}
    for limit in (100, 1):
        response = client.get("/movies", params={"limit": limit})
        assert response.status_code == 200
        assert main.cache.get(limit) == response.json()
        responses[limit] = response.json()

    repeated = client.get("/movies", params={"limit": 100})
    assert repeated.status_code == 200
    assert repeated.json() == responses[100]

    processed = client.post("/movies/process", json=processing_body)
    assert processed.status_code == 200
    body = processed.json()
    assert body["validation_rows_removed"] == 0
    assert body["cleaning_report"] == {
        "rows_before": 20,
        "rows_after": 16,
        "rows_removed": 4,
        "columns_before": 4,
        "columns_after": 4,
        "columns_removed": 0,
    }
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    after = client.get("/movies", params={"limit": 100})
    assert after.status_code == 200
    data = after.json()
    titles = [row["title"] for row in data["data"]]
    ids = [row["id"] for row in data["data"]]

    assert data["total_rows"] == 16
    assert titles == [f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"]
    assert ids == list(range(1, 17))
    assert main.cache.get(100) == data


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    def fail_if_called(*args, **kwargs):
        pytest.fail("A cache hit should not query the database")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()
