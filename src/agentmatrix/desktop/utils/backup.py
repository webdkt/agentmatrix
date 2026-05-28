import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

BACKUP_KEEP_COUNT = 5


def backup_file(file_path: Path, backup_dir: Path, prefix: str) -> Optional[Path]:
    if not file_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{prefix}_{timestamp}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)
    return backup_path


def cleanup_old_backups(backup_dir: Path, prefix: str, keep: int = BACKUP_KEEP_COUNT):
    if not backup_dir.exists():
        return
    backups = sorted(
        backup_dir.glob(f"{prefix}_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink()