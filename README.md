# MP3 Movie API

This project is a FastAPI application that stores one collection of movies in SQLite and serves it through a REST API. The `main.py` file defines the endpoints, `src/database.py` creates connections and the movies table, and `src/storage.py` holds the `MovieStorage` class that runs all SQL. The `data_pipeline` package from MP1 validates and cleans the data, and `src/cache.py` provides a `MovieCache` built on fakeredis. Uploading a CSV replaces the stored collection in one transaction and clears the cache. `GET /movies` returns cached responses for repeated requests with the same limit, and `GET /movies/search` filters movies with SQL. `POST /movies/process` cleans the stored movies, saves the result back to SQLite, and invalidates the cache so the next retrieval reads fresh data.

## Run the API

```bash
python -m uvicorn main:app --reload
```

## Run the tests

```bash
python -m pytest tests -v
```

## Sample processing request

Send this body to `POST /movies/process` after uploading `fixtures/sample_movies.csv`:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {"enabled": true, "columns": ["rating"], "method": "iqr", "threshold": 1.5}
  }
}
```

Expected result for the 20-row sample:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```
