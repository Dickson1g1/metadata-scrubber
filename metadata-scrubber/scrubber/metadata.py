"""
Metadata extraction for before/after comparison reports.

We read metadata BEFORE scrubbing (so the report shows what was removed)
and AFTER scrubbing (to verify nothing sensitive remains).
All functions return a flat dict of field_name -> value strings.
"""

from pathlib import Path
from .detector import FileType, detect


def read_metadata(path: Path) -> dict[str, str]:
    """
    Extract all readable metadata from a file.
    Returns a dict of {field_name: value} for display in the report.
    Returns an empty dict if the file type is unsupported or reading fails.
    """
    file_type = detect(path)

    readers = {
        FileType.JPEG: _read_image_metadata,
        FileType.PNG:  _read_image_metadata,
        FileType.PDF:  _read_pdf_metadata,
        FileType.DOCX: _read_office_metadata,
        FileType.XLSX: _read_office_metadata,
        FileType.PPTX: _read_office_metadata,
    }

    reader = readers.get(file_type)
    if reader is None:
        return {}

    try:
        return reader(path)
    except Exception:
        return {}


def _read_image_metadata(path: Path) -> dict[str, str]:
    """
    Extract EXIF and other metadata from JPEG/PNG images using Pillow.

    EXIF (Exchangeable Image File Format) is embedded in JPEG files and
    stores camera settings, GPS coordinates, timestamps, software, and more.
    PNG files can contain tEXt chunks with author, copyright, and tool info.

    The privacy-sensitive fields to watch for:
      GPSInfo (tag 34853) — exact GPS location where photo was taken
      Make/Model (tags 271/272) — camera manufacturer and model
      DateTime* (tags 306/36867/36868) — exact timestamps
      Artist/Copyright (tags 315/33432) — author identity
      Software (tag 305) — editing software used (can fingerprint the user)
    """
    from PIL import Image
    from PIL.ExifTags import TAGS

    meta = {}
    with Image.open(path) as img:
        # getexif() returns an IFD (Image File Directory) mapping tag IDs to values
        exif_data = img.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                # TAGS maps numeric IDs to human-readable names
                tag_name = TAGS.get(tag_id, str(tag_id))
                # Truncate long values (e.g. thumbnail data) for display
                meta[tag_name] = str(value)[:200]

        # PNG tEXt chunks are stored in img.info dict
        for key, value in img.info.items():
            if key not in ("exif",):   # skip raw EXIF blob (already parsed above)
                meta[f"PNG:{key}"] = str(value)[:200]

    return meta


def _read_pdf_metadata(path: Path) -> dict[str, str]:
    """
    Extract metadata from PDF files using PyMuPDF (fitz).

    PDF metadata is stored in the document's Info dictionary and can
    contain: Title, Author, Subject, Keywords, Creator, Producer,
    CreationDate, ModDate. The Producer field reveals what software
    created or modified the PDF — a common privacy leak.
    """
    import fitz  # PyMuPDF

    meta = {}
    with fitz.open(path) as doc:
        pdf_meta = doc.metadata
        if pdf_meta:
            for key, value in pdf_meta.items():
                if value:   # skip empty fields
                    meta[key] = str(value)

        # XMP metadata — a more modern XML-based metadata format embedded in PDFs
        xmp = doc.get_xml_metadata()
        if xmp:
            meta["xmp_present"] = f"Yes ({len(xmp)} bytes)"

    return meta


def _read_office_metadata(path: Path) -> dict[str, str]:
    """
    Extract core metadata from Office Open XML files.

    All OOXML formats (docx/xlsx/pptx) store document properties in
    docProps/core.xml inside the ZIP archive. This file contains:
      creator, lastModifiedBy, created, modified, revision, description...

    Word .docx files additionally store revision history, tracked changes,
    and author names in the document body — we report those fields too.
    """
    import zipfile
    from xml.etree import ElementTree as ET

    meta = {}
    # Namespace used in core.xml — required to parse the XML correctly
    ns = {
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
    }

    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "docProps/core.xml" in zf.namelist():
                xml_data = zf.read("docProps/core.xml")
                root = ET.fromstring(xml_data)

                # Extract each known property element
                fields = {
                    "creator":         "dc:creator",
                    "lastModifiedBy":  "cp:lastModifiedBy",
                    "created":         "dcterms:created",
                    "modified":        "dcterms:modified",
                    "revision":        "cp:revision",
                    "description":     "dc:description",
                    "keywords":        "cp:keywords",
                }
                for label, xpath in fields.items():
                    # ET.find with namespace dict
                    prefix, tag = xpath.split(":")
                    elem = root.find(f"{{{ns[prefix]}}}{tag}")
                    if elem is not None and elem.text:
                        meta[label] = elem.text

            # app.xml contains application name and version
            if "docProps/app.xml" in zf.namelist():
                app_xml = zf.read("docProps/app.xml").decode("utf-8", errors="ignore")
                # Simple text search — app.xml is small and simple
                for tag in ["Application", "AppVersion", "Company"]:
                    start = app_xml.find(f"<{tag}>")
                    end   = app_xml.find(f"")
                    if start != -1 and end != -1:
                        meta[f"app:{tag}"] = app_xml[start+len(tag)+2:end]

    except Exception:
        pass

    return meta
