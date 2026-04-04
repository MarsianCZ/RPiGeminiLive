# RPiGeminiLive
Python scripts to run Gemini Live on Raspberry Pi with the AIY Voice Kit.
It should work with almost any ALSA-compatible microphone/speaker setup, not only the AIY kit.

## Repository Contents
- `push-to-talk.py` - wrapper with GPIO button/LED functions and app entrypoint.
- `gemini-on-voicehat.py` - Gemini Live session/audio streaming logic used by `push-to-talk.py`.
- `app_config.py` - loads and validates app settings from `config.json`.
- `config.json` - main configuration file (API key, GPIO, audio, Gemini, debug).

## Requirements
- Raspberry Pi (tested with AIY Voice HAT).
- Physical button and LED connected to GPIO required for push to talk (defaults in `config.json`: button `GPIO 23`, LED `GPIO 25`).
- Python 3.10+.
- ALSA utilities: `arecord`, `aplay`.
- Python packages:
  - `google-genai`
  - `gpiozero`

## Quick Start (`push-to-talk.py`)
1. Open `config.json` and set:
   - `api.api_key` (replace `PUT_YOUR_GEMINI_API_KEY_HERE`)
2. (Optional) adjust devices/settings in `config.json`:
   - `audio.alsa_in_dev`
   - `audio.alsa_out_dev`
   - Tip: list ALSA devices with `arecord -l` and `aplay -l`
3. Run the script:
   - `python3 push-to-talk.py`

After startup, hold the button to record; when released, the model response is played through the speaker.

## Configuration
All settings are centralized in `config.json` and loaded by `app_config.py`.

- Edit sections: `api`, `gpio`, `audio`, `gemini`, `debug`.
- Keep `config.json` private if it contains a real API key.
