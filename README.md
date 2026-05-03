# paribus-bulk-processing-system

Bulk processing system for hospital CSV uploads that integrates with the existing Hospital Directory API.

## What it does

This service exposes `POST /hospitals/bulk` and accepts a multipart CSV upload with columns for `name`, `address`, and optional `phone`. It creates hospitals one by one in the downstream Hospital Directory API, tags them with a batch ID, and activates the batch after all rows succeed.

Bonus endpoints are included for CSV validation, batch progress polling, batch detail lookup, and resuming failed batches.

## Requirements

- Python 3.10+
- `uv`

## Deployment

Render can use the provided [render.yaml](render.yaml) configuration. Set `HOSPITAL_DIRECTORY_API_BASE_URL` if you want to point the bulk processor at a different Hospital Directory deployment.

The project also includes [Dockerfile](Dockerfile) and [docker-compose.yml](docker-compose.yml) for local container runs.

## Setup

```bash
uv sync --group dev
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Test

```bash
uv run pytest -q
```

## Example request

```bash
curl -X POST "http://127.0.0.1:8000/hospitals/bulk" \
	-F "file=@hospitals.csv;type=text/csv"
```

## Bonus endpoints

- `POST /hospitals/bulk/validate` validates the CSV without creating hospitals.
- `GET /hospitals/bulk/{batch_id}/progress` returns current batch progress.
- `GET /hospitals/bulk/{batch_id}` returns the full stored batch state.
- `POST /hospitals/bulk/{batch_id}/resume` retries failed rows and activates the batch if all rows succeed.

## Docker

```bash
docker compose up --build
```

The app will be available at `http://127.0.0.1:8000`.
