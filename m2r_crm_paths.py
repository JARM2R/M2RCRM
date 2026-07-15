"""
M2R CRM Path Resolution
========================
Provides consistent paths for assets and writable files,
whether running from source or from a PyInstaller bundle.
"""

import sys
import shutil
from datetime import datetime
from pathlib import Path


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, 'frozen', False)


if _is_frozen():
    # PyInstaller puts read-only data in sys._MEIPASS (_internal folder)
    ASSET_DIR = Path(sys._MEIPASS)
    # Writable location = folder containing the .exe
    APP_DIR = Path(sys.executable).parent
else:
    # Development: everything lives next to the source files
    ASSET_DIR = Path(__file__).parent
    APP_DIR = Path(__file__).parent


def ensure_writable_database():
    """Copy the seed database from the bundle to APP_DIR on first run.

    Only acts when frozen and the writable copy does not yet exist.
    """
    if not _is_frozen():
        return

    target = APP_DIR / "m2r_crm.db"
    if target.exists():
        return

    seed = ASSET_DIR / "m2r_crm.db"
    if seed.exists():
        shutil.copy2(seed, target)


def backup_database(keep: int = 10) -> None:
    """Create a timestamped backup of the database on startup.

    Backups are stored in a 'backups' folder next to the database.
    Only the most recent `keep` backups are retained.
    """
    db_path = APP_DIR / "m2r_crm.db"
    if not db_path.exists():
        return

    backup_dir = APP_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"m2r_crm_{timestamp}.db"
    shutil.copy2(db_path, backup_path)

    # Remove oldest backups beyond the keep limit
    backups = sorted(backup_dir.glob("m2r_crm_*.db"))
    for old in backups[:-keep]:
        old.unlink()
