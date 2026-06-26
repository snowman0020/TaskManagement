"""Image attachment validation — type sniffing and limits.

Kept storage-free so the rules can be unit-tested without MongoDB/GridFS.
"""

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image
MAX_IMAGES_PER_TASK = 10


def sniff_image_type(data: bytes) -> str | None:
    """Detect an image type from its magic bytes, or None if unrecognized.

    Used to reject files whose declared content-type is spoofed.
    """
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image(filename: str, declared_type: str | None, data: bytes) -> str:
    """Validate one image's size and type. Returns the resolved content-type.

    Raises ValueError with a human-readable message on the first failure.
    """
    if len(data) == 0:
        raise ValueError(f"'{filename}' is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"'{filename}' is {len(data) // 1024} KB; the limit is "
            f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB"
        )
    sniffed = sniff_image_type(data)
    if sniffed is None or sniffed not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"'{filename}' is not a supported image (PNG, JPEG, WebP, or GIF)"
        )
    # Prefer the sniffed type — it cannot be spoofed by a wrong header.
    return sniffed
