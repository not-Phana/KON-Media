"""File and filesystem management for KON Media.

Handles Windows filename sanitization, collision/overwrite protection,
temporary file cleanup, and safe Windows Explorer integration.
"""

import os
import re
import subprocess
from pathlib import Path
from backend.config import DOWNLOADS_DIR

# Windows reserved device names
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

_ILLEGAL_CHARS_PATTERN = re.compile(r'[\x00-\x1f\\/:*?"<>|]')


def sanitize_filename(title: str, ext: str = "") -> str:
    """Sanitize a raw title into a safe Windows filename.

    - Removes characters illegal on Windows NTFS/FAT32.
    - Prevents collisions with Windows reserved device names.
    - Truncates long names to prevent exceeding MAX_PATH.
    - Normalizes extension.
    """
    if not title:
        title = "media_download"

    # Normalize extension (ensure leading dot if non-empty)
    ext = ext.strip()
    if ext and not ext.startswith("."):
        ext = f".{ext}"

    # Remove illegal characters
    cleaned = _ILLEGAL_CHARS_PATTERN.sub("_", title)

    # Collapse multiple underscores and spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")

    # If completely empty after sanitization
    if not cleaned:
        cleaned = "media_download"

    # Check for reserved device names
    base_upper = cleaned.split(".")[0].upper()
    if base_upper in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    # Truncate base name to 100 characters
    max_base_len = 100
    if len(cleaned) > max_base_len:
        cleaned = cleaned[:max_base_len].rstrip(" .")

    return f"{cleaned}{ext}"


def get_unique_destination_path(directory: Path, filename: str) -> Path:
    """Return a non-colliding destination path.

    If 'video.mp4' already exists, returns 'video (1).mp4', etc.,
    preventing accidental overwriting of existing files.
    """
    dest_path = directory / filename
    if not dest_path.exists():
        return dest_path

    p = Path(filename)
    stem = p.stem
    suffix = p.suffix

    counter = 1
    while True:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = directory / candidate_name
        if not candidate_path.exists():
            return candidate_path
        counter += 1


def open_in_file_explorer(file_path: Path, allowed_root: Path = None) -> bool:
    """Open Windows File Explorer with the specific downloaded file selected.

    Restricts operations to files strictly inside the allowed downloads directory
    to prevent arbitrary filesystem traversal.
    """
    try:
        resolved_file = file_path.resolve()
        resolved_root = (allowed_root or DOWNLOADS_DIR).resolve()

        # Security check: must reside inside allowed directory
        if not resolved_file.is_relative_to(resolved_root):
            raise PermissionError("Access denied: path outside allowed downloads directory.")

        if resolved_file.exists():
            # Use explorer.exe /select,"<path>" to highlight the file
            subprocess.Popen(
                ["explorer.exe", f"/select,{str(resolved_file)}"],
                shell=False
            )
            return True
        elif resolved_root.exists():
            # If the file itself was moved/deleted, open the downloads directory
            subprocess.Popen(
                ["explorer.exe", str(resolved_root)],
                shell=False
            )
            return True
        return False
    except Exception:
        return False


def cleanup_partial_files(file_prefix: str, directory: Path) -> None:
    """Safely remove leftover partial or temporary files for a given job.

    Removes any intermediate output matching '{file_prefix}.*' or partial files
    ending in '.part', '.ytdl', '.temp'.
    """
    try:
        if not directory.exists() or not file_prefix:
            return
        # Remove any task-prefixed temporary outputs
        for item in directory.glob(f"{file_prefix}.*"):
            if item.is_file():
                try:
                    item.unlink(missing_ok=True)
                except OSError:
                    pass
        # Remove any trailing partial markers
        for item in directory.glob(f"{file_prefix}*"):
            if item.is_file() and (item.suffix in (".part", ".ytdl", ".temp") or item.name.endswith(".temp")):
                try:
                    item.unlink(missing_ok=True)
                except OSError:
                    pass
    except Exception:
        pass
