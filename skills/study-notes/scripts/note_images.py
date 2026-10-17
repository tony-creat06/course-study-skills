"""Expose the shared passive-image validation API for note rendering and publishing."""
import importlib.util
from pathlib import Path


SHARED_PATH = Path(__file__).resolve().parents[2] / 'study-planner' / 'scripts' / 'passive_images.py'
SPEC = importlib.util.spec_from_file_location('note_passive_images', SHARED_PATH)
_shared = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_shared)
MAX_IMAGE_BYTES = _shared.MAX_IMAGE_BYTES
DATA_HEADERS = _shared.DATA_HEADERS
validate_reference = _shared.validate_reference
image_data = _shared.image_data
