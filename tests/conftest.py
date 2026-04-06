import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_SERVICE_ROOT = PROJECT_ROOT / "image-service"

if str(IMAGE_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(IMAGE_SERVICE_ROOT))
