#!/usr/bin/env python3
"""Gemini Live session logic for push-to-talk wrapper."""

import asyncio
import sys
from collections.abc import Callable

from google import genai
from google.genai import types

import app_config as cfg


class LedMode:
    IDLE = "idle"
    RECORDING = "recording"
    SPEAKING = "speaking"


def require_api_key() -> None:
    if not cfg.API_KEY or cfg.API_KEY == "PUT_YOUR_GEMINI_API_KEY_HERE":
        print(
            "Missing api.api_key in config.json.",
            file=sys.stderr,
        )
        sys.exit(2)


async def spawn_player():
    return await asyncio.create_subprocess_exec(
        *cfg.APLAY_CMD,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )


async def run_gemini_session(
    pressed_evt: asyncio.Event,
    released_evt: asyncio.Event,
    set_led_mode: Callable[[str], None],
) -> None:
    """Run Gemini Live send/receive loop controlled by external button events."""
    require_api_key()

    client = genai.Client(api_key=cfg.API_KEY)
    player = await spawn_player()

    async def restart_player():
        nonlocal player
        try:
            if player and player.stdin:
                player.stdin.close()
            if player:
                player.terminate()
        except Exception:
            pass
        player = await spawn_player()

    async with client.aio.live.connect(model=cfg.MODEL, config=cfg.GEMINI_CONFIG) as session:
        print("✅ Connected. Hold the button to record (PTT). Ctrl+C to exit.")
        print(f"   Model: {cfg.MODEL}")
        print(f"   ALSA IN : {cfg.ALSA_IN_DEV}")
        print(f"   ALSA OUT: {cfg.ALSA_OUT_DEV}")
        if cfg.VOICE_NAME:
            print(f"   Voice: {cfg.VOICE_NAME}")

        async def receiver_loop():
            nonlocal player
            while True:
                turn = session.receive()
                had_audio = False
                audio_bytes = 0

                async for resp in turn:
                    sc = getattr(resp, "server_content", None)
                    if not sc:
                        continue

                    if getattr(sc, "interrupted", False):
                        set_led_mode(LedMode.IDLE)
                        await restart_player()
                        continue

                    out_tr = getattr(sc, "output_transcription", None)
                    if cfg.PRINT_TRANSCRIPT and out_tr and getattr(out_tr, "text", None):
                        print(f"\n📝 {out_tr.text}")

                    mt = getattr(sc, "model_turn", None)
                    if not mt:
                        continue

                    for part in mt.parts:
                        if part.inline_data and isinstance(
                            part.inline_data.data, (bytes, bytearray)
                        ):
                            if not had_audio:
                                had_audio = True
                                set_led_mode(LedMode.SPEAKING)
                            try:
                                audio_bytes += len(part.inline_data.data)
                                player.stdin.write(part.inline_data.data)
                                await player.stdin.drain()
                            except Exception:
                                await restart_player()

                if had_audio:
                    if cfg.PRINT_AUDIO_STATS:
                        print(f"\n🔊 played {audio_bytes} bytes")
                    set_led_mode(LedMode.IDLE)
                elif cfg.PRINT_AUDIO_STATS:
                    print("\n⚠️ No audio received in this turn.")

        recv_task = asyncio.create_task(receiver_loop())

        try:
            while True:
                pressed_evt.clear()
                released_evt.clear()
                await pressed_evt.wait()

                set_led_mode(LedMode.RECORDING)
                await session.send_realtime_input(activity_start=types.ActivityStart())

                rec = await asyncio.create_subprocess_exec(
                    *cfg.ARECORD_CMD,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # If arecord exits immediately, report ALSA error explicitly.
                await asyncio.sleep(0.05)
                if rec.returncode is not None:
                    err = b""
                    if rec.stderr:
                        err = await rec.stderr.read()
                    err_text = err.decode("utf-8", errors="replace").strip()
                    print(
                        f"\n⚠️ arecord failed on device '{cfg.ALSA_IN_DEV}'. "
                        f"{err_text or 'Unknown ALSA error.'}"
                    )
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                    set_led_mode(LedMode.IDLE)
                    continue

                # Stream chunks to Gemini as they are captured to minimize latency.
                sent_audio_chunks = 0
                while not released_evt.is_set():
                    try:
                        chunk = await asyncio.wait_for(rec.stdout.read(cfg.CHUNK), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue

                    if not chunk:
                        if rec.returncode is not None:
                            break
                        continue

                    try:
                        await session.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type=cfg.AUDIO_MIME)
                        )
                        sent_audio_chunks += 1
                    except Exception:
                        break

                try:
                    rec.terminate()
                except Exception:
                    pass

                arecord_err_text = ""
                if rec.stderr:
                    try:
                        await asyncio.wait_for(rec.wait(), timeout=0.3)
                    except Exception:
                        pass
                    err = await rec.stderr.read()
                    arecord_err_text = err.decode("utf-8", errors="replace").strip()

                if sent_audio_chunks == 0 and cfg.PRINT_AUDIO_STATS:
                    interrupted_shutdown = "Interrupted system call" in arecord_err_text
                    if arecord_err_text and not interrupted_shutdown:
                        print(
                            f"\n⚠️ arecord produced no audio on '{cfg.ALSA_IN_DEV}'. "
                            f"{arecord_err_text}"
                        )
                    if interrupted_shutdown:
                        print(
                            "\n⚠️ Button was released before audio frame capture."
                        )
                    print("\n⚠️ No microphone audio captured during button hold.")

                await session.send_realtime_input(activity_end=types.ActivityEnd())
                set_led_mode(LedMode.IDLE)

        except asyncio.CancelledError:
            pass
        finally:
            recv_task.cancel()
            set_led_mode(LedMode.IDLE)

    try:
        if player and player.stdin:
            player.stdin.close()
        if player:
            player.terminate()
    except Exception:
        pass
