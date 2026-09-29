from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import AttendanceEvent
from app.schemas import AttendanceAction, EnrollResponse, EventResponse, RecognitionResponse
from app.security import require_api_key
from app.service import AttendanceService
from app.vision import FaceEngine


settings = get_settings()
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="FaceClock YOLO", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache
def face_engine() -> FaceEngine:
    return FaceEngine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/employees/enroll", response_model=EnrollResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def enroll(
    request: Request,
    external_id: str = Form(min_length=1, max_length=80),
    display_name: str = Form(min_length=1, max_length=160),
    consent: bool = Form(),
    images: list[UploadFile] = File(min_length=3, max_length=8),
    db: Session = Depends(db_session),
) -> EnrollResponse:
    if not consent:
        raise HTTPException(status_code=400, detail="Explicit biometric consent is required")
    engine_instance = face_engine()
    try:
        samples = [engine_instance.extract(await image.read()) for image in images]
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    employee = AttendanceService(db).enroll(
        external_id, display_name, [sample.embedding for sample in samples], engine_instance.model_version
    )
    return EnrollResponse(employee_id=employee.id, external_id=employee.external_id, templates=len(samples))


@app.post("/v1/attendance/recognize", response_model=RecognitionResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def recognize(
    request: Request,
    action: AttendanceAction = Form(),
    camera_id: str = Form(min_length=1, max_length=80),
    image: UploadFile = File(),
    db: Session = Depends(db_session),
) -> RecognitionResponse:
    try:
        sample = face_engine().extract(await image.read())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    service = AttendanceService(db)
    employee, score = service.match(sample.embedding)
    event = service.record(employee, action.value, score, camera_id)
    return RecognitionResponse(
        event_id=event.id,
        decision=event.decision,
        action=action,
        employee_id=employee.id if employee else None,
        display_name=employee.display_name if employee else None,
        similarity=score,
        reason=event.reason,
    )


@app.get("/v1/attendance/events", response_model=list[EventResponse], dependencies=[Depends(require_api_key)])
def events(limit: int = 100, db: Session = Depends(db_session)) -> list[EventResponse]:
    rows = db.scalars(select(AttendanceEvent).order_by(AttendanceEvent.occurred_at.desc()).limit(min(limit, 500))).all()
    return [
        EventResponse(
            id=row.id,
            employee_id=row.employee_id,
            action=row.action,
            decision=row.decision,
            similarity=float(row.similarity),
            camera_id=row.camera_id,
            reason=row.reason,
            occurred_at=row.occurred_at,
            event_hash=row.event_hash,
        )
        for row in rows
    ]

