# ABOUTME: ImageHandler class for managing image uploads to Substack CDN
# ABOUTME: Handles uploading images from files, URLs, or raw bytes

import os
import re
from typing import Any, Dict, List, Optional, Union

import aiohttp


class ImageHandler:
    """Handles image upload operations for Substack"""

    MAX_IMAGE_BYTES = 25 * 1024 * 1024
    SUPPORTED_FORMATS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    SUPPORTED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }

    def __init__(self, client: Any) -> None:
        """Initialize the image handler with an authenticated client

        Args:
            client: An authenticated Substack API client
        """
        self.client = client

    async def upload_image(
        self, source: Union[str, bytes], filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload an image to Substack CDN

        Args:
            source: Either a file path, URL, or bytes data
            filename: Optional filename for bytes data

        Returns:
            Dict with 'url', 'id', and other metadata from Substack

        Raises:
            ValueError: If image format is not supported or invalid input
            FileNotFoundError: If local file doesn't exist
            Exception: If upload fails
        """
        # Input validation
        if source is None:
            raise ValueError("Source cannot be None")

        if filename is not None and not isinstance(filename, str):
            raise ValueError("Filename must be a string if provided")

        # Validate filename doesn't contain path separators (security)
        if filename and ("/" in filename or "\\" in filename):
            raise ValueError("Filename cannot contain path separators")
        if isinstance(source, str):
            if source.startswith(("http://", "https://")):
                await self._inspect_remote_image(source)
                result = self.client.get_image(source)
                filename = filename or os.path.basename(source) or "image.jpg"
            else:
                if not os.path.exists(source):
                    raise FileNotFoundError(f"Image file not found: {source}")

                if not self._validate_image_format(source):
                    raise ValueError(
                        f"Unsupported image format. Supported: {', '.join(self.SUPPORTED_FORMATS)}"
                    )
                self._inspect_local_image(source)

                result = self.client.get_image(source)
                filename = filename or os.path.basename(source)

        elif isinstance(source, bytes):
            import tempfile

            if not filename:
                filename = "image.jpg"

            # Ensure valid extension
            if not self._validate_image_format(filename):
                if "." not in filename:
                    filename += ".jpg"
            self._inspect_image_bytes(source)

            fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
            try:
                os.chmod(temp_path, 0o600)  # Secure permissions
                with os.fdopen(fd, "wb") as temp_file:
                    temp_file.write(source)
            except:
                os.close(fd)
                raise

            try:
                result = self.client.get_image(temp_path)
            finally:
                # Clean up temp file
                os.unlink(temp_path)
        else:
            raise ValueError("Source must be a file path, URL, or bytes")

        # Return the result from Substack's get_image
        return {
            "url": result.get("url"),
            "id": result.get("id"),
            "content_type": result.get("contentType"),
            "bytes": result.get("bytes"),
            "width": result.get("imageWidth"),
            "height": result.get("imageHeight"),
            "filename": filename,
        }

    def _inspect_local_image(self, path: str) -> str:
        """Validate local image size and sniffed MIME type."""
        file_size = os.path.getsize(path)
        if file_size > self.MAX_IMAGE_BYTES:
            raise ValueError("Image files larger than 25 MB are not supported")

        with open(path, "rb") as image_file:
            header = image_file.read(64)
        return self._validate_sniffed_mime(header)

    def _inspect_image_bytes(self, data: bytes) -> str:
        """Validate in-memory image size and sniffed MIME type."""
        if len(data) > self.MAX_IMAGE_BYTES:
            raise ValueError("Image files larger than 25 MB are not supported")
        return self._validate_sniffed_mime(data[:64])

    async def _inspect_remote_image(self, url: str) -> tuple[str, Optional[int]]:
        """Validate remote image metadata before asking Substack to fetch it."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch image from {url}: HTTP {response.status}"
                    )
                content_type = (response.headers.get("Content-Type") or "").split(";")[
                    0
                ]
                content_length = response.headers.get("Content-Length")
                size = (
                    int(content_length)
                    if content_length and content_length.isdigit()
                    else None
                )
                if size is not None and size > self.MAX_IMAGE_BYTES:
                    raise ValueError("Image files larger than 25 MB are not supported")
                if content_type and content_type not in self.SUPPORTED_MIME_TYPES:
                    raise ValueError(f"Unsupported image content type: {content_type}")
                if not content_type:
                    header = await response.content.read(64)
                    content_type = self._validate_sniffed_mime(header)
                return content_type, size

    async def _fetch_from_url(self, url: str) -> bytes:
        """Fetch image data from URL

        Args:
            url: The image URL

        Returns:
            Image data as bytes

        Raises:
            Exception: If fetch fails
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Failed to fetch image from {url}: HTTP {response.status}"
                    )
                return await response.read()

    def _validate_image_format(self, filename: str) -> bool:
        """Validate if the image format is supported

        Args:
            filename: The filename to check

        Returns:
            True if format is supported, False otherwise
        """
        if not filename or "." not in filename:
            return False

        ext = os.path.splitext(filename)[1].lower()
        return ext in self.SUPPORTED_FORMATS

    def _validate_sniffed_mime(self, header: bytes) -> str:
        """Validate a file's MIME type from its magic bytes."""
        mime_type = self._sniff_image_mime(header)
        if mime_type not in self.SUPPORTED_MIME_TYPES:
            raise ValueError("Unsupported image content")
        return mime_type

    def _sniff_image_mime(self, header: bytes) -> Optional[str]:
        """Detect common image formats from file headers."""
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if header.startswith(b"RIFF") and b"WEBP" in header[:16]:
            return "image/webp"
        return None

    def get_optimized_url(
        self,
        url: str,
        width: Optional[int] = None,
        quality: str = "auto:good",
        format: str = "auto",
    ) -> str:
        """Get an optimized version of a Substack CDN image URL

        Args:
            url: The original Substack CDN URL
            width: Optional width constraint
            quality: Quality setting (auto:good, auto:low, etc.)
            format: Image format (auto, webp, etc.)

        Returns:
            Optimized URL

        Raises:
            ValueError: If invalid input provided
        """
        # Input validation
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        if width is not None:
            if not isinstance(width, int) or width <= 0:
                raise ValueError("Width must be a positive integer if provided")

        valid_qualities = [
            "auto:good",
            "auto:low",
            "auto:best",
            "100",
            "90",
            "80",
            "70",
            "60",
        ]
        if quality not in valid_qualities:
            raise ValueError(f"Quality must be one of: {', '.join(valid_qualities)}")

        valid_formats = ["auto", "webp", "jpg", "png"]
        if format not in valid_formats:
            raise ValueError(f"Format must be one of: {', '.join(valid_formats)}")
        # Parse existing URL parameters
        if "substackcdn.com" not in url:
            return url

        # Build new parameters
        params = []

        if width:
            params.append(f"w_{width}")

        params.append("c_limit")
        params.append(f"f_{format}")
        params.append(f"q_{quality}")
        params.append("fl_progressive:steep")

        # Reconstruct URL
        base_url = "https://substackcdn.com/image/fetch/"
        param_string = ",".join(params)

        # Extract the original image URL
        match = re.search(r"https://[^/]+/image/fetch/[^/]+/(https://.+)", url)
        if match:
            original_url = match.group(1)
            return f"{base_url}{param_string}/{original_url}"

        return url

    async def batch_upload(
        self, sources: List[Union[str, bytes]], filenames: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Upload multiple images

        Args:
            sources: List of file paths, URLs, or bytes
            filenames: Optional list of filenames for bytes sources

        Returns:
            List of upload results with 'success' flag
        """
        results = []
        resolved_filenames: List[Optional[str]] = list(filenames or []) or [None] * len(
            sources
        )

        for source, filename in zip(sources, resolved_filenames):
            try:
                result = await self.upload_image(source, filename)
                results.append(
                    {
                        "success": True,
                        "url": result["url"],
                        "id": result["id"],
                        "filename": result.get("filename"),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "success": False,
                        "error": str(e),
                        "source": (
                            source if isinstance(source, str) else f"bytes:{filename}"
                        ),
                    }
                )

        return results
