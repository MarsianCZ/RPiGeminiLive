#!/usr/bin/env python3
"""Central configuration loader for push-to-talk Gemini app."""

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).with_name("config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "api": {
        "api_key": "",
    },
    "gpio": {
        "button_gpio": 23,
        "led_gpio": 25,
        "button_bounce_sec": 0.03,
    },
    "audio": {
        "send_rate": 16000,
        "recv_rate": 24000,
        "chunk": 2048,
        "alsa_in_dev": "default",
        "alsa_out_dev": "default",
    },
    "gemini": {
        "model": "gemini-2.5-flash-native-audio-preview-12-2025",
        "system_instruction": "Respond briefly and concisely.",
        "voice_name": "Kore",
    },
    "debug": {
        "print_transcript": True,
        "print_audio_stats": True,
    },
    "wake_word": {
        "keyword": "gemini",
        "vosk_model_path": "vosk-model-small-en-us-0.15",
        "listen_rate": 16000,
        "listen_chunk": 4000,
        "silence_timeout_seconds": 1.0,
        "speech_rms_threshold": 450,
        "max_record_seconds": 12.0,
        "wait_pulse_seconds": 1.2,
    },
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_file_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"Missing configuration file: {CONFIG_PATH}. "
            "Create config.json next to app_config.py."
        )
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {CONFIG_PATH}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Top-level JSON object expected in {CONFIG_PATH}.")
    return _merge_dict(DEFAULT_CONFIG, loaded)


_CFG = _load_file_config()

# --- API ---
API_KEY = str(_CFG["api"]["api_key"]).strip()

# --- GPIO (AIY Voice HAT v1) ---
BTN_GPIO = int(_CFG["gpio"]["button_gpio"])
LED_GPIO = int(_CFG["gpio"]["led_gpio"])
BTN_BOUNCE_SEC = float(_CFG["gpio"]["button_bounce_sec"])

# --- Audio ---
SEND_RATE = int(_CFG["audio"]["send_rate"])
RECV_RATE = int(_CFG["audio"]["recv_rate"])
CHUNK = int(_CFG["audio"]["chunk"])
ALSA_IN_DEV = str(_CFG["audio"]["alsa_in_dev"])
ALSA_OUT_DEV = str(_CFG["audio"]["alsa_out_dev"])

ARECORD_CMD = [
    "arecord",
    "-D",
    ALSA_IN_DEV,
    "-q",
    "-f",
    "S16_LE",
    "-c",
    "1",
    "-r",
    str(SEND_RATE),
    "-t",
    "raw",
]

APLAY_CMD = [
    "aplay",
    "-D",
    ALSA_OUT_DEV,
    "-q",
    "-f",
    "S16_LE",
    "-c",
    "1",
    "-r",
    str(RECV_RATE),
    "-t",
    "raw",
]

AUDIO_MIME = f"audio/pcm;rate={SEND_RATE}"

# --- Gemini Live ---
MODEL = str(_CFG["gemini"]["model"])
INSTRUCTIONS = str(_CFG["gemini"]["system_instruction"])
VOICE_NAME = str(_CFG["gemini"]["voice_name"]).strip()

# --- Debug / console ---
PRINT_TRANSCRIPT = bool(_CFG["debug"]["print_transcript"])
PRINT_AUDIO_STATS = bool(_CFG["debug"]["print_audio_stats"])

# --- Wake-word mode ---
WAKE_KEYWORD = str(_CFG["wake_word"]["keyword"]).strip().lower()
WAKE_VOSK_MODEL_PATH = str(_CFG["wake_word"]["vosk_model_path"]).strip()
WAKE_LISTEN_RATE = int(_CFG["wake_word"]["listen_rate"])
WAKE_LISTEN_CHUNK = int(_CFG["wake_word"]["listen_chunk"])
WAKE_SILENCE_TIMEOUT_SECONDS = float(_CFG["wake_word"]["silence_timeout_seconds"])
WAKE_SPEECH_RMS_THRESHOLD = int(_CFG["wake_word"]["speech_rms_threshold"])
WAKE_MAX_RECORD_SECONDS = float(_CFG["wake_word"]["max_record_seconds"])
WAKE_WAIT_PULSE_SECONDS = float(_CFG["wake_word"]["wait_pulse_seconds"])

GEMINI_CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": INSTRUCTIONS,
    "realtime_input_config": {"automatic_activity_detection": {"disabled": True}},
    "output_audio_transcription": {},
}

if VOICE_NAME:
    GEMINI_CONFIG["speech_config"] = {
        "voice_config": {"prebuilt_voice_config": {"voice_name": VOICE_NAME}}
    }
