"""Unit tests for transcription client."""

import pytest
from pytest_httpx import HTTPXMock

from voice_agent.transcribe import TranscriptionError, transcribe


@pytest.mark.unit
class TestTranscribe:
    """Tests for transcribe function."""

    async def test_successful_transcription(self, httpx_mock: HTTPXMock) -> None:
        """Test successful transcription."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "hello world"},
        )

        result = await transcribe(
            b"audio data",
            "http://localhost:8080/transcribe",
        )

        assert result == "hello world"

    async def test_empty_transcription_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test empty transcription raises error."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": ""},
        )

        with pytest.raises(TranscriptionError, match="Empty transcription"):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_whitespace_transcription_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test whitespace-only transcription raises error."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "   "},
        )

        with pytest.raises(TranscriptionError, match="Empty transcription"):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_http_error_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test HTTP error raises TranscriptionError."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            status_code=500,
        )

        with pytest.raises(TranscriptionError, match="status 500"):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_timeout_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test timeout raises TranscriptionError."""
        import httpx

        httpx_mock.add_exception(httpx.TimeoutException("timeout"))

        with pytest.raises(TranscriptionError, match="timed out"):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_connection_error_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test connection error raises TranscriptionError."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("connection refused"))

        with pytest.raises(TranscriptionError, match="request error"):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_invalid_json_raises(self, httpx_mock: HTTPXMock) -> None:
        """Test invalid JSON response raises error."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            text="not json",
        )

        with pytest.raises(TranscriptionError):
            await transcribe(
                b"audio data",
                "http://localhost:8080/transcribe",
            )

    async def test_strips_whitespace(self, httpx_mock: HTTPXMock) -> None:
        """Test whitespace is stripped from transcription."""
        httpx_mock.add_response(
            url="http://localhost:8080/transcribe",
            json={"text": "  hello world  \n"},
        )

        result = await transcribe(
            b"audio data",
            "http://localhost:8080/transcribe",
        )

        assert result == "hello world"
