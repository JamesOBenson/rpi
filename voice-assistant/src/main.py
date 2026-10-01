#!/usr/bin/env python3
"""
STEM Buddy - Offline Voice Assistant
================================================
A voice assistant that runs completely offline on
Raspberry Pi 5. Always listening for the wake word.

Features:
- Continuous wake-word detection ("Buddy") - always on
- Voice interrupt: "STOP!" or physical button (GPIO, if available)
- 1000+ fact knowledge base (cybersecurity + STEM) with RAG
- Kid-friendly responses
- LED feedback (console colors if no GPIO)

License: MIT (Open Source)
"""

import asyncio
import os
import signal
import sys
import threading
import time

import yaml
import sounddevice as sd
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Import local modules
from stt_engine import WakeWordListener
from tts_engine import TextToSpeech
from llm_engine import LocalLLM
from knowledge_base import KnowledgeBase
from interrupt_handler import InterruptHandler
from led_controller import LEDController, LEDState

console = Console()

DEFAULT_CONFIG = "config/settings.yaml"


def load_config(path: str = DEFAULT_CONFIG) -> dict:
    """Load YAML configuration."""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠ Could not load config ({e}), using defaults")
        return {}


class STEMBuddy:
    """Main voice assistant orchestrator."""

    def __init__(self, config_path: str = DEFAULT_CONFIG):
        self.config = load_config(config_path)
        self.running = False
        self.stream = None

        llm_cfg = self.config.get("llm", {})
        gpio_cfg = self.config.get("gpio", {})
        self.top_k = self.config.get("rag", {}).get("top_k", 3)
        self.wake_word = self.config.get("app", {}).get("wake_word", "buddy")

        # Initialize components
        self.led = LEDController(enabled=gpio_cfg.get("enabled", False))
        stt_cfg = self.config.get("stt", {})
        # Continuous wake-word listener (always on the mic)
        self.wake = WakeWordListener(
            wake_word=self.wake_word,
            model_size=stt_cfg.get("model_size", "small")
        )
        self.tts = TextToSpeech()
        self.llm = LocalLLM(
            model_path=llm_cfg.get("model"),
            n_ctx=llm_cfg.get("context_window", 512),
            n_threads=llm_cfg.get("threads", 8)
        )
        self.knowledge_base = KnowledgeBase()
        self.interrupt = InterruptHandler(
            button_pin=gpio_cfg.get("button_pin", 4)
        )

        # Wire handlers
        self.interrupt.setup_button(self._on_button)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    async def start(self):
        """Start the voice assistant."""
        console.print(Panel(
            "[bold green]STEM BUDDY is starting![/bold green]\n"
            f"Say [bold]'{self.wake_word.capitalize()}'[/bold] then ask your question\n"
            "Say [bold]'STOP!'[/bold] to interrupt",
            title="[bold blue]STEM Buddy[/bold blue]"
        ))

        # Check for audio devices
        self._check_audio_devices()

        # Heavy init (LLM + knowledge base)
        self.llm.initialize()
        self.knowledge_base.initialize()
        self.led.set_state(LEDState.IDLE)

        self.running = True

        # One persistent microphone stream - always open while running
        self.stream = sd.InputStream(
            samplerate=self.wake.sample_rate, channels=1, dtype="float32"
        )
        self.stream.start()
        console.print("[green]✓ Microphone live - always listening[/green]")

        while self.running:
            try:
                self.led.set_state(LEDState.LISTENING)
                console.print(
                    f"[yellow]🎧 Listening... say [bold]'{self.wake_word.capitalize()}'[/bold][/yellow]"
                )

                # Blocks until "buddy" + question are captured
                question = self.wake.wait_for_question(self.stream)
                if not question:
                    continue

                question = question.strip()
                console.print(f"[blue]You said: {question}[/blue]")

                self._process_question(question)

            except KeyboardInterrupt:
                break
            except Exception as e:
                if not self.running:
                    break
                console.print(f"[red]Error: {e}[/red]")
                self.led.set_state(LEDState.ERROR)
                await asyncio.sleep(3)

        self._close_stream()

    def _close_stream(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def _check_audio_devices(self):
        """Warn clearly if no microphone/speakers are connected."""
        try:
            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            has_output = any(d.get("max_output_channels", 0) > 0 for d in devices)
            if not has_input:
                console.print(Panel("[red]No microphone detected![/red]\nPlug in a USB microphone and restart.", title="⚠ Audio"))
            if not has_output:
                console.print(Panel("[red]No speakers detected![/red]\nPlug in USB speakers and restart.", title="⚠ Audio"))
            if has_input and has_output:
                console.print("[green]✓ Audio devices found[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not check audio: {e}[/yellow]")

    def _process_question(self, question: str):
        """Process a question: stream RAG+LLM sentences, speak each as ready."""
        self.led.set_state(LEDState.THINKING)
        console.print("[yellow]Thinking...[/yellow]")

        stop_event = threading.Event()
        self.led.set_state(LEDState.SPEAKING)
        self._speak_streaming(question, stop_event)

        if stop_event.is_set():
            console.print("[red]Interrupted by 'STOP'[/red]")
            self.led.set_state(LEDState.INTERRUPTED)
        self.led.set_state(LEDState.IDLE)

    def _speak_streaming(self, question: str, stop_event: threading.Event):
        """
        Stream sentences from the LLM; synthesize each in a worker thread;
        play them in order. The first sentence starts playing while the LLM
        is still generating later ones - lower perceived latency.

        A mic-watcher thread listens for 'STOP' during playback and is
        guaranteed to be stopped before this returns (so it never lingers
        on the microphone and conflicts with the next listening cycle).
        """
        import queue

        ready = queue.Queue()

        def worker():
            for sent in self.llm.query_with_rag_streaming(
                question, self.knowledge_base, top_k=self.top_k
            ):
                if stop_event.is_set():
                    break
                sent = self._simplify_for_kids(sent)
                console.print(f"[cyan]▸ {sent}[/cyan]")
                wav = self.tts.synthesize(sent)
                if wav:
                    ready.put(wav)
            ready.put(None)  # sentinel

        wt = threading.Thread(target=worker, daemon=True)
        wt.start()

        # Watch the mic for 'STOP' only while we are speaking
        watching = threading.Event()
        watching.set()
        watcher = threading.Thread(
            target=self.wake.watch_for_stop,
            args=(self.stream, stop_event, watching),
            daemon=True
        )
        watcher.start()

        # Play sentences as they become ready (sequential, no overlap)
        while True:
            if stop_event.is_set():
                break
            item = ready.get()
            if item is None:
                break
            self.tts.play_wav(item, stop_event)
            Path(item).unlink(missing_ok=True)

        # Stop the mic watcher and worker BEFORE returning
        watching.clear()
        watcher.join(timeout=1)
        wt.join(timeout=2)

        # Clean up any synthesized-but-unplayed audio (e.g. after a STOP)
        while not ready.empty():
            try:
                leftover = ready.get_nowait()
                if leftover:
                    Path(leftover).unlink(missing_ok=True)
            except Exception:
                break

    def _simplify_for_kids(self, text: str) -> str:
        """Keep answers short and friendly."""
        text = text.strip()
        if len(text) > 250:
            cut = text[:250]
            last_period = cut.rfind(". ")
            if last_period > 100:
                text = cut[:last_period + 1]
            else:
                text = cut + "..."
        return text

    def _on_button(self):
        """GPIO button callback - stop speech immediately."""
        self.tts.stop()

    def _handle_signal(self, signum, frame):
        """Handle SIGINT / SIGTERM: clean shutdown + hard failsafe."""
        if getattr(self, "_shutting_down", False):
            return
        self._shutting_down = True
        console.print("\n[bold yellow]Shutting down...[/bold yellow]")
        self.running = False
        self._close_stream()
        # Failsafe: if the main thread can't finish cleanly within 3s
        # (e.g. blocked in a C call), force-exit so systemd never has to
        # SIGKILL us and stop/restart stays fast.
        def _force_exit():
            time.sleep(3)
            os._exit(0)
        threading.Thread(target=_force_exit, daemon=True).start()

    def stop(self):
        """Stop the voice assistant."""
        self.running = False
        self._close_stream()
        self.led.cleanup()
        self.interrupt.cleanup()
        console.print(Panel("STEM Buddy is offline. Goodbye!", style="blue"))


async def main():
    """Main entry point."""
    buddy = STEMBuddy()
    try:
        await buddy.start()
    except KeyboardInterrupt:
        buddy.stop()
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        buddy.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())