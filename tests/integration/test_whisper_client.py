"""Integration tests for whisper client."""

import pytest
from pytest_httpx import HTTPXMock

from voice_agent.transcribe import TranscriptionError, transcribe


@pytest.mark.integration
class TestWhisperClient:
    """Integration tests for whisper-server client."""

    async def test_transcribe_real_audio_format(
        self, httpx_mock: HTTPXMock, sample_audio_bytes: bytes
    ) -> None:
        """Test transcription with realistic audio data."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "test transcription"},
        )

        result = await transcribe(
            sample_audio_bytes,
            "http://localhost:8080/transcribe",
        )

        assert result == "test transcription"

        # Verify request was made correctly
        request = httpx_mock.get_request()
        assert request is not None
        assert "multipart/form-data" in request.headers["content-type"]

    async def test_transcribe_handles_unicode(self, httpx_mock: HTTPXMock) -> None:
        """Test transcription with unicode characters."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "hello \u4e16\u754c"},
        )

        result = await transcribe(
            b"audio",
            "http://localhost:8080/transcribe",
        )

        assert "\u4e16\u754c" in result

    async def test_transcribe_custom_timeout(self, httpx_mock: HTTPXMock) -> None:
        """Test transcription with custom timeout."""
        httpx_mock.add_response(
            url="http://custom:9000/transcribe",
            json={"text": "result"},
        )

        result = await transcribe(
            b"audio",
            "http://custom:9000/transcribe",
            timeout=5.0,
        )

        assert result == "result"

    async def test_transcribe_server_error_details(self, httpx_mock: HTTPXMock) -> None:
        """Test error handling preserves status code."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            status_code=503,
        )

        with pytest.raises(TranscriptionError) as exc_info:
            await transcribe(
                b"audio",
                "http://localhost:8080/transcribe",
            )

        assert "503" in str(exc_info.value)

    async def test_transcribe_malformed_response(self, httpx_mock: HTTPXMock) -> None:
        """Test handling of malformed JSON response."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"unexpected": "format"},
        )

        with pytest.raises(TranscriptionError, match="Empty transcription"):
            await transcribe(
                b"audio",
                "http://localhost:8080/transcribe",
            )
