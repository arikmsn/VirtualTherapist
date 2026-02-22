"""Audio service - handles audio transcription for session recordings.

Service boundary: accepts raw audio bytes or file path, returns transcript text.
Language is explicit (never hardcoded) to support Hebrew, English, and future locales.
"""

import os
import tempfile
from typing import Optional
from app.core.config import settings
from loguru import logger


class AudioService:
    """Service for processing audio recordings via ASR (Whisper)."""

    def __init__(self):
        self.max_file_size = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
        self.supported_formats = [
            fmt.strip() for fmt in settings.SUPPORTED_AUDIO_FORMATS.split(",")
        ]

    async def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_file_path: Path to an audio file on disk.
            language: ISO-639-1 language code (e.g. "he", "en").
                      Defaults to settings.DEFAULT_LANGUAGE.

        Returns:
            Transcribed text.
        """
        language = language or settings.DEFAULT_LANGUAGE
        self._validate_file(audio_file_path)

        try:
            transcript = await self._transcribe_with_openai(audio_file_path, language)
            logger.info(f"Transcribed audio ({language}): {audio_file_path}")
            return transcript
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

    async def transcribe_upload(
        self,
        file_bytes: bytes,
        filename: str,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio from uploaded bytes (e.g. from a multipart form).

        Writes to a temp file, transcribes, then cleans up.

        Args:
            file_bytes: Raw audio bytes.
            filename: Original filename (used to infer format).
            language: ISO-639-1 language code.

        Returns:
            Transcribed text.
        """
        language = language or settings.DEFAULT_LANGUAGE

        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = ".webm"  # browser MediaRecorder default

        if len(file_bytes) > self.max_file_size:
            raise ValueError(
                f"Audio file too large: {len(file_bytes)} bytes "
                f"(max: {self.max_file_size})"
            )

        # Write to temp file so the OpenAI SDK can read it
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            tmp.write(file_bytes)
            tmp.flush()
            tmp.close()
            return await self.transcribe_audio(tmp.name, language=language)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _transcribe_with_openai(
        self, audio_file_path: str, language: str
    ) -> str:
        """Transcribe using OpenAI Whisper API (v1+ SDK)."""
        from openai import AsyncOpenAI
        from app.core.config import is_placeholder_key

        if is_placeholder_key(settings.OPENAI_API_KEY):
            raise RuntimeError(
                "OpenAI API key is missing or a placeholder. "
                "Set a valid OPENAI_API_KEY in .env to use audio transcription."
            )

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        with open(audio_file_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
            )

        return transcript.text

    def _validate_file(self, file_path: str) -> None:
        """Validate that an audio file exists, is within size limits, and has a supported format."""
        if not os.path.exists(file_path):
            raise ValueError(f"Audio file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(
                f"Audio file too large: {file_size} bytes (max: {self.max_file_size})"
            )

        file_ext = os.path.splitext(file_path)[1][1:].lower()
        # Allow webm (browser default) in addition to configured formats
        allowed = self.supported_formats + ["webm"]
        if file_ext not in allowed:
            raise ValueError(f"Unsupported audio format: {file_ext}")
