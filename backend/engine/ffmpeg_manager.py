"""FFmpeg detection, custom path resolution, and executable validation for KON Media."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def validate_ffmpeg_path(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Validate an FFmpeg executable from a custom path or system PATH.

    Accepts:
    - None or empty string: auto-detects from system PATH.
    - Path to an ffmpeg executable (e.g. E:\\...\\bin\\ffmpeg.exe).
    - Path to a directory containing ffmpeg.exe (e.g. E:\\...\\bin).

    Returns a structured status dictionary:
    {
        "available": bool,
        "path": Optional[str],
        "version": Optional[str],
        "source": "custom" | "path" | "none",
        "error": Optional[str],
    }
    """
    # 1. Automatic PATH detection if no custom path configured
    if not custom_path or not str(custom_path).strip():
        system_path = shutil.which("ffmpeg")
        if not system_path:
            return {
                "available": False,
                "path": None,
                "version": None,
                "source": "none",
                "error": "FFmpeg was not found in system PATH. Please configure a custom path in Settings.",
            }

        return _test_ffmpeg_executable(system_path, source="path")

    # 2. Custom path evaluation
    raw_path = str(custom_path).strip().strip('"').strip("'")
    target_path = Path(raw_path)

    if not target_path.exists():
        return {
            "available": False,
            "path": raw_path,
            "version": None,
            "source": "custom",
            "error": f"Configured path does not exist: '{raw_path}'",
        }

    # If the user pointed to a directory (e.g. C:\ffmpeg\bin)
    if target_path.is_dir():
        # Check for ffmpeg.exe (Windows) or ffmpeg (POSIX)
        candidate_exe = target_path / "ffmpeg.exe"
        if not candidate_exe.exists():
            candidate_exe = target_path / "ffmpeg"

        if not candidate_exe.exists():
            return {
                "available": False,
                "path": str(target_path),
                "version": None,
                "source": "custom",
                "error": f"Directory exists, but no 'ffmpeg.exe' or 'ffmpeg' was found in '{raw_path}'",
            }
        executable_path = str(candidate_exe)
    else:
        executable_path = str(target_path)

    return _test_ffmpeg_executable(executable_path, source="custom")


def _test_ffmpeg_executable(exe_path: str, source: str) -> Dict[str, Any]:
    """Execute 'ffmpeg -version' against a candidate binary to verify it runs and reports its version."""
    try:
        res = subprocess.run(
            [exe_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if res.returncode == 0 and res.stdout:
            # First line typically contains version string, e.g.:
            # "ffmpeg version 7.1-full_build-www.gyan.dev Copyright (c) 2000-2024 the FFmpeg developers"
            first_line = res.stdout.splitlines()[0].strip()
            return {
                "available": True,
                "path": str(exe_path),
                "version": first_line,
                "source": source,
                "error": None,
            }
        else:
            err = res.stderr.strip() or f"Process exited with non-zero code ({res.returncode})"
            return {
                "available": False,
                "path": str(exe_path),
                "version": None,
                "source": source,
                "error": err,
            }
    except PermissionError:
        return {
            "available": False,
            "path": str(exe_path),
            "version": None,
            "source": source,
            "error": "Permission denied while attempting to execute the specified FFmpeg file.",
        }
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "path": str(exe_path),
            "version": None,
            "source": source,
            "error": "Verification timed out while executing FFmpeg binary.",
        }
    except Exception as e:
        return {
            "available": False,
            "path": str(exe_path),
            "version": None,
            "source": source,
            "error": f"Execution error: {e}",
        }
