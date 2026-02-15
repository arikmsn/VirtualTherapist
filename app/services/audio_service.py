"""Audio service - handles audio transcription for session recordings"""

from typing import Optional
import os
from app.core.config import settings
from loguru import logger


class AudioService:
    """Service for processing audio recordings"""

    def __init__(self):
        self.max_file_size = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024  # Convert to bytes
        self.supported_formats = settings.SUPPORTED_AUDIO_FORMATS.split(',')

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file to text using Whisper or similar

        Args:
            audio_file_path: Path to the audio file

        Returns:
            Transcribed text
        """

        # Validate file
        if not os.path.exists(audio_file_path):
            raise ValueError(f"Audio file not found: {audio_file_path}")

        file_size = os.path.getsize(audio_file_path)
        if file_size > self.max_file_size:
            raise ValueError(f"Audio file too large: {file_size} bytes (max: {self.max_file_size})")

        # Check format
        file_ext = os.path.splitext(audio_file_path)[1][1:].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported audio format: {file_ext}")

        try:
            # Use OpenAI Whisper for transcription
            if settings.AI_PROVIDER == "openai":
                transcript = await self._transcribe_with_openai(audio_file_path)
            else:
                # Use Anthropic or local Whisper model
                transcript = await self._transcribe_with_whisper(audio_file_path)

            logger.info(f"Successfully transcribed audio file: {audio_file_path}")
            return transcript

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise

    async def _transcribe_with_openai(self, audio_file_path: str) -> str:
        """Transcribe using OpenAI Whisper API"""
        import openai

        with open(audio_file_path, "rb") as audio_file:
            transcript = await openai.Audio.atranscribe("whisper-1", audio_file)

        return transcript["text"]

    async def _transcribe_with_whisper(self, audio_file_path: str) -> str:
        """Transcribe using local Whisper model"""
        import whisper

        model = whisper.load_model("base")  # Use 'base' model for speed, 'large' for accuracy
        result = model.transcribe(audio_file_path, language="he")  # Hebrew by default

        return result["text"]

    def validate_audio_file(self, file_path: str) -> bool:
        """Validate audio file format and size"""

        if not os.path.exists(file_path):
            return False

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            return False

        file_ext = os.path.splitext(file_path)[1][1:].lower()
        if file_ext not in self.supported_formats:
            return False

        return True
