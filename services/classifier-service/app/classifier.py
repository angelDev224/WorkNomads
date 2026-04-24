"""
Stub classifier.

In production replace this module with a real ML inference pipeline
(e.g. a fine-tuned ResNet / CLIP model served via ONNX Runtime or a
remote inference endpoint). The interface contract is:
    classify(photo_key: str) -> ClassificationResult
"""
import hashlib
import json
import random

LABELS = [
    "digital-nomad",
    "remote-worker",
    "frequent-traveller",
    "local-professional",
    "student",
]


class ClassificationResult:
    def __init__(self, label: str, confidence: float, details: dict):
        self.label = label
        self.confidence = confidence
        self.details = json.dumps(details)


def classify(photo_key: str) -> ClassificationResult:
    """
    Deterministic stub: uses a hash of the photo_key so the same key
    always returns the same result (useful for testing).
    """
    seed = int(hashlib.md5(photo_key.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    label = rng.choice(LABELS)
    confidence = round(rng.uniform(0.55, 0.99), 4)
    details = {
        "scores": {lbl: round(rng.random(), 4) for lbl in LABELS},
        "model": "stub-classifier",
    }
    # Ensure the chosen label has the highest score
    details["scores"][label] = confidence
    return ClassificationResult(label=label, confidence=confidence, details=details)
