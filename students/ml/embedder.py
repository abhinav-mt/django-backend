from pathlib import Path

import numpy as np
from ai_edge_litert.interpreter import Interpreter
from PIL import Image

MODEL_PATH = Path(__file__).parent / "mobilefacenet.tflite"
INPUT_SIZE = 112
EMBEDDING_SIZE = 192

_interpreter = None


def _get_interpreter():
    global _interpreter
    if _interpreter is None:
        _interpreter = Interpreter(model_path=str(MODEL_PATH))
        _interpreter.allocate_tensors()
    return _interpreter


def get_embedding(image_file):
    """Takes a tightly cropped face image and returns 192 numbers (a list)."""
    img = Image.open(image_file).convert("RGB").resize((INPUT_SIZE, INPUT_SIZE))
    x = (np.asarray(img, dtype=np.float32) - 128.0) / 128.0
    x = np.expand_dims(x, axis=0)

    interpreter = _get_interpreter()
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()[0]
    interpreter.set_tensor(input_info["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_info["index"])[0]

    if out.shape[0] != EMBEDDING_SIZE:
        raise ValueError(f"Expected {EMBEDDING_SIZE} numbers, got {out.shape[0]}")
    return out.astype(float).tolist()