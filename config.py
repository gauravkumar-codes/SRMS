"""Central place for file locations.

Works both when run as `python main.py` and when frozen into an .exe/.app by
PyInstaller:
  * the database lives next to the program (APP_DIR), so it is never lost
  * images are read from the bundled resources (RESOURCE_DIR)
"""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):                      # packaged build
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:                                                  # normal Python run
    APP_DIR = RESOURCE_DIR = Path(__file__).resolve().parent

BASE_DIR = APP_DIR
DB_PATH = APP_DIR / "rms.db"
IMAGE_DIR = RESOURCE_DIR / "images"


def image_path(name: str) -> str:
    """Absolute path of a file inside the images folder."""
    return str(IMAGE_DIR / name)
