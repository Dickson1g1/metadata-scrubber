"""
Concurrent batch scrubber using ThreadPoolExecutor.

Why threads (not multiprocessing) for file I/O?
  File operations — reading, writing, compressing — spend most time waiting
  on disk I/O. During that wait the GIL (Global Interpreter Lock) is released,
  so multiple threads can run concurrently on different files.
  Processes would add spawn overhead and IPC cost for no benefit here.

Routing logic:
  Each file is detected (magic bytes), then dispatched to the appropriate
  scrubber function. If a file type is unsupported it is skipped with a note.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .detector import FileType, detect
from .scrub_image  import scrub_image
from .scrub_pdf    import scrub_pdf
from .scrub_office import scrub_office


# Maps FileType to the scrubber function that handles it
SCRUBBERS = {
    FileType.JPEG: scrub_image,
    FileType.PNG:  scrub_image,
    FileType.PDF:  scrub_pdf,
    FileType.DOCX: scrub_office,
    FileType.XLSX: scrub_office,
    FileType.PPTX: scrub_office,
}


def _process_one(path: Path, dry_run: bool) -> dict:
    """
    Detect file type and call the appropriate scrubber.
    Returns a result dict from the scrubber, or a skip/error dict.
    This function runs inside a worker thread.
    """
    file_type = detect(path)

    if file_type == FileType.UNKNOWN:
        # Not a supported format — skip gracefully
        return {
            "path":           path,
            "success":        False,
            "fields_removed": [],
            "error":          "Unsupported file type",
            "skipped":        True,
        }

    scrubber = SCRUBBERS[file_type]
    result   = scrubber(path, dry_run=dry_run)
    result["file_type"] = file_type.name
    result.setdefault("skipped", False)
    return result


def batch_scrub(
    paths:       list[Path],
    dry_run:     bool = False,
    max_workers: int  = 8,
    on_progress  = None,
) -> list[dict]:
    """
    Scrub metadata from a list of files concurrently.

    Parameters
    ----------
    paths : list[Path]
        Files to process.
    dry_run : bool
        If True, report what would be removed without modifying files.
    max_workers : int
        Thread pool size (default 8 — good balance for I/O-bound work).
    on_progress : callable | None
        Optional callback(path, result) called as each file completes.

    Returns
    -------
    list[dict]
        One result dict per file.
    """
    results = []

    # ThreadPoolExecutor manages the thread pool lifecycle automatically.
    # The 'with' block ensures all threads are joined before we return.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs at once — executor queues any that exceed max_workers
        future_to_path = {
            executor.submit(_process_one, path, dry_run): path
            for path in paths
        }

        # as_completed() yields futures as they finish — we process
        # results immediately rather than waiting for all to complete.
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
            except Exception as exc:
                # A thread crashed unexpectedly — capture the error
                result = {
                    "path":           path,
                    "success":        False,
                    "fields_removed": [],
                    "error":          f"Unexpected error: {exc}",
                    "skipped":        False,
                }

            results.append(result)

            # Fire the progress callback so the CLI can print live updates
            if on_progress:
                try:
                    on_progress(path, result)
                except Exception:
                    pass   # never let a callback crash the worker

    return results


def collect_files(root: Path, recursive: bool = False) -> list[Path]:
    """
    Collect all files under a directory (optionally recursively).
    Only returns files — directories and symlinks are skipped.

    Parameters
    ----------
    root : Path
        A file path (returned as-is) or a directory to scan.
    recursive : bool
        If True, walk all subdirectories. If False, top-level only.

    Returns
    -------
    list[Path]
        All file paths found.
    """
    if root.is_file():
        return [root]

    if not root.is_dir():
        return []

    glob_pattern = "**/*" if recursive else "*"
    return [p for p in root.glob(glob_pattern) if p.is_file()]
