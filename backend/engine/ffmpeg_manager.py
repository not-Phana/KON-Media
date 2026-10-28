"""FFmpeg detection, custom path resolution, and executable validation for KON Media."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _find_bundled_ffmpeg() -> Optional[str]:
    """Check for bundled or package-provided FFmpeg executable."""
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return str(bundled)
    except Exception:
        pass
    return None


def validate_ffmpeg_path(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Validate an FFmpeg executable from a custom path, system PATH, or bundled package.

    Accepts:
    - None or empty string: auto-detects from system PATH or bundled imageio-ffmpeg.
    - Path to an ffmpeg executable (e.g. E:\\...\\bin\\ffmpeg.exe).
    - Path to a directory containing ffmpeg.exe (e.g. E:\\...\\bin).

    Returns a structured status dictionary:
    {
        "available": bool,
        "path": Optional[str],
        "version": Optional[str],
        "source": "custom" | "path" | "bundled" | "none",
        "error": Optional[str],
    }
    """
    # 1. Automatic PATH detection or bundled fallback if no custom path configured
    if not custom_path or not str(custom_path).strip():
        system_path = shutil.which("ffmpeg")
        if system_path:
            return _test_ffmpeg_executable(system_path, source="path")

        bundled_path = _find_bundled_ffmpeg()
        if bundled_path:
            return _test_ffmpeg_executable(bundled_path, source="bundled")

        return {
            "available": False,
            "path": None,
            "version": None,
            "source": "none",
            "error": "FFmpeg was not found in system PATH. Please configure a custom path in Settings.",
        }

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


def inspect_media_streams(file_path: str | Path, custom_ffmpeg_path: Optional[str] = None) -> Dict[str, Any]:
    """Inspect a media file using FFmpeg to verify actual video and audio streams.

    Returns:
    {
        "inspected": bool,
        "has_video": bool,
        "has_audio": bool,
        "video_codec": Optional[str],
        "audio_codec": Optional[str],
        "streams": List[str],
        "container": Optional[str],
        "error": Optional[str],
    }
    """
    path_obj = Path(file_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        return {
            "inspected": False,
            "has_video": False,
            "has_audio": False,
            "video_codec": None,
            "audio_codec": None,
            "streams": [],
            "container": None,
            "error": "File does not exist or is empty.",
        }

    status = validate_ffmpeg_path(custom_ffmpeg_path)
    if not status["available"] or not status.get("path"):
        ext = path_obj.suffix.lstrip(".").lower()
        return {
            "inspected": False,
            "has_video": ext in ("mp4", "webm", "mkv", "avi", "mov", "flv"),
            "has_audio": ext in ("mp3", "m4a", "ogg", "opus", "wav", "flac", "aac"),
            "video_codec": None,
            "audio_codec": None,
            "streams": [],
            "container": ext,
            "error": "FFmpeg not available for deep inspection.",
        }

    try:
        import re
        res = subprocess.run(
            [status["path"], "-i", str(path_obj)],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        combined_output = (res.stderr or "") + (res.stdout or "")

        video_match = re.search(r"Stream #\d+:\d+(?:\[0x[0-9a-fA-F]+\])?(?:\([a-zA-Z]+\))?: Video:\s*([a-zA-Z0-9_-]+)", combined_output, re.IGNORECASE)
        audio_match = re.search(r"Stream #\d+:\d+(?:\[0x[0-9a-fA-F]+\])?(?:\([a-zA-Z]+\))?: Audio:\s*([a-zA-Z0-9_-]+)", combined_output, re.IGNORECASE)

        has_video = video_match is not None
        has_audio = audio_match is not None
        video_codec = video_match.group(1).lower() if video_match else None
        audio_codec = audio_match.group(1).lower() if audio_match else None

        streams = []
        for line in combined_output.splitlines():
            s_line = line.strip()
            if s_line.startswith("Stream #") and ("Video:" in s_line or "Audio:" in s_line):
                streams.append(s_line)

        return {
            "inspected": True,
            "has_video": has_video,
            "has_audio": has_audio,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "streams": streams,
            "container": path_obj.suffix.lstrip(".").lower(),
            "error": None,
        }
    except Exception as e:
        ext = path_obj.suffix.lstrip(".").lower()
        return {
            "inspected": False,
            "has_video": ext in ("mp4", "webm", "mkv", "avi", "mov"),
            "has_audio": ext in ("mp3", "m4a", "ogg", "opus", "wav", "flac"),
            "video_codec": None,
            "audio_codec": None,
            "streams": [],
            "container": ext,
            "error": f"FFmpeg inspection failed: {e}",
        }
