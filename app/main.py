import base64
import hmac
import os
from pathlib import Path
import threading
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form, Header
from pydantic import BaseModel, Field
from .core import AttendanceStore
from .vision import VisionPipeline

app = FastAPI(title="FaceClock Review API", version="2.0.0")
lock = threading.RLock()
store = None
vision = None


def authorized(x_api_key: str = Header(default="")):
    expected = os.environ.get("FACECLOCK_API_KEY", "")
    if len(expected) < 32:
        raise HTTPException(503, "API key is not configured")
    if not hmac.compare_digest(expected, x_api_key):
        raise HTTPException(401, "Unauthorized")


def resources(load_vision=False):
    global store, vision
    with lock:
        if store is None:
            try:
                encryption = base64.b64decode(
                    os.environ["FACECLOCK_ENCRYPTION_KEY"], validate=True
                )
                audit = base64.b64decode(
                    os.environ["FACECLOCK_AUDIT_KEY"], validate=True
                )
                path = Path(
                    os.environ.get("FACECLOCK_DATABASE", ".local/attendance.db")
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                store = AttendanceStore(path, encryption, audit)
                os.chmod(path, 0o600)
            except (KeyError, ValueError) as error:
                raise HTTPException(
                    503, "Encryption and audit keys are not configured"
                ) from error
        if load_vision and vision is None:
            try:
                vision = VisionPipeline(
                    os.environ.get("FACECLOCK_DETECTOR", "models/yolov8n-face.pt"),
                    os.environ.get("FACECLOCK_ENCODER", "models/arcface.onnx"),
                )
            except (ImportError, FileNotFoundError) as error:
                raise HTTPException(
                    503, "Vision dependencies or configured models are missing"
                ) from error
    return store, vision


@app.get("/health")
def health():
    return {
        "service": "faceclock",
        "reviewRequired": True,
        "modelsLoaded": vision is not None,
    }


@app.post("/v1/employees/enroll", dependencies=[Depends(authorized)])
async def enroll(
    external_id: str = Form(),
    display_name: str = Form(),
    consent: bool = Form(),
    images: list[UploadFile] = File(),
):
    if not 3 <= len(images) <= 8:
        raise HTTPException(400, "Three to eight images required")
    payloads = [await image.read(8 * 1024 * 1024 + 1) for image in images]
    database, pipeline = resources(True)
    try:
        with lock:
            database.enroll(
                external_id,
                display_name,
                [pipeline.embed(image) for image in payloads],
                consent,
            )
        return {"enrolled": True, "employeeId": external_id}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.post("/v1/attendance/recognize", dependencies=[Depends(authorized)])
async def recognize(
    action: str = Form(), camera_id: str = Form(), image: UploadFile = File()
):
    data = await image.read(8 * 1024 * 1024 + 1)
    database, pipeline = resources(True)
    try:
        with lock:
            return database.propose(pipeline.embed(data), action, camera_id)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


class Review(BaseModel):
    reviewer: str = Field(min_length=1, max_length=120)
    approved: bool


@app.post("/v1/reviews/{review_id}", dependencies=[Depends(authorized)])
def confirm(review_id: str, decision: Review):
    database, _ = resources()
    try:
        with lock:
            return database.confirm(review_id, decision.reviewer, decision.approved)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.delete("/v1/employees/{employee_id}", dependencies=[Depends(authorized)])
def revoke(employee_id: str):
    database, _ = resources()
    with lock:
        database.revoke(employee_id)
    return {"templatesDeleted": True}


@app.get("/v1/export", dependencies=[Depends(authorized)])
def export():
    database, _ = resources()
    with lock:
        return database.export()
