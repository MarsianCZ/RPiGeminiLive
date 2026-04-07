#!/usr/bin/env python3
"""Push-to-Talk wrapper for Raspberry Pi + AIY Voice HAT.

This wrapper keeps GPIO button and LED handling in one file while Gemini Live
session/audio logic lives in gemini-on-voicehat.py and settings live in
app_config.py.
"""

import asyncio
import importlib.util
from pathlib import Path

from gpiozero import Button, PWMLED

import app_config as cfg


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
    def __init__(self, pin: int):
        self.led = PWMLED(pin)
        self.set(LedMode.IDLE)

    def set(self, mode: str):
        self.led.off()
        if mode == LedMode.IDLE:
            self.led.value = 0
        elif mode == LedMode.RECORDING:
            self.led.value = 1
        elif mode == LedMode.SPEAKING:
            self.led.pulse(
                fade_in_time=cfg.LED_SPEAKING_FADE_IN_SECONDS,
                fade_out_time=cfg.LED_SPEAKING_FADE_OUT_SECONDS,
                background=True,
            )
        elif mode == LedMode.ERROR:
            self.led.blink(
                on_time=cfg.LED_ERROR_BLINK_ON_SECONDS,
                off_time=cfg.LED_ERROR_BLINK_OFF_SECONDS,
                n=cfg.LED_ERROR_BLINK_COUNT,
                background=True,
            )
        else:
            self.led.value = 0


def bind_button_events(
    btn: Button,
    loop: asyncio.AbstractEventLoop,
    pressed_evt: asyncio.Event,
    released_evt: asyncio.Event,
) -> None:
    """Bridge GPIO button callbacks from thread context into asyncio events."""
    def on_press():
        loop.call_soon_threadsafe(pressed_evt.set)

    def on_release():
        loop.call_soon_threadsafe(released_evt.set)

    btn.when_pressed = on_press
    btn.when_released = on_release


async def main():
    print("Starting initialization...")
    led = LedController(cfg.LED_GPIO)

    loop = asyncio.get_running_loop()
    pressed_evt = asyncio.Event()
    released_evt = asyncio.Event()
    btn = Button(cfg.BTN_GPIO, pull_up=True, bounce_time=cfg.BTN_BOUNCE_SEC)
    bind_button_events(btn, loop, pressed_evt, released_evt)
    await run_gemini_session(
        pressed_evt=pressed_evt,
        released_evt=released_evt,
        set_led_mode=led.set,
        ready_hint="Hold the button to record (PTT). Ctrl+C to exit.",
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExit.")
