"""
PDF metadata scrubber using PyMuPDF (fitz).

PDF metadata lives in two places:
  1. The Info dictionary (/Info object) — traditional key/value pairs:
     /Title, /Author, /Subject, /Keywords, /Creator, /Producer,
     /CreationDate, /ModDate
  2. XMP metadata stream — a modern XML-based metadata format embedded
     as a stream object. Often duplicates the Info dict but can contain
     additional fields.

Strategy:
  PyMuPDF's set_metadata({}) replaces the Info dictionary with an empty one.
  set_xml_metadata("") removes the XMP stream entirely.
  We then save to a new temp file and atomically replace the original.

What gets removed:
  Author, Title, Subject, Keywords, Creator (authoring tool),
  Producer (PDF generator software), CreationDate, ModDate,
  and the entire XMP metadata stream including Dublin Core fields.
"""

import os
import tempfile
from pathlib import Path


def scrub_pdf(path: Path, dry_run: bool = False) -> dict:
    """
    Remove all metadata from a PDF file.

    Parameters
    ----------
    path : Path
        Path to the PDF (modified in place).
    dry_run : bool
        If True, analyse only — do not write changes.

    Returns
    -------
    dict with success, fields_removed, error keys.
    """
    import fitz  # PyMuPDF

    result = {
        "path":           path,
        "success":        False,
        "fields_removed": [],
        "error":          None,
    }

    try:
        with fitz.open(path) as doc:
            # Read existing metadata to record what will be removed
            current_meta = doc.metadata or {}
            result["fields_removed"] = [
                k for k, v in current_meta.items() if v
            ]
            # Note if XMP metadata is present
            if doc.get_xml_metadata():
                result["fields_removed"].append("xmp_metadata")

            if dry_run:
                result["success"] = True
                return result

            # Replace the Info dictionary with an empty one.
            # PyMuPDF expects a dict with the same keys set to empty strings —
            # passing an empty dict {} clears all fields.
            empty_meta = {k: "" for k in current_meta}
            doc.set_metadata(empty_meta)

            # Remove XMP metadata stream entirely
            doc.set_xml_metadata("")

            # Save to a temp file in the same directory then rename.
            # We use the same directory so os.rename() is atomic (same filesystem).
            # fitz.open() locks the original file on some systems, so we must
            # close the document before renaming.
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=path.parent,
                suffix=".tmp",
            )
            os.close(tmp_fd)

            # garbage=4 removes unreferenced objects (cleans up orphaned metadata)
            # deflate=True compresses streams for smaller output
            # clean=True sanitises the content stream
            doc.save(
                tmp_path,
                garbage=4,
                deflate=True,
                clean=True,
            )

        # doc is now closed — safe to rename
        os.replace(tmp_path, path)   # atomic on POSIX
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        # Clean up temp file if something went wrong
        try:
            if "tmp_path" in locals():
                os.unlink(tmp_path)
        except OSError:
            pass

    return result
