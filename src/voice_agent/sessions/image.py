"""Image attachment types for multimodal prompts."""

from dataclasses import dataclass


@dataclass
class ImageAttachment:
    """An image attachment for sending to Claude.

    Attributes:
        data: Base64-encoded image data.
        media_type: MIME type of the image (e.g. "image/jpeg").
    """

    data: str
    media_type: str
