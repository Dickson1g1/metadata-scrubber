"""
File type detection using magic bytes (file signatures).

Why not use file extensions?
  Extensions can be wrong, missing, or intentionally misleading.
  Every file format has a unique sequence of bytes at the start called
  a "magic number" or "file signature". Checking those bytes is the
  authoritative way to identify a file's true format.

Examples:
  JPEG files always start with FF D8 FF
  PNG  files always start with 89 50 4E 47 0D 0A 1A 0A
  PDF  files always start with 25 50 44 46 (%PDF)
  ZIP  files always start with 50 4B 03 04 (PK..)
  Office .docx/.xlsx/.pptx files are ZIP archives internally —
  we peek inside the ZIP to find the content type.
"""

import zipfile
from enum import Enum, auto
from pathlib import Path


class FileType(Enum):
    """Supported file types that the scrubber can process."""
    JPEG    = auto()
    PNG     = auto()
    PDF     = auto()
    DOCX    = auto()   # Word
    XLSX    = auto()   # Excel
    PPTX    = auto()   # PowerPoint
    UNKNOWN = auto()   # unsupported or unrecognised format


# Magic byte signatures mapped to file types.
# Each entry is (offset, bytes_to_match, FileType).
# offset=0 means the signature starts at the very beginning of the file.
SIGNATURES = [
    (0, b'\xff\xd8\xff',                    FileType.JPEG),
    (0, b'\x89PNG\r\n\x1a\n',              FileType.PNG),
    (0, b'%PDF',                             FileType.PDF),
    # Office Open XML formats (.docx, .xlsx, .pptx) are all ZIP files.
    # We detect ZIP first, then peek inside to distinguish Word/Excel/PPT.
    (0, b'PK\x03\x04',                     FileType.DOCX),  # placeholder — refined below
]

# Maximum bytes to read for signature detection
MAGIC_READ_BYTES = 8


def detect(path: Path) -> FileType:
    """
    Detect the true file type of a file by reading its magic bytes.

    Parameters
    ----------
    path : Path
        Path to the file to inspect.

    Returns
    -------
    FileType
        The detected file type, or FileType.UNKNOWN if unrecognised.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(MAGIC_READ_BYTES)
    except (OSError, PermissionError):
        return FileType.UNKNOWN

    # Check JPEG: FF D8 FF
    if header[:3] == b'\xff\xd8\xff':
        return FileType.JPEG

    # Check PNG: 8-byte signature
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return FileType.PNG

    # Check PDF: starts with %PDF
    if header[:4] == b'%PDF':
        return FileType.PDF

    # Check ZIP (all Office Open XML formats are ZIP archives)
    if header[:4] == b'PK\x03\x04':
        return _detect_office_type(path)

    return FileType.UNKNOWN


def _detect_office_type(path: Path) -> FileType:
    """
    Distinguish between .docx, .xlsx, and .pptx by inspecting the ZIP contents.

    Office Open XML files contain a [Content_Types].xml file inside the ZIP.
    That file's content identifies the Office application:
      - Word:       'application/vnd.openxmlformats-officedocument.wordprocessingml'
      - Excel:      'application/vnd.openxmlformats-officedocument.spreadsheetml'
      - PowerPoint: 'application/vnd.openxmlformats-officedocument.presentationml'
    """
    try:
        with zipfile.ZipFile(path, "r") as zf:
            # [Content_Types].xml is always present in a valid OOXML file
            if "[Content_Types].xml" not in zf.namelist():
                return FileType.UNKNOWN

            content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")

            if "wordprocessingml" in content_types:
                return FileType.DOCX
            if "spreadsheetml" in content_types:
                return FileType.XLSX
            if "presentationml" in content_types:
                return FileType.PPTX

    except (zipfile.BadZipFile, KeyError, OSError):
        pass

    return FileType.UNKNOWN


def is_supported(path: Path) -> bool:
    """Return True if this file's type can be scrubbed."""
    return detect(path) != FileType.UNKNOWN
