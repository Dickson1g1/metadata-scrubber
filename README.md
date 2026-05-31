```
 ███╗   ███╗███████╗████████╗ █████╗ ██████╗  █████╗ ████████╗ █████╗ 
 ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗
 ██╔████╔██║█████╗     ██║   ███████║██║  ██║███████║   ██║   ███████║
 ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║██║  ██║██╔══██║   ██║   ██╔══██║
 ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║██████╔╝██║  ██║   ██║   ██║  ██║
 ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝

 ███████╗ ██████╗██████╗ ██╗   ██╗██████╗ ██████╗ ███████╗██████╗ 
 ██╔════╝██╔════╝██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔════╝██╔══██╗
 ███████╗██║     ██████╔╝██║   ██║██████╔╝██████╔╝█████╗  ██████╔╝
 ╚════██║██║     ██╔══██╗██║   ██║██╔══██╗██╔══██╗██╔══╝  ██╔══██╗
 ███████║╚██████╗██║  ██║╚██████╔╝██████╔╝██████╔╝███████╗██║  ██║
 ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

   exif · pdf · office · gps · timestamps · privacy protection
```

# metadata-scrubber

> Strip EXIF data, GPS coordinates, author info, timestamps, and software
> traces from JPEG, PNG, PDF, Word, Excel, and PowerPoint files.
> Concurrent batch processing, dry-run preview, and before/after
> verification reports — all from one command.

---

## What it does

`metadata-scrubber` removes privacy-sensitive metadata embedded inside
common file formats before you share, publish, or archive them. It
detects file types by magic bytes (not extensions), processes files
concurrently for speed, and produces a verification report showing
exactly what was removed.

```
$ python scrub.py photo.jpg --verify

  ✔ photo.jpg  12 field(s) removed

  Field             Before                          After
  ──────────────    ──────────────────────────────  ──────────
  GPSInfo           {'GPSLatitude': (40, 42, ...)}  ✔ removed
  Make              Apple                           ✔ removed
  Model             iPhone 14 Pro                   ✔ removed
  DateTime          2024:03:15 14:22:01             ✔ removed
  Software          16.3.1                          ✔ removed
  Artist            John Smith                      ✔ removed
  ...

  Summary
  Files scrubbed:   1
  Fields removed:   12
```

---

## Features

- **JPEG + PNG** — strips all EXIF data including GPS coordinates, camera
  make and model, timestamps, artist, copyright, software, and thumbnails;
  rebuilds images from raw pixel data so no metadata can survive
- **PDF** — clears the Info dictionary (Author, Title, Creator, Producer,
  ModDate) and removes the XMP metadata stream entirely
- **Word / Excel / PowerPoint** — rewrites `docProps/core.xml` and
  `docProps/app.xml` inside the ZIP archive; removes author, company,
  revision history, application name, and all timestamps
- **Magic-byte file detection** — identifies file types by reading the
  first 8 bytes, not the extension; spoof-resistant and reliable
- **Concurrent batch processing** — `ThreadPoolExecutor` handles 1000+
  files efficiently; configurable worker thread count
- **Dry-run mode** — preview exactly what would be removed before making
  any changes (`--dry-run`)
- **Verification reports** — before/after comparison table for every file
  showing each field and its status (`--verify`)
- **Atomic writes** — all file modifications use tmp → rename pattern;
  a crash mid-write never corrupts the original
- **Rich colored terminal output** — progress indicators, summary panel,
  and comparison tables via `rich`
- **CI-friendly exit codes** — `0` all files scrubbed · `1` one or more
  errors

---

## What gets removed

| Format | Fields removed |
|--------|---------------|
| JPEG   | GPS coordinates, Make, Model, DateTime, DateTimeOriginal, Artist, Copyright, Software, Thumbnail, MakerNote, all EXIF tags |
| PNG    | Author, Copyright, Comment, Description, Software, Creation Time, all tEXt/zTXt/iTXt chunks |
| PDF    | Author, Title, Subject, Keywords, Creator, Producer, CreationDate, ModDate, XMP metadata stream |
| DOCX   | creator, lastModifiedBy, created, modified, revision, description, keywords, Application, AppVersion, Company |
| XLSX   | Same as DOCX |
| PPTX   | Same as DOCX |

---

## Requirements

- Python 3.10+
- [`Pillow`](https://pillow.readthedocs.io/) — JPEG/PNG processing
- [`PyMuPDF`](https://pymupdf.readthedocs.io/) — PDF processing
- [`python-docx`](https://python-docx.readthedocs.io/) — Word support
- [`openpyxl`](https://openpyxl.readthedocs.io/) — Excel support
- [`python-pptx`](https://python-pptx.readthedocs.io/) — PowerPoint support
- [`rich`](https://github.com/Textualize/rich) — terminal rendering

```bash
pip install Pillow PyMuPDF python-docx openpyxl python-pptx rich
```

---

## Installation

```bash
git clone https://github.com/Dickson1g1/metadata-scrubber.git
cd metadata-scrubber
python3 -m venv .venv && source .venv/bin/activate
pip install Pillow PyMuPDF python-docx openpyxl python-pptx rich
chmod +x scrub.py

# Optional: install system-wide
ln -s "$(pwd)/scrub.py" ~/.local/bin/scrub
```

---

## Usage

```bash
# Scrub a single file
python scrub.py photo.jpg

# Dry run — preview without modifying anything
python scrub.py photo.jpg --dry-run

# Before/after verification report
python scrub.py photo.jpg --verify

# Scrub all files in a directory
python scrub.py ~/Documents/

# Recursive — include all subdirectories
python scrub.py ~/Photos/ --recursive

# Multiple targets at once
python scrub.py report.pdf letter.docx budget.xlsx slides.pptx

# More worker threads for large batches
python scrub.py ~/Photos/ --recursive --workers 16

# Combine flags
python scrub.py ~/sensitive/ --recursive --dry-run --verify
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All files processed successfully |
| `1`  | One or more files failed or no files found |

---

## Project structure

```
metadata-scrubber/
├── scrubber/
│   ├── __init__.py
│   ├── detector.py      # magic-byte file type detection
│   ├── metadata.py      # metadata reader for before/after comparison
│   ├── scrub_image.py   # JPEG + PNG scrubber (Pillow)
│   ├── scrub_pdf.py     # PDF scrubber (PyMuPDF)
│   ├── scrub_office.py  # Word / Excel / PowerPoint scrubber
│   ├── worker.py        # ThreadPoolExecutor concurrent batch processor
│   └── display.py       # rich tables, panels, progress output
├── scrub.py             # CLI entry point
└── tests/
    └── test_scrubber.py
```

---

## Running tests

```bash
python tests/test_scrubber.py
```

---

## Concepts covered

- Magic-byte file signature detection (format-agnostic file identification)
- EXIF data structure and PIL/Pillow EXIF API
- Image reconstruction from raw pixel data (zero-metadata strategy)
- Office Open XML (OOXML) ZIP archive structure
- XML namespace parsing with `xml.etree.ElementTree`
- Atomic file writes with `tempfile.mkstemp` + `os.replace`
- `concurrent.futures.ThreadPoolExecutor` for I/O-bound batch work
- `as_completed()` for live progress output during concurrent tasks
- `rich` — `Table`, `Panel`, `Console`, `Text`

---

## License

MIT — do whatever you want, attribution appreciated.
