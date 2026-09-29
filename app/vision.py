from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort
from ultralytics import YOLO

from app.config import get_settings


@dataclass(frozen=True)
class FaceSample:
    embedding: np.ndarray
    confidence: float
    quality: float


class FaceEngine:
    def __init__(self) -> None:
        settings = get_settings()
        self.detector = YOLO(settings.yolo_model)
        self.encoder = ort.InferenceSession(settings.arcface_model, providers=["CPUExecutionProvider"])
        self.input_name = self.encoder.get_inputs()[0].name
        self.model_version = f"{settings.yolo_model}|{settings.arcface_model}"

    def extract(self, image_bytes: bytes) -> FaceSample:
        raw = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image")
        prediction = self.detector.predict(image, verbose=False, conf=0.6)[0]
        boxes = prediction.boxes
        if boxes is None or len(boxes) != 1:
            raise ValueError("Exactly one face must be visible")
        xyxy = boxes.xyxy[0].cpu().numpy().astype(int)
        confidence = float(boxes.conf[0].cpu().item())
        height, width = image.shape[:2]
        x1, y1, x2, y2 = xyxy
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        face = image[y1:y2, x1:x2]
        if face.size == 0:
            raise ValueError("Invalid face region")
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        area_ratio = float((x2 - x1) * (y2 - y1) / (width * height))
        quality = min(sharpness / 150.0, 1.0) * min(area_ratio / 0.08, 1.0)
        if sharpness < 35 or brightness < 35 or brightness > 225 or area_ratio < 0.02:
            raise ValueError("Image quality is insufficient")
        blob = cv2.resize(face, (112, 112)).astype(np.float32)
        blob = cv2.cvtColor(blob, cv2.COLOR_BGR2RGB)
        blob = (blob - 127.5) / 127.5
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        embedding = self.encoder.run(None, {self.input_name: blob})[0][0].astype(np.float32)
        embedding /= max(float(np.linalg.norm(embedding)), 1e-12)
        return FaceSample(embedding=embedding, confidence=confidence, quality=quality)

