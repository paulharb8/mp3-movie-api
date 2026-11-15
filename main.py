import io
import logging

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    HealthResponse,
    MovieDataResponse,
    MovieProcessingReport,
    MovieStorage,
    MovieUploadInfo,
    ProcessConfig,
    log_requests,
    setup_logging,
)
from src.storage import MOVIE_COLUMNS

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse CSV file")

    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        raise HTTPException(
            status_code=400, detail=f"CSV must contain exactly these columns: {MOVIE_COLUMNS}"
        )
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    df = df[MOVIE_COLUMNS]

    storage.save(df)
    logger.info(f"Uploaded movies: filename={file.filename}, rows={len(df)}")
    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    logger.info(f"Retrieved movies: returned_rows={len(data)}, total_rows={total_rows}")
    return {"data": data, "total_rows": total_rows}


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(
        f"Queried movies: columns={columns}, min_rating={min_rating}, returned_rows={len(results)}"
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    df = storage.get()
    if df.empty:
        raise HTTPException(status_code=400, detail="No movies stored. Upload a CSV first.")

    config_dict = config.model_dump()
    try:
        validated = validate_dataframe(
            df,
            config_dict["validation"]["required_columns"],
            config_dict["validation"]["numeric_columns"],
        )
        processed = process_data(validated, config_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    report = create_cleaning_report(validated, processed)
    validation_removed = len(df) - len(validated)
    storage.save(processed)
    logger.info(
        f"Processed movies: validation_removed={validation_removed}, "
        f"rows_before={report['rows_before']}, rows_after={report['rows_after']}"
    )
    return {"validation_rows_removed": validation_removed, "cleaning_report": report}
