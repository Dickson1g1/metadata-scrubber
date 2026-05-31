"""
Office Open XML metadata scrubber (Word, Excel, PowerPoint).

All OOXML formats (.docx, .xlsx, .pptx) are ZIP archives containing
XML files. Document metadata lives in two files inside the ZIP:
  docProps/core.xml  — author, timestamps, revision, keywords
  docProps/app.xml   — application name, version, company name

Strategy:
  1. Read the ZIP into memory
  2. Replace docProps/core.xml with a minimal empty version
  3. Replace docProps/app.xml with a minimal empty version
  4. Write all other ZIP entries unchanged to a new file
  5. Atomically replace the original

We handle the ZIP manually rather than using python-docx/openpyxl because:
  - All three formats use the same structure for metadata
  - A single function handles all three (DRY principle)
  - python-docx would re-serialise the entire document, risking data loss

What gets removed:
  creator, lastModifiedBy, created, modified, revision,
  description, keywords, category, contentStatus,
  Application, AppVersion, Company name
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path

# Minimal empty core.xml — preserves the namespace declarations required
# by the OOXML spec but contains no personal data.
EMPTY_CORE_XML = '''

'''.encode("utf-8")

# Minimal empty app.xml — no application name, version, or company.
EMPTY_APP_XML = '''

'''.encode("utf-8")


def scrub_office(path: Path, dry_run: bool = False) -> dict:
    """
    Remove metadata from a Word, Excel, or PowerPoint file.

    Parameters
    ----------
    path : Path
        Path to the Office file (modified in place).
    dry_run : bool
        If True, report findings but do not modify the file.

    Returns
    -------
    dict with success, fields_removed, error keys.
    """
    result = {
        "path":           path,
        "success":        False,
        "fields_removed": [],
        "error":          None,
    }

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Record what metadata files are present
            names = zf.namelist()
            if "docProps/core.xml" in names:
                # Parse and record existing fields before scrubbing
                from xml.etree import ElementTree as ET
                core_data = zf.read("docProps/core.xml")
                try:
                    root = ET.fromstring(core_data)
                    # Grab all text content from child elements
                    for child in root:
                        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if child.text and child.text.strip():
                            result["fields_removed"].append(tag)
                except ET.ParseError:
                    result["fields_removed"].append("core.xml (parse error)")

            if "docProps/app.xml" in names:
                result["fields_removed"].append("app.xml")

            if dry_run:
                result["success"] = True
                return result

            # Read all existing ZIP entries into memory
            entries = {}
            for name in names:
                entries[name] = zf.read(name)

        # Replace metadata files with empty versions
        entries["docProps/core.xml"] = EMPTY_CORE_XML
        entries["docProps/app.xml"]  = EMPTY_APP_XML

        # Write a new ZIP to a temp file, preserving all other content
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            suffix=".tmp",
        )
        os.close(tmp_fd)

        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
            for name, data in entries.items():
                # Use STORED (no compression) for XML files that Office expects
                # to be directly addressable, DEFLATED for everything else.
                compress = zipfile.ZIP_DEFLATED
                out_zf.writestr(name, data, compress_type=compress)

        # Atomic replace
        os.replace(tmp_path, path)
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        try:
            if "tmp_path" in locals():
                os.unlink(tmp_path)
        except OSError:
            pass

    return result
