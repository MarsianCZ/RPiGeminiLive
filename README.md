# RPiGeminiLive
Python scripts to run Gemini Live on Raspberry Pi with the AIY Voice Kit.
It should work with almost any ALSA-compatible microphone/speaker setup, not only the AIY kit.

## Repository Contents
- `push-to-talk.py` - wrapper with GPIO button/LED functions and app entrypoint.
- `wake-word.py` - wake-word entrypoint (keyword starts voice-activity-based recording turn).
- `button-wake-word.py` - button-gated wake-word mode with short follow-up conversation loop.
- `gemini-on-voicehat.py` - shared Gemini Live session/audio streaming logic used by all modes.
- `app_config.py` - loads and validates app settings from `config.json`.
- `config.json` - main configuration file (API key, GPIO, LED behavior, audio, Gemini, debug).

## Requirements
- Raspberry Pi (tested with AIY Voice HAT).
- Physical button and LED connected to GPIO required for push to talk (defaults in `config.json`: button `GPIO 23`, LED `GPIO 25`).
- Python 3.10+.
- ALSA utilities: `arecord`, `aplay`.
- Python packages:
  - `google-genai`
  - `gpiozero`
  - `vosk` (for `wake-word.py` and `button-wake-word.py`)

Install Python dependencies:
- `pip install google-genai gpiozero vosk`

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

## Wake-Word Mode (`wake-word.py`)
1. Install wake-word dependency:
   - `pip install vosk`
2. Download a Vosk model from official model list:
   - [Vosk Models (official)](https://alphacephei.com/vosk/models)
   - Recommended on Raspberry Pi: `vosk-model-small-en-us-0.15`
   - Example:
     - `wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip`
     - `unzip vosk-model-small-en-us-0.15.zip`
3. Set `wake_word.vosk_model_path` in `config.json` to the extracted model directory (not the `.zip` file), for example:
   - `vosk-model-small-en-us-0.15`
4. Set `wake_word.keyword` in `config.json`.
5. (Optional) tune VAD:
   - `wake_word.silence_timeout_seconds`
   - `wake_word.speech_rms_threshold`
   - `wake_word.max_record_seconds`
6. Run:
   - `python3 wake-word.py`

Behavior:
- App waits for keyword using microphone input.
- LED pulses very slowly while waiting for keyword.
- After keyword detection, it records while voice is present and ends after silence (`wake_word.silence_timeout_seconds`).
- `wake_word.max_record_seconds` is a safety cap to prevent endless recording.

## Button + Wake-Word Mode (`button-wake-word.py`)
Run:
- `python3 button-wake-word.py`

Behavior:
- App waits for button press.
- After button press, app waits for wake keyword.
- After keyword detection, app records your prompt and plays model response.
- Then app automatically opens a short follow-up listening window and continues the conversation turn-by-turn.
- If no follow-up speech is detected in that window, it exits conversation flow and waits for button press again.

Tune follow-up window:
- `button_wake_word.followup_listen_seconds` (default `4.0`)

## Configuration
All settings are centralized in `config.json` and loaded by `app_config.py`.

- Edit sections: `api`, `gpio`, `led`, `audio`, `gemini`, `debug`.
- Wake mode settings are in section: `wake_word`.
- Button + wake mode settings are in section: `button_wake_word`.
- Keep `config.json` private if it contains a real API key.
