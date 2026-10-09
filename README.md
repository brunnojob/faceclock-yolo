# FaceClock Review API

Face detection, embeddings, identification proposals, and human review before attendance recording, with encrypted templates and an authenticated audit trail.

## Run

Requirements: Python 3.11+, FastAPI, YOLO, and ONNX.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Behavior

Set `FACECLOCK_API_KEY` to at least 32 characters. `FACECLOCK_ENCRYPTION_KEY` and `FACECLOCK_AUDIT_KEY` must contain random 32-byte keys encoded as base64. For vision processing, install `requirements-vision.txt` and supply compatible models through `FACECLOCK_DETECTOR` and `FACECLOCK_ENCODER`. Model weights and accuracy validation are not included. Enrollment requires consent and 3 to 8 images. `/v1/export` produces a report. Revocation deletes templates.

## Result synchronization

The [operations archive](https://vercel-home-telemetry-api.vercel.app/laboratory.html?project=faceclock-yolo) stores execution results. Supabase migrations are in the [API repository](https://github.com/brunnojob/vercel-home-telemetry-api/tree/main/supabase/migrations).

```sh
python cloud/sync.py enqueue result.json --project faceclock-yolo
python cloud/sync.py sync
```

Set `BRUNNODEV_ACCESS_TOKEN` to your session token. The SQLite outbox retains reports until the server confirms persistence; identical content does not create duplicate records. Tokens are not stored in source code. To run the synchronization tests:

```sh
python -m unittest discover -s cloud
```
