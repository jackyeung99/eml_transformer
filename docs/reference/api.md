# API Reference

The FastAPI application loads `configs/prod.yaml` during startup. Interactive OpenAPI documentation is available at `/docs` when the service is running.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health |
| GET | `/sources` | Configured source names |
| GET | `/records?source={name}` | Paginated Silver records |
| GET | `/datasets` | Configured datasets |
| GET | `/datasets/{dataset_name}` | Paginated model-ready dataset |
| GET | `/models` | Configured models and output references |
| GET | `/models/{model_name}` | Stored model metadata |
| GET | `/models/{model_name}/parameters` | Features, settings, metrics, and diagnostics |
| GET | `/models/{model_name}/forecasts` | Paginated stored forecasts |

Dataset endpoints accept `limit` and `offset`. `/records` limits pages to 1,000 rows; dataset and forecast endpoints allow up to 10,000. Unknown definitions or empty stored datasets return 404. Storage-read failures return 500.

Examples:

```bash
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/records?source=eia_region&limit=100&offset=0'
curl 'http://127.0.0.1:8000/datasets/hourly_load?limit=100'
curl http://127.0.0.1:8000/models
curl 'http://127.0.0.1:8000/models/miso_hourly_load_sarimax/forecasts?limit=100'
```

Responses serialize datetimes as ISO-8601 strings. Authentication, filtering beyond pagination, and API versioned routes are not currently implemented.
