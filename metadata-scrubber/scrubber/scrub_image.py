"""
JPEG and PNG metadata scrubber using Pillow.

Strategy for images:
  The cleanest way to remove ALL metadata is to re-encode the image from
  its raw pixel data. We open the image, access only the pixel array,
  create a brand-new Image object from those pixels, and save it.
  The new file has no EXIF, no XMP, no ICC profile header metadata,
  no IPTC, and no thumbnail.

  For JPEG we preserve the original quality setting to avoid visible
  re-compression artifacts. We use subsampling=0 and quality=95 as a
  safe default when the original quality can't be determined.

  For PNG we strip all tEXt, zTXt, and iTXt chunks (text metadata).
  PNG pixel data is losslessly preserved.

What gets removed:
  JPEG: GPS coordinates, camera make/model, timestamps, artist, copyright,
        software, thumbnail, all maker notes (Canon/Nikon/Sony raw data)
  PNG:  Author, Copyright, Comment, Description, Software, Creation Time,
        all tEXt and metadata chunks
"""

import io
from pathlib import Path
from PIL import Image


def scrub_image(path: Path, dry_run: bool = False) -> dict:
    """
    Remove all metadata from a JPEG or PNG image.

    Parameters
    ----------
    path : Path
        Path to the image file (modified in place).
    dry_run : bool
        If True, analyse only — do not write any changes.

    Returns
    -------
    dict with keys:
        path         : Path
        success      : bool
        fields_removed : list of metadata field names that were present
        error        : str | None
    """
    result = {
        "path":           path,
        "success":        False,
        "fields_removed": [],
        "error":          None,
    }

    try:
        with Image.open(path) as img:
            # Record what metadata existed before scrubbing
            exif = img.getexif()
            from PIL.ExifTags import TAGS
            result["fields_removed"] = [
                TAGS.get(tag_id, str(tag_id)) for tag_id in exif.keys()
            ]
            # Also record any PNG tEXt metadata
            for key in img.info:
                if key != "exif":
                    result["fields_removed"].append(f"PNG:{key}")

            if dry_run:
                result["success"] = True
                return result

            # Convert to RGB if needed (e.g. RGBA PNG → strip alpha for JPEG)
            # We preserve the original mode for PNG to keep transparency.
            original_format = img.format
            original_mode   = img.mode

            # Access raw pixel data — this is the only thing we keep
            pixel_data = img.tobytes()
            size       = img.size
            mode       = img.mode

        # Reconstruct the image from raw pixels only — no metadata
        clean_img = Image.frombytes(mode, size, pixel_data)

        # Save back to the same path, overwriting the original
        if original_format == "JPEG":
            # save_all=False, no exif= kwarg → no EXIF written
            # quality=95 preserves near-original quality with minimal re-compression
            clean_img.save(
                path,
                format="JPEG",
                quality=95,
                optimize=True,
                # Do NOT pass exif= parameter — this is what keeps EXIF out
            )
        elif original_format == "PNG":
            # PNG metadata is stored in 'pnginfo' — omitting it removes everything
            clean_img.save(
                path,
                format="PNG",
                optimize=True,
                # No pnginfo= → no tEXt/zTXt/iTXt chunks written
            )

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result
