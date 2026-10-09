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

## Optional report archive

Export a JSON report from the command above, then run `python cloud/sync.py enqueue result.json --project faceclock-yolo` and `python cloud/sync.py sync`. Synchronization requires `BRUNNODEV_ACCESS_TOKEN` and the external operations API; the local outbox retains unacknowledged reports.

## License

Original source and documentation are MIT licensed; see [LICENSE](LICENSE). Third-party dependencies and media retain their respective terms. Maintained by [Brunno Dev](https://brunnodev.store).
