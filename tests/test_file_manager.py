"""Unit tests for File Manager, Windows Sanitization & Explorer Security."""

import os
import pytest
from pathlib import Path
from backend.storage.file_manager import (
    sanitize_filename,
    get_unique_destination_path,
    open_in_file_explorer,
)
from backend.config import DOWNLOADS_DIR


def test_sanitize_filename_illegal_characters():
    raw = 'Video: "My Cool Show" <Part 1>? / \\ | *'
    sanitized = sanitize_filename(raw, "mp4")
    assert ":" not in sanitized
    assert '"' not in sanitized
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert "?" not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "|" not in sanitized
    assert "*" not in sanitized
    assert sanitized.endswith(".mp4")


def test_sanitize_filename_reserved_windows_names():
    assert sanitize_filename("CON", "mp4") == "_CON.mp4"
    assert sanitize_filename("prn", "mp3") == "_prn.mp3"
    assert sanitize_filename("aux", "wav") == "_aux.wav"
    assert sanitize_filename("NUL", "m4a") == "_NUL.m4a"
    assert sanitize_filename("com1", "mp4") == "_com1.mp4"


def test_sanitize_filename_length_and_fallbacks():
    long_title = "A" * 300
    sanitized = sanitize_filename(long_title, "mp4")
    assert len(sanitized) <= 110  # 100 char base + 4 char ext
    assert sanitized.endswith(".mp4")

    # Empty fallback
    assert sanitize_filename("", "mp4") == "media_download.mp4"
    assert sanitize_filename("   ...  ", "mp4") == "media_download.mp4"


def test_unique_destination_path(tmp_path):
    # Create an initial file
    f1 = tmp_path / "test_video.mp4"
    f1.write_text("dummy")

    p2 = get_unique_destination_path(tmp_path, "test_video.mp4")
    assert p2.name == "test_video (1).mp4"

    # Create that file too
    p2.write_text("dummy")
    p3 = get_unique_destination_path(tmp_path, "test_video.mp4")
    assert p3.name == "test_video (2).mp4"


def test_open_in_file_explorer_path_traversal_protection():
    # Attempting to open a path outside DOWNLOADS_DIR must fail for security
    outside_path = Path("C:/Windows/System32/calc.exe")
    assert open_in_file_explorer(outside_path) is False
