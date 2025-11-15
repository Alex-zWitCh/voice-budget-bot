"""
Voice transcription using Vosk for Speech-to-Text.
Supports Uzbek, Russian, and English.
"""

import os
import json
import subprocess
import logging
import threading
from vosk import Model, KaldiRecognizer
from config import Config

logger = logging.getLogger(__name__)


class VoiceTranscriber:
    """
    Voice transcription handler using Vosk.
    
    Uses shared model cache to ensure each Vosk model is loaded only once
    across all instances, reducing memory usage and initialization time.
    """
    
    # Class-level shared model cache
    _shared_models = {}
    _model_lock = threading.Lock()
    _models_loaded = False
    
    def __init__(self):
        """Initialize VoiceTranscriber instance with shared models."""
        logger.debug("Creating new VoiceTranscriber instance")
        self._ensure_models_loaded()
    
    @classmethod
    def _ensure_models_loaded(cls):
        """Ensure all Vosk models are loaded (thread-safe, loads only once)."""
        if cls._models_loaded:
            logger.debug(f"Models already loaded, using cached models. Available languages: {list(cls._shared_models.keys())}")
            return
        
        with cls._model_lock:
            # Double-check after acquiring lock (thread-safe pattern)
            if cls._models_loaded:
                logger.debug(f"Models were loaded by another thread. Available languages: {list(cls._shared_models.keys())}")
                return
            
            logger.info("Loading Vosk models (first time initialization)...")
            language_paths = {
                "uz": Config.VOSK_MODEL_PATH_UZ,
                "ru": Config.VOSK_MODEL_PATH_RU,
                "en": Config.VOSK_MODEL_PATH_EN,
            }
            
            loaded_count = 0
            for lang, model_path in language_paths.items():
                if model_path and os.path.exists(model_path):
                    try:
                        logger.info(f"Loading Vosk model for '{lang}' from {model_path}")
                        cls._shared_models[lang] = Model(model_path)
                        loaded_count += 1
                        logger.info(f"Successfully loaded Vosk model for '{lang}'")
                    except Exception as e:
                        logger.error(f"Error loading model for '{lang}' from {model_path}: {e}", exc_info=True)
                else:
                    logger.warning(f"Model not found for '{lang}' at {model_path} (path exists: {os.path.exists(model_path) if model_path else False})")
            
            cls._models_loaded = True
            logger.info(f"Model loading complete. Loaded {loaded_count}/{len(language_paths)} models. Available languages: {list(cls._shared_models.keys())}")
    
    @property
    def models(self):
        """Get shared models dictionary (read-only access)."""
        return VoiceTranscriber._shared_models
    
    def transcribe(self, audio_file_path: str, language: str = "en") -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_file_path: Path to audio file
            language: Language code (uz, ru, en)
        
        Returns:
            Transcribed text
        """
        logger.debug(f"Starting transcription for file: {audio_file_path}, requested language: {language}")
        
        # Ensure models are loaded
        self._ensure_models_loaded()
        
        original_language = language
        if language not in self.models:
            # Fallback to English if model not available
            language = "en" if "en" in self.models else list(self.models.keys())[0] if self.models else None
            if language and language != original_language:
                logger.info(f"Language '{original_language}' not available, falling back to '{language}'")
        
        if not language or language not in self.models:
            logger.warning(f"No Vosk model available for transcription. Requested: {original_language}, Available: {list(self.models.keys())}")
            return "Voice transcription not available. Please send text message."
        
        logger.debug(f"Using Vosk model for language: {language} (from shared model cache)")
        
        try:
            # Convert audio to WAV format using ffmpeg directly
            wav_path = audio_file_path.replace(".ogg", ".wav").replace(".mp3", ".wav")
            logger.debug(f"Converting audio to WAV format: {audio_file_path} -> {wav_path}")
            
            # Use ffmpeg to convert to 16kHz mono 16-bit WAV (required by Vosk)
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", audio_file_path,
                "-ar", "16000",  # Sample rate: 16kHz
                "-ac", "1",      # Channels: mono
                "-sample_fmt", "s16",  # Sample format: 16-bit signed
                "-y",            # Overwrite output file
                wav_path
            ]
            
            # Run ffmpeg conversion
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            logger.debug(f"Audio conversion completed successfully")
            
            # Transcribe using Vosk
            model = self.models[language]
            rec = KaldiRecognizer(model, 16000)
            rec.SetWords(True)
            
            logger.debug(f"Starting Vosk transcription process")
            text_parts = []
            
            with open(wav_path, "rb") as wav_file:
                chunk_count = 0
                while True:
                    data = wav_file.read(4000)
                    if len(data) == 0:
                        break
                    chunk_count += 1
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if "text" in result:
                            text_parts.append(result["text"])
            
            # Get final result
            final_result = json.loads(rec.FinalResult())
            if "text" in final_result:
                text_parts.append(final_result["text"])
            
            transcribed_text = " ".join(text_parts).strip()
            logger.info(f"Transcription completed for {audio_file_path} (language: {language}). Length: {len(transcribed_text)} characters, Chunks processed: {chunk_count}")
            
            # Clean up temporary file
            if os.path.exists(wav_path) and wav_path != audio_file_path:
                os.remove(wav_path)
                logger.debug(f"Cleaned up temporary WAV file: {wav_path}")
            
            return transcribed_text
        
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed for {audio_file_path}: {e.stderr.decode() if e.stderr else str(e)}", exc_info=True)
            return "Could not transcribe audio. Please try again or send text message."
        except Exception as e:
            logger.error(f"Error transcribing audio file {audio_file_path} (language: {language}): {e}", exc_info=True)
            return "Could not transcribe audio. Please try again or send text message."

