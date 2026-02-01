"""Whisper server client for audio transcription.

Sends audio data to whisper-server and returns transcription text.
"""

import httpx


class TranscriptionError(Exception):
    """Raised when transcription fails."""


async def transcribe(
    audio_data: bytes,
    whisper_url: str,
    timeout: float = 60.0,
) -> str:
    """Transcribe audio data using whisper-server.

    Args:
        audio_data: Raw audio bytes (e.g., .oga format from Telegram).
        whisper_url: URL of the whisper-server /transcribe endpoint.
        timeout: Request timeout in seconds.

    Returns:
        Transcribed text from the audio.

    Raises:
        TranscriptionError: If the request fails or transcription is empty.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                whisper_url,
                files={"audio": ("audio.oga", audio_data, "audio/ogg")},
            )
            response.raise_for_status()

            data = response.json()
            text = data.get("text", "").strip()

            if not text:
                raise TranscriptionError("Empty transcription received")

            return text

    except httpx.TimeoutException as e:
        raise TranscriptionError(f"Transcription request timed out: {e}") from e
    except httpx.HTTPStatusError as e:
        raise TranscriptionError(
            f"Transcription request failed with status {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise TranscriptionError(f"Transcription request error: {e}") from e
    except (KeyError, ValueError) as e:
        raise TranscriptionError(f"Invalid transcription response: {e}") from e
