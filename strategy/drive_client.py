"""Google Drive client — auth, list, download for the asset-ingestion pipeline.

Authentication: service account JSON path from `GOOGLE_APPLICATION_CREDENTIALS`
(Google's standard convention). The service account must have at least Viewer
access to each client's drive_folder_id (read-only is sufficient — never asks
to write).

This module is the only place we touch the Google Drive API. Higher layers
(brand_enricher, reference_ads) consume `DriveFile` dataclasses and use the
client methods.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass(frozen=True)
class DriveFile:
    """Minimal Drive file metadata. Used as a value object across the pipeline."""

    id: str
    name: str
    mime_type: str
    size: int  # 0 for folders (Drive returns no size for folders)
    modified_time: str  # ISO 8601 from Drive API; opaque key for cache invalidation
    parent_id: str

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def is_video(self) -> bool:
        return self.mime_type.startswith("video/")

    @property
    def is_pdf(self) -> bool:
        return self.mime_type == "application/pdf"

    @property
    def cache_key(self) -> str:
        """Stable key for caching: changes only when the file's content changes."""
        return f"{self.id}:{self.modified_time}"

    @property
    def stem(self) -> str:
        """Filename without extension. Used for cache file naming."""
        return Path(self.name).stem


class DriveClient:
    """Thin wrapper around the Google Drive v3 API for read-only file ingestion."""

    def __init__(self, credentials_path: str | None = None):
        path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not path:
            raise EnvironmentError(
                "GOOGLE_APPLICATION_CREDENTIALS not set and no credentials_path passed. "
                "Point it at the service account JSON. See .env.example."
            )
        if not Path(path).exists():
            raise FileNotFoundError(f"Service account JSON not found at: {path}")

        self._creds = service_account.Credentials.from_service_account_file(
            path, scopes=DRIVE_SCOPES
        )
        self._service = build("drive", "v3", credentials=self._creds, cache_discovery=False)

    def list_folder(self, folder_id: str) -> list[DriveFile]:
        """List immediate children of a folder (non-recursive). Skips trashed files."""
        files: list[DriveFile] = []
        page_token: str | None = None
        while True:
            try:
                response = (
                    self._service.files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        fields="nextPageToken, files(id, name, mimeType, size, "
                        "modifiedTime, parents)",
                        pageSize=100,
                        pageToken=page_token,
                    )
                    .execute()
                )
            except HttpError as e:
                raise DriveAccessError(
                    f"Drive API error listing folder {folder_id}: {e}"
                ) from e

            for f in response.get("files", []):
                files.append(
                    DriveFile(
                        id=f["id"],
                        name=f["name"],
                        mime_type=f["mimeType"],
                        size=int(f.get("size", 0)),
                        modified_time=f.get("modifiedTime", ""),
                        parent_id=(f.get("parents") or [folder_id])[0],
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return files

    def find_subfolder_id(self, parent_id: str, name: str) -> str | None:
        """Return the ID of an immediate-child folder by name, or None if missing."""
        for child in self.list_folder(parent_id):
            if child.is_folder and child.name == name:
                return child.id
        return None

    def list_subfolder(self, parent_id: str, subfolder_name: str) -> list[DriveFile]:
        """List files inside a named subfolder. Returns [] if the subfolder doesn't exist."""
        sub_id = self.find_subfolder_id(parent_id, subfolder_name)
        if sub_id is None:
            return []
        return [f for f in self.list_folder(sub_id) if not f.is_folder]

    def download_to(self, file_id: str, dest_path: Path) -> Path:
        """Download a Drive file to a local path. Creates parent dirs if needed."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(fileId=file_id)
        with open(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest_path

    def download_bytes(self, file_id: str) -> bytes:
        """Download file content to memory. Use only for small files (<10MB)."""
        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()


class DriveAccessError(RuntimeError):
    """Raised when the Drive API returns an error. Wraps the underlying HttpError."""
