from pathlib import Path
from .core import normalize


class VisionPipeline:
    def __init__(self, detector_path, encoder_path):
        import onnxruntime as ort
        from ultralytics import YOLO

        if not Path(detector_path).is_file() or not Path(encoder_path).is_file():
            raise FileNotFoundError("configured model weights are missing")
        self.detector = YOLO(detector_path)
        self.encoder = ort.InferenceSession(
            encoder_path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.encoder.get_inputs()[0].name

    def embed(self, image_bytes):
        import cv2
        import numpy as np

        if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
            raise ValueError("image missing or too large")
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None or max(image.shape[:2]) > 8192:
            raise ValueError("invalid image dimensions")
        detections = self.detector.predict(image, verbose=False, conf=0.7)[0].boxes
        if detections is None or len(detections) != 1:
            raise ValueError("exactly one face required")
        x1, y1, x2, y2 = [int(value) for value in detections.xyxy[0].tolist()]
        crop = image[
            max(0, y1) : min(image.shape[0], y2), max(0, x1) : min(image.shape[1], x2)
        ]
        if min(crop.shape[:2]) < 64:
            raise ValueError("face too small")
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < 30 or not 35 < gray.mean() < 220:
            raise ValueError("insufficient face image quality")
        rgb = cv2.cvtColor(cv2.resize(crop, (112, 112)), cv2.COLOR_BGR2RGB).astype(
            np.float32
        )
        tensor = np.expand_dims(np.transpose((rgb - 127.5) / 127.5, (2, 0, 1)), 0)
        return normalize(
            self.encoder.run(None, {self.input_name: tensor})[0].reshape(-1)
        )
