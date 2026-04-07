#!/usr/bin/env python3
"""Wake-word entrypoint: listens for keyword, then records a timed message turn."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

from gpiozero import PWMLED

import app_config as cfg

try:
    from vosk import KaldiRecognizer, Model
except ImportError:
    KaldiRecognizer = None
    Model = None


def _load_run_gemini_session():
    module_path = Path(__file__).with_name("gemini-on-voicehat.py")
    spec = importlib.util.spec_from_file_location("gemini_on_voicehat", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Gemini module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_gemini_session


run_gemini_session = _load_run_gemini_session()


class LedMode:
    IDLE = "idle"
    RECORDING = "recording"
    SPEAKING = "speaking"
    ERROR = "error"


class LedController:
    """LED behavior for wake mode.

    - waiting_for_wake=True + IDLE: very slow pulse
    - RECORDING: solid on
    - SPEAKING: medium pulse
    """

    def __init__(self, pin: int):
        self.led = PWMLED(pin)
        self.waiting_for_wake = False
        self.current_mode = LedMode.IDLE
        self._apply()

    def set_waiting_for_wake(self, enabled: bool) -> None:
        self.waiting_for_wake = enabled
        self._apply()

    def set(self, mode: str) -> None:
        self.current_mode = mode
        self._apply()

    def _apply(self) -> None:
        self.led.off()
        if self.current_mode == LedMode.RECORDING:
            self.led.value = 1
        elif self.current_mode == LedMode.SPEAKING:
            self.led.pulse(
                fade_in_time=cfg.LED_SPEAKING_FADE_IN_SECONDS,
                fade_out_time=cfg.LED_SPEAKING_FADE_OUT_SECONDS,
                background=True,
            )
        elif self.current_mode == LedMode.ERROR:
            self.led.blink(
                on_time=cfg.LED_ERROR_BLINK_ON_SECONDS,
                off_time=cfg.LED_ERROR_BLINK_OFF_SECONDS,
                n=cfg.LED_ERROR_BLINK_COUNT,
                background=True,
            )
        elif self.waiting_for_wake:
            self.led.pulse(
                fade_in_time=cfg.LED_WAKE_WAIT_PULSE_SECONDS,
                fade_out_time=cfg.LED_WAKE_WAIT_PULSE_SECONDS,
                background=True,
            )
        else:
            self.led.value = 0


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword in text.strip().lower()


async def _wait_for_wake_keyword(vosk_model: Model, keyword: str) -> None:
    rec = await asyncio.create_subprocess_exec(
        "arecord",
        "-D",
        cfg.ALSA_IN_DEV,
        "-q",
        "-f",
        "S16_LE",
        "-c",
        "1",
        "-r",
        str(cfg.WAKE_LISTEN_RATE),
        "-t",
        "raw",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    recognizer = KaldiRecognizer(vosk_model, cfg.WAKE_LISTEN_RATE)

    try:
        while True:
            chunk = await rec.stdout.read(cfg.WAKE_LISTEN_CHUNK)
            if not chunk:
                if rec.returncode is not None:
                    err = b""
                    if rec.stderr:
                        err = await rec.stderr.read()
                    err_text = err.decode("utf-8", errors="replace").strip()
                    raise RuntimeError(
                        f"Wake listener failed on '{cfg.ALSA_IN_DEV}': "
                        f"{err_text or 'Unknown ALSA error.'}"
                    )
                continue

            if recognizer.AcceptWaveform(chunk):
                final_json = json.loads(recognizer.Result())
                if _contains_keyword(final_json.get("text", ""), keyword):
                    return
            else:
                partial_json = json.loads(recognizer.PartialResult())
                if _contains_keyword(partial_json.get("partial", ""), keyword):
                    return
    finally:
        try:
            rec.terminate()
        except Exception:
            pass
        try:
            await asyncio.wait_for(rec.wait(), timeout=0.3)
        except Exception:
            pass


async def _wake_loop(
    pressed_evt: asyncio.Event,
    released_evt: asyncio.Event,
    led: LedController,
    vosk_model: Model,
) -> None:
    if not cfg.WAKE_KEYWORD:
        raise RuntimeError("wake_word.keyword is empty in config.json")

    while True:
        led.set_waiting_for_wake(True)
        print(f"Waiting for wake keyword: '{cfg.WAKE_KEYWORD}'")
        await _wait_for_wake_keyword(vosk_model, cfg.WAKE_KEYWORD)

        led.set_waiting_for_wake(False)
        print("Wake keyword detected. Listening for message...")

        released_evt.clear()
        pressed_evt.set()
        await released_evt.wait()

        # Give Gemini loop a brief moment to finish turn transition.
        await asyncio.sleep(0.35)


async def main():
    print("Starting initialization (wake-word mode)...")

    if Model is None or KaldiRecognizer is None:
        print(
            "Missing dependency: install vosk (pip install vosk).",
            file=sys.stderr,
        )
        sys.exit(2)

    model_path = Path(cfg.WAKE_VOSK_MODEL_PATH)
    if not model_path.exists():
        print(
            "Missing Vosk model path in config.json wake_word.vosk_model_path: "
            f"{model_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    vosk_model = Model(str(model_path))

    led = LedController(cfg.LED_GPIO)
    pressed_evt = asyncio.Event()
    released_evt = asyncio.Event()

    gemini_task = asyncio.create_task(
        run_gemini_session(
            pressed_evt=pressed_evt,
            released_evt=released_evt,
            set_led_mode=led.set,
            auto_stop_on_silence=True,
            silence_timeout_seconds=cfg.WAKE_SILENCE_TIMEOUT_SECONDS,
            speech_rms_threshold=cfg.WAKE_SPEECH_RMS_THRESHOLD,
            max_record_seconds=cfg.WAKE_MAX_RECORD_SECONDS,
        )
    )
    wake_task = asyncio.create_task(_wake_loop(pressed_evt, released_evt, led, vosk_model))

    try:
        await asyncio.gather(gemini_task, wake_task)
    finally:
        gemini_task.cancel()
        wake_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExit.")
