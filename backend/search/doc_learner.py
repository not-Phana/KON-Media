"""Document knowledge extractor and Google Drive / Docs self-learning bridge.

Parses songs, soundtracks, playlists, and thematic media pairings from Google Docs,
Google Drive files, markdown notes, and text files, feeding them directly into
KON Media's SearchLearningModel to autonomously train dense embeddings and associations.
"""

import re
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.search.learning_model import SearchLearningModel
from backend.search.engine import get_shared_learning_model

log = logging.getLogger("kon_doc_learner")

# Regex patterns to detect Google Doc and Google Drive URLs
GDOCS_URL_PATTERN = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")
GDRIVE_FILE_PATTERN = re.compile(r"drive\.google\.com/(?:file/d/|open\?id=)([a-zA-Z0-9_-]+)")


def extract_doc_id_from_url(url_or_id: str) -> Tuple[Optional[str], str]:
    """Extract document/file ID and source type from a URL or raw ID string."""
    clean = url_or_id.strip()

    doc_match = GDOCS_URL_PATTERN.search(clean)
    if doc_match:
        return doc_match.group(1), "gdocs"

    drive_match = GDRIVE_FILE_PATTERN.search(clean)
    if drive_match:
        return drive_match.group(1), "gdrive"

    # If it's a bare alphanumeric ID (typically 25-45 chars)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,50}", clean):
        return clean, "gdocs"

    return None, "text"


def fetch_google_doc_content(doc_id: str) -> Tuple[str, str]:
    """Fetch content of a Google Doc using gdocs CLI or public web export fallback.

    Returns: (text_content, fetch_method)
    """
    # 1. Attempt retrieval via gdocs CLI
    try:
        proc = subprocess.run(
            ["gdocs", "readonly", "get", doc_id, "--format", "markdown"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip(), "gdocs_cli"
    except Exception as e:
        log.debug("gdocs CLI fetch failed or not configured: %s", e)

    # 2. Attempt retrieval via gdrive CLI export
    try:
        proc = subprocess.run(
            ["gdrive", "readonly", "export", doc_id, "--format", "txt"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip(), "gdrive_cli"
    except Exception as e:
        log.debug("gdrive CLI export failed: %s", e)

    # 3. Fallback: HTTP public export for docs with link sharing enabled
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(export_url)
            if resp.status_code == 200 and len(resp.text.strip()) > 10:
                return resp.text.strip(), "public_export"
            elif resp.status_code == 401 or resp.status_code == 403:
                raise PermissionError("Google Doc requires sign-in. Use 'gdocs auth login' or enable link sharing.")
    except Exception as e:
        log.warning("Google Doc HTTP export failed: %s", e)
        raise

    raise ValueError(f"Could not fetch Google Doc content for ID '{doc_id}'.")


def parse_knowledge_pairs(text: str) -> List[Tuple[str, str]]:
    """Parse media knowledge pairs from structured text, markdown, tables, or notes.

    Supports:
    - Arrow associations: 'Titanic -> Celine Dion - My Heart Will Go On'
    - Colon mappings: 'Cyberpunk Edgerunners: I Really Want to Stay at Your House'
    - Hyphen pairings: 'Interstellar - Hans Zimmer - Cornfield Chase'
    - Markdown tables: | Subject | Song Title | Artist |
    - Track by Artist: 'Bohemian Rhapsody by Queen'
    - Artist - Track: 'Daft Punk - Get Lucky'
    """
    pairs: List[Tuple[str, str]] = []
    seen = set()

    lines = text.splitlines()
    for line in lines:
        raw_line = line.strip()
        if not raw_line or raw_line.startswith("#") or raw_line.startswith("---"):
            continue

        # Strip markdown bullets
        clean_line = re.sub(r"^[\*\-\+\d\.\s]+\s*", "", raw_line).strip()
        if not clean_line:
            continue

        # Pattern A: Markdown Table rows (| Query / Context | Song / Track | [Artist] |)
        if clean_line.startswith("|") and clean_line.endswith("|"):
            parts = [p.strip() for p in clean_line.split("|")[1:-1] if p.strip()]
            if len(parts) >= 2:
                # Ignore header rows
                if any(k in parts[0].lower() for k in ("query", "movie", "film", "soundtrack", "topic", "context", "---")):
                    continue
                q = parts[0]
                target = f"{parts[2]} - {parts[1]}" if len(parts) >= 3 else parts[1]
                pair_key = (q.lower(), target.lower())
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((q, target))
            continue

        # Pattern B: Explicit arrow associations (A -> B, A => B, A --> B)
        arrow_match = re.split(r"\s*(?:->|=>|-->|↦)\s*", clean_line, maxsplit=1)
        if len(arrow_match) == 2:
            q, target = arrow_match[0].strip(), arrow_match[1].strip()
            if q and target:
                pair_key = (q.lower(), target.lower())
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((q, target))
                continue

        # Pattern C: Colon associations ('Cyberpunk 2077: I Really Want to Stay at Your House')
        if ":" in clean_line and not clean_line.startswith("http"):
            c_parts = clean_line.split(":", 1)
            q, target = c_parts[0].strip(), c_parts[1].strip()
            # Ensure query is a reasonable label and target has substance
            if 1 <= len(q.split()) <= 6 and len(target.split()) >= 1:
                pair_key = (q.lower(), target.lower())
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((q, target))
                continue

        # Pattern D: "X by Y" pattern ('Bohemian Rhapsody by Queen')
        by_match = re.match(r"^(.+?)\s+by\s+(.+)$", clean_line, re.IGNORECASE)
        if by_match:
            song, artist = by_match.group(1).strip(), by_match.group(2).strip()
            full_title = f"{artist} - {song}"
            pair_key = (song.lower(), full_title.lower())
            if pair_key not in seen:
                seen.add(pair_key)
                pairs.append((song, full_title))
                pairs.append((f"{song} song", full_title))
            continue

        # Pattern E: Standard 'Artist - Song' listing
        if " - " in clean_line:
            parts = clean_line.split(" - ", 1)
            artist, song = parts[0].strip(), parts[1].strip()
            if artist and song:
                pair_key = (song.lower(), clean_line.lower())
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append((song, clean_line))
                    pairs.append((f"{song} {artist}", clean_line))
                continue

    return pairs


class DocumentLearner:
    """Orchestrates ingesting documents and training SearchLearningModel."""

    def __init__(self, model: Optional[SearchLearningModel] = None):
        self.model = model or get_shared_learning_model()

    def learn_from_text(
        self,
        text_content: str,
        epochs: int = 5,
        source_name: str = "custom_text",
    ) -> Dict[str, Any]:
        """Parse structured text and train the neural ranking model on extracted pairs."""
        pairs = parse_knowledge_pairs(text_content)
        if not pairs:
            return {
                "status": "no_pairs_found",
                "message": "No structured media pairs or track associations could be extracted from the document.",
                "extracted_count": 0,
                "samples": [],
            }

        feedback_entries = []
        for q, target in pairs:
            feedback_entries.append({
                "query": q,
                "selected_title": target,
                "is_mismatch": False,
            })

        train_results = self.model.self_train(
            feedback_entries=feedback_entries,
            download_history=[],
            epochs=epochs,
        )

        sample_preview = [{"query": q, "target_media": target} for q, target in pairs[:6]]

        return {
            "status": "success",
            "source": source_name,
            "extracted_count": len(pairs),
            "epochs": epochs,
            "training_results": train_results,
            "sample_associations": sample_preview,
            "model_stats": self.model.get_stats(),
        }

    def learn_from_google_doc(
        self,
        url_or_id: str,
        epochs: int = 5,
    ) -> Dict[str, Any]:
        """Fetch a Google Doc / Drive file by link or ID and train the model on its contents."""
        doc_id, source_type = extract_doc_id_from_url(url_or_id)
        if not doc_id:
            raise ValueError(f"Could not parse valid Google Doc or Drive file ID from '{url_or_id}'.")

        content, method = fetch_google_doc_content(doc_id)
        res = self.learn_from_text(
            text_content=content,
            epochs=epochs,
            source_name=f"google_doc_{doc_id} (via {method})",
        )
        res["doc_id"] = doc_id
        res["fetch_method"] = method
        return res
