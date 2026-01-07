"""Document metadata extraction service.

Extracts EXIF data from images, metadata from videos/audio files, etc.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# Office document MIME types
OFFICE_DOCUMENT_TYPES = {
    # Microsoft Office
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # LibreOffice / OpenDocument
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    # RTF
    "application/rtf",
}


def is_office_document(document) -> bool:
    """Check if document is an Office/LibreOffice document."""
    if document.content_type in OFFICE_DOCUMENT_TYPES:
        return True

    # Also check file extension
    filename = document.filename.lower()
    office_extensions = {
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".rtf",
    }
    return any(filename.endswith(ext) for ext in office_extensions)


def can_convert_to_pdf(document) -> bool:
    """Check if document can be converted to PDF for preview.

    This requires LibreOffice to be installed on the server.
    """
    if not is_office_document(document):
        return False

    # Check if libreoffice is available
    try:
        import subprocess
        result = subprocess.run(
            ["which", "libreoffice"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def extract_image_metadata(file_path: str) -> dict[str, Any]:
    """Extract EXIF and other metadata from an image file."""
    metadata = {}
    summary = {}

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        with Image.open(file_path) as img:
            # Basic image info
            summary["dimensions"] = f"{img.width} x {img.height} px"
            metadata["Width"] = img.width
            metadata["Height"] = img.height
            metadata["Format"] = img.format
            metadata["Mode"] = img.mode

            # Get EXIF data
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)

                    # Handle bytes and complex types
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="ignore")
                        except Exception:
                            value = str(value)[:50] + "..."
                    elif hasattr(value, "__iter__") and not isinstance(value, str):
                        try:
                            value = ", ".join(str(v) for v in value[:5])
                            if len(list(value)) > 5:
                                value += "..."
                        except Exception:
                            value = str(value)[:100]

                    metadata[str(tag)] = str(value)[:200]  # Limit length

                    # Build summary
                    if tag == "Make":
                        camera_make = value
                    elif tag == "Model":
                        camera_model = value
                        if "camera_make" in dir():
                            summary["camera"] = f"{camera_make} {camera_model}"
                        else:
                            summary["camera"] = camera_model
                    elif tag == "DateTimeOriginal":
                        summary["date_taken"] = value
                    elif tag == "ExposureTime":
                        if hasattr(value, "numerator"):
                            summary["exposure"] = f"{value.numerator}/{value.denominator}s"
                        else:
                            summary["exposure"] = str(value)
                    elif tag == "FNumber":
                        if hasattr(value, "numerator"):
                            summary["aperture"] = f"f/{value.numerator/value.denominator:.1f}"
                        else:
                            summary["aperture"] = f"f/{value}"
                    elif tag == "ISOSpeedRatings":
                        summary["iso"] = str(value)
                    elif tag == "FocalLength":
                        if hasattr(value, "numerator"):
                            summary["focal_length"] = f"{value.numerator/value.denominator:.1f}mm"
                        else:
                            summary["focal_length"] = f"{value}mm"
                    elif tag == "GPSInfo":
                        # Extract GPS coordinates
                        gps = _extract_gps(value)
                        if gps:
                            summary["gps"] = gps

            # Try to get XMP data for more metadata
            if hasattr(img, "info"):
                for key, value in img.info.items():
                    if key not in metadata and isinstance(value, (str, int, float)):
                        metadata[str(key)] = str(value)[:200]

    except ImportError:
        logger.warning("PIL/Pillow not installed, cannot extract image metadata")
    except Exception as e:
        logger.error(f"Error extracting image metadata: {e}")

    return {"raw": metadata, "summary": summary}


def _extract_gps(gps_info: dict) -> str | None:
    """Extract GPS coordinates from EXIF GPSInfo."""
    try:
        from PIL.ExifTags import GPSTAGS

        gps_data = {}
        for key, val in gps_info.items():
            tag = GPSTAGS.get(key, key)
            gps_data[tag] = val

        lat = gps_data.get("GPSLatitude")
        lat_ref = gps_data.get("GPSLatitudeRef")
        lon = gps_data.get("GPSLongitude")
        lon_ref = gps_data.get("GPSLongitudeRef")

        if lat and lon:
            lat_val = _convert_to_degrees(lat)
            lon_val = _convert_to_degrees(lon)

            if lat_ref == "S":
                lat_val = -lat_val
            if lon_ref == "W":
                lon_val = -lon_val

            return f"{lat_val:.6f},{lon_val:.6f}"
    except Exception as e:
        logger.debug(f"Error extracting GPS: {e}")
    return None


def _convert_to_degrees(value):
    """Convert GPS coordinates to degrees."""
    d = float(value[0].numerator) / float(value[0].denominator) if hasattr(value[0], "numerator") else float(value[0])
    m = float(value[1].numerator) / float(value[1].denominator) if hasattr(value[1], "numerator") else float(value[1])
    s = float(value[2].numerator) / float(value[2].denominator) if hasattr(value[2], "numerator") else float(value[2])
    return d + (m / 60.0) + (s / 3600.0)


def extract_video_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from a video file."""
    metadata = {}
    summary = {}

    # Try ffprobe first (most reliable)
    try:
        import subprocess
        import json

        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path,
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Extract format info
            fmt = data.get("format", {})
            if "duration" in fmt:
                duration_secs = float(fmt["duration"])
                hours = int(duration_secs // 3600)
                minutes = int((duration_secs % 3600) // 60)
                seconds = int(duration_secs % 60)
                if hours > 0:
                    summary["duration"] = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    summary["duration"] = f"{minutes}:{seconds:02d}"
                metadata["Duration"] = fmt["duration"]

            if "bit_rate" in fmt:
                bitrate = int(fmt["bit_rate"]) / 1000
                summary["bitrate"] = f"{bitrate:.0f} kbps"
                metadata["Bit Rate"] = fmt["bit_rate"]

            metadata["Format"] = fmt.get("format_name", "")
            metadata["Format Long Name"] = fmt.get("format_long_name", "")

            # Find video stream
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = stream.get("width")
                    height = stream.get("height")
                    if width and height:
                        summary["resolution"] = f"{width}x{height}"
                        metadata["Resolution"] = f"{width}x{height}"

                    summary["codec"] = stream.get("codec_name", "")
                    metadata["Video Codec"] = stream.get("codec_name", "")
                    metadata["Video Codec Long"] = stream.get("codec_long_name", "")

                    # Frame rate
                    fps = stream.get("r_frame_rate", "")
                    if fps and "/" in fps:
                        num, den = fps.split("/")
                        fps_val = float(num) / float(den)
                        summary["framerate"] = f"{fps_val:.2f} fps"
                    metadata["Frame Rate"] = fps

                    break

            # Find audio stream
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    metadata["Audio Codec"] = stream.get("codec_name", "")
                    metadata["Audio Channels"] = stream.get("channels", "")
                    metadata["Audio Sample Rate"] = stream.get("sample_rate", "")
                    break

    except FileNotFoundError:
        logger.warning("ffprobe not installed, cannot extract video metadata")
    except Exception as e:
        logger.error(f"Error extracting video metadata: {e}")

    return {"raw": metadata, "summary": summary}


def extract_audio_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from an audio file."""
    metadata = {}
    summary = {}

    # Try mutagen first for ID3 tags
    try:
        from mutagen import File as MutagenFile
        from mutagen.easyid3 import EasyID3

        audio = MutagenFile(file_path, easy=True)
        if audio:
            # Duration
            if hasattr(audio.info, "length"):
                duration_secs = audio.info.length
                minutes = int(duration_secs // 60)
                seconds = int(duration_secs % 60)
                summary["duration"] = f"{minutes}:{seconds:02d}"
                metadata["Duration"] = f"{duration_secs:.2f}s"

            # Bitrate
            if hasattr(audio.info, "bitrate"):
                summary["bitrate"] = f"{audio.info.bitrate // 1000} kbps"
                metadata["Bit Rate"] = str(audio.info.bitrate)

            # Sample rate
            if hasattr(audio.info, "sample_rate"):
                summary["sample_rate"] = f"{audio.info.sample_rate} Hz"
                metadata["Sample Rate"] = str(audio.info.sample_rate)

            # ID3 tags
            if hasattr(audio, "tags") and audio.tags:
                for key, value in audio.tags.items():
                    if isinstance(value, list):
                        value = value[0] if value else ""
                    metadata[key] = str(value)[:200]

                    # Build summary
                    if key.lower() == "title":
                        summary["title"] = str(value)
                    elif key.lower() == "artist":
                        summary["artist"] = str(value)
                    elif key.lower() == "album":
                        summary["album"] = str(value)

    except ImportError:
        # Fall back to ffprobe
        try:
            import subprocess
            import json

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    file_path,
                ],
                capture_output=True,
                timeout=30,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt = data.get("format", {})

                if "duration" in fmt:
                    duration_secs = float(fmt["duration"])
                    minutes = int(duration_secs // 60)
                    seconds = int(duration_secs % 60)
                    summary["duration"] = f"{minutes}:{seconds:02d}"

                if "bit_rate" in fmt:
                    summary["bitrate"] = f"{int(fmt['bit_rate']) // 1000} kbps"

                # Tags
                tags = fmt.get("tags", {})
                for key, value in tags.items():
                    metadata[key] = str(value)[:200]
                    if key.lower() == "title":
                        summary["title"] = value
                    elif key.lower() == "artist":
                        summary["artist"] = value
                    elif key.lower() == "album":
                        summary["album"] = value

        except Exception as e:
            logger.error(f"Error extracting audio metadata with ffprobe: {e}")

    except Exception as e:
        logger.error(f"Error extracting audio metadata: {e}")

    return {"raw": metadata, "summary": summary}


def extract_document_metadata(document) -> dict[str, Any]:
    """Extract metadata from a document based on its type.

    Returns:
        dict with "raw" (all metadata) and category-specific summary keys
    """
    if not document.file:
        return {}

    file_path = document.file.path
    if not os.path.exists(file_path):
        return {}

    category = document.category

    if category == "image":
        result = extract_image_metadata(file_path)
        return {
            "file_metadata": result.get("raw", {}),
            "image_metadata": result.get("summary", {}),
        }
    elif category == "video":
        result = extract_video_metadata(file_path)
        return {
            "file_metadata": result.get("raw", {}),
            "video_metadata": result.get("summary", {}),
        }
    elif category == "audio":
        result = extract_audio_metadata(file_path)
        return {
            "file_metadata": result.get("raw", {}),
            "audio_metadata": result.get("summary", {}),
        }
    else:
        # For other documents, try basic file info
        metadata = {
            "File Size": os.path.getsize(file_path),
            "Modified Time": os.path.getmtime(file_path),
        }
        return {"file_metadata": metadata}
