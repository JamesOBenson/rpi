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
import re
import signal
import sys
import threading
import time

import yaml
import numpy as np
import sounddevice as sd
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Import local modules
from stt_engine import WakeWordListener, is_nonspeech, strip_markers
from whisper_engine import WhisperSTT
from whisper_client import WhisperClient
from tts_engine import TextToSpeech
from tts_client import TTSClient
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
        rag_cfg = self.config.get("rag", {})
        self.top_k = rag_cfg.get("top_k", 3)
        self.similarity_threshold = rag_cfg.get("similarity_threshold", 0.8)
        self.wake_word = self.config.get("app", {}).get("wake_word", "buddy")

        # Initialize components
        self.led = LEDController(enabled=gpio_cfg.get("enabled", False))
        stt_cfg = self.config.get("stt", {})
        self.stt_cfg = stt_cfg
        self.question_engine = stt_cfg.get("question_engine", "whisper").lower()

        # Wake word detection
        ww_cfg = self.config.get("wake_word", {})
        ww_framework = ww_cfg.get("framework", "openwakeword").lower()

        # Initialize wake word listener based on framework.
        # Both frameworks run inside WakeWordListener: openwakeword adds
        # its detector on top of the Vosk grammar one (whichever hears
        # the wake word first wins); if OWW can't load, Vosk carries alone.
        wake_words = [w.strip() for w in ww_cfg.get("wake_words", "buddy").split(",")]
        self.wake = WakeWordListener(
            wake_word=self.wake_word,
            model_size=stt_cfg.get("model_size", "small"),
            hybrid=(self.question_engine in ("whisper", "hailo", "whisper-http")),
            debug_audio=stt_cfg.get("debug_audio", False),
            framework="vosk",
            wake_confidence=ww_cfg.get("wake_confidence", 0.3),
            oww_models=wake_words if ww_framework == "openwakeword" else None,
            oww_threshold=ww_cfg.get("threshold", 0.5),
            oww_cooldown=ww_cfg.get("cooldown", 1.5),
        )
        if ww_framework == "openwakeword" and self.wake.oww_model is None:
            print("⚠ OpenWakeWord unavailable - using Vosk grammar wake")
        elif ww_framework == "openwakeword":
            print(f"✓ Using OpenWakeWord (wake words: {wake_words})")
        else:
            print("✓ Using Vosk wake word detection")
        self.whisper = None
        self.hailo = None
        if self.question_engine in ("whisper", "hailo", "whisper-http"):
            # CPU Whisper is ALWAYS loaded in hybrid modes: it is the
            # wake-word judge (Vosk can't reliably hear 'buddy'), and the
            # automatic fallback when Hailo is absent or fails.
            if self.question_engine == "whisper-http":
                # Use HTTP client - model stays warm in separate process
                self.whisper = WhisperClient(
                    server_url=stt_cfg.get(
                        "whisper_server_url", "http://127.0.0.1:8765"
                    ),
                    timeout=stt_cfg.get("whisper_timeout", 30.0),
                )
            else:
                # Direct model loading (original behavior)
                self.whisper = WhisperSTT(
                    model_size=stt_cfg.get("whisper_model", "base.en"),
                    cpu_threads=stt_cfg.get("whisper_threads", 4),
                    initial_prompt=stt_cfg.get("whisper_prompt", ""),
                )
            self.wake.whisper = self.whisper
            if self.question_engine == "hailo":
                try:
                    from hailo_whisper_engine import HailoWhisperSTT

                    self.hailo = HailoWhisperSTT(
                        model_dir=stt_cfg.get("hailo_model_dir") or None
                    )
                    self.wake.hailo = self.hailo
                except Exception as e:
                    print(
                        f"⚠ Hailo STT unavailable ({e}) - " f"using CPU Whisper instead"
                    )
        # Speaker lock: after "buddy", keep only the voice that said it in
        # the question window; background voices (TV, other kids) are
        # zeroed out before STT. Contaminated references fall back to the
        # original audio, so it degrades to today's behavior at worst.
        self.spk_filter = None
        spk_cfg = stt_cfg.get("speaker_lock", {})
        if spk_cfg.get("enabled", True) and self.question_engine in (
            "whisper",
            "hailo",
            "whisper-http",
        ):
            try:
                from speaker_filter import SpeakerFilter

                model_path = Path(spk_cfg.get("model", "models/spk/campplus_en.onnx"))
                if not model_path.is_absolute():
                    model_path = Path(__file__).parent.parent / model_path
                self.spk_filter = SpeakerFilter(
                    str(model_path),
                    threshold=spk_cfg.get("threshold", 0.75),
                    min_keep=spk_cfg.get("min_keep", 0.25),
                    num_threads=spk_cfg.get("threads", 4),
                )
                console.print(
                    f"[green]✓ Speaker lock on (same-speaker ≥ {self.spk_filter.threshold})[/green]"
                )
            except Exception as e:
                console.print(f"[yellow]⚠ Speaker lock unavailable ({e})[/yellow]")

        # Initialize TTS (direct or HTTP mode)
        tts_cfg = self.config.get("tts", {})
        tts_mode = tts_cfg.get("mode", "direct").lower()
        if tts_mode == "http":
            try:
                self.tts = TTSClient(
                    server_url=tts_cfg.get("http_server_url", "http://127.0.0.1:8766"),
                    timeout=tts_cfg.get("http_timeout", 30.0),
                )
                console.print("[green]✓ TTS HTTP client ready[/green]")
            except Exception as e:
                console.print(
                    f"[yellow]⚠ TTS server unavailable ({e}) - falling back to direct[/yellow]"
                )
                self.tts = TextToSpeech()
        else:
            self.tts = TextToSpeech()
        self.llm = LocalLLM(
            model_path=llm_cfg.get("model"),
            n_ctx=llm_cfg.get("context_window", 512),
            n_threads=llm_cfg.get("threads", 8),
        )
        self.knowledge_base = KnowledgeBase(max_distance=self.similarity_threshold)
        self.interrupt = InterruptHandler(button_pin=gpio_cfg.get("button_pin", 4))

        # Wire handlers
        self.interrupt.setup_button(self._on_button)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    async def start(self):
        """Start the voice assistant."""
        console.print(
            Panel(
                "[bold green]STEM BUDDY is starting![/bold green]\n"
                f"Say [bold]'{self.wake_word.capitalize()}'[/bold] then ask your question\n"
                "Say [bold]'STOP!'[/bold] to interrupt",
                title="[bold blue]STEM Buddy[/bold blue]",
            )
        )

        # Check for audio devices
        self._check_audio_devices()

        # Heavy init (LLM + knowledge base)
        self.llm.initialize()
        self.knowledge_base.initialize()
        self.led.set_state(LEDState.IDLE)

        self.running = True

        # One persistent microphone stream - always open while running.
        # Opened at 48 kHz when noise suppression is on: RNNoise works at
        # 48k and the wrapper hands 16k back to everything downstream.
        ns = self.config.get("audio", {}).get("noise_suppression", True)
        audio_cfg = self.config.get("audio", {})
        try:
            from audio_chain import SignalChain, HighPass, AGC

            hp_hz = float(audio_cfg.get("highpass_hz", 100))
            hp = HighPass(sr=self.wake.sample_rate, fc=hp_hz)
            agc = AGC() if audio_cfg.get("agc", True) else None
        except Exception as e:
            hp = agc = None
            hp_hz = 0
            console.print(f"[yellow]⚠ signal chain unavailable ({e})[/yellow]")
        if ns:
            try:
                from noise_suppressor import NoiseSuppressedStream

                base = sd.InputStream(samplerate=48000, channels=1, dtype="float32")
                base.start()
                self.stream = SignalChain(NoiseSuppressedStream(base), hp, agc)
                console.print(
                    f"[green]✓ RNNoise + highpass {hp_hz:.0f} Hz"
                    + (" + AGC[/green]" if agc else "[/green]")
                )
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Noise suppression unavailable ({e}) - raw mic[/yellow]"
                )
                ns = False
        if not ns:
            base = sd.InputStream(
                samplerate=self.wake.sample_rate, channels=1, dtype="float32"
            )
            base.start()
            self.stream = SignalChain(base, hp, agc)
        console.print("[green]✓ Microphone live - always listening[/green]")

        while self.running:
            try:
                self.led.set_state(LEDState.LISTENING)
                console.print(
                    f"[yellow]🎧 Listening... say [bold]'{self.wake_word.capitalize()}'[/bold][/yellow]"
                )

                # Blocks until "buddy" + question are captured
                question, q_audio = self.wake.wait_for_question(self.stream)
                if q_audio is not None:
                    # Quiet speech (peak ~0.2) measurably degrades every STT
                    # engine; raise it to a comfortable level first.
                    q_audio = self._normalize(q_audio)
                    if self.stt_cfg.get("debug_audio"):
                        self._save_debug_audio(q_audio, "-raw")
                    if self.spk_filter is not None:
                        # Speaker lock: keep only the voice that said
                        # "buddy"; the rest (TV, other kids) goes to zero.
                        ref = self.spk_filter.reference(self.wake.last_wake_audio)
                        q_audio, spk_info = self.spk_filter.filter(q_audio, ref)
                        print(f"  (speaker lock: {spk_info})")
                    if self.stt_cfg.get("debug_audio"):
                        self._save_debug_audio(q_audio)
                        # raw mic recording of the same window (A/B compare)
                        raw_last = getattr(self.stream, "raw_last", None)
                        if raw_last is not None:
                            mic = raw_last(len(q_audio) / 16000 + 0.5)
                            if len(mic):
                                self._save_debug_audio(mic, "-mic", samplerate=48000)
                if not question and self.whisper is not None and q_audio is not None:
                    # Separate-utterance case: wake word was its own sentence,
                    # so the question audio wasn't transcribed yet.
                    question_source = None
                    if self.hailo is not None:
                        h = self._safe_hailo(q_audio)
                        if h and is_nonspeech(h):
                            # Hailo heard only music/noise. Whisper would
                            # just hallucinate on it (measured 5-17s of
                            # fluent garbage) - same answer, much slower.
                            print("  (music/noise - not a question)")
                            continue
                        if h and len(h.split()) >= 2:
                            question = self._strip_wake(h)
                            question_source = "hailo"
                    if not question:
                        w = self.whisper.transcribe(q_audio)
                        if w:
                            question = self._strip_wake(w)
                            question_source = "whisper"
                else:
                    question_source = self.wake.last_source
                if (
                    question
                    and question_source == "hailo"
                    and self.whisper is not None
                    and q_audio is not None
                    and (len(q_audio) < 3.5 * 16000 or is_nonspeech(question))
                ):
                    # Short-window re-judge: the Hailo 5s model is
                    # out-of-distribution on <~3s of speech and garbles it
                    # ("black holes" -> "black horse"). CPU Whisper handles
                    # short audio fine; if it heard something usable, prefer
                    # it. Keep the existing text if Whisper comes up empty.
                    w = self.whisper.transcribe(q_audio)
                    if w:
                        w = w.strip()
                        if self.wake._has_wake(w):
                            cand = self.wake._after_wake(w)
                        else:
                            cand = self._strip_wake(w)
                        if cand and len(cand.split()) >= 2:
                            question = cand
                if not question:
                    continue

                question = strip_markers(question).strip()
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
        # Release the Hailo device BEFORE Python teardown: letting HailoRT
        # destruct alongside ctranslate2/vosk crashes (SIGBUS/SIGSEGV) and
        # would make systemd see an abnormal exit + restart flap.
        if self.hailo is not None:
            try:
                self.hailo.close()
            except Exception:
                pass
            self.hailo = None
            self.wake.hailo = None

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
                console.print(
                    Panel(
                        "[red]No microphone detected![/red]\nPlug in a USB microphone and restart.",
                        title="⚠ Audio",
                    )
                )
            if not has_output:
                console.print(
                    Panel(
                        "[red]No speakers detected![/red]\nPlug in USB speakers and restart.",
                        title="⚠ Audio",
                    )
                )
            if has_input and has_output:
                console.print("[green]✓ Audio devices found[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not check audio: {e}[/yellow]")

    def _looks_unintelligible(self, question: str) -> bool:
        """Heuristic: short, no question word, nothing related in the KB.

        Threshold 0.75 (tighter than the RAG context filter at 0.8):
        measured nearest-fact distances - real questions 0.22-0.72
        (worst: "tell me your black horse" -> 0.72), misheard fragments
        and non-questions 0.76-0.78 ("blah", "uh huh").
        """
        if len(question.split()) > 5:
            return False
        q = question.lower()
        question_words = (
            "why",
            "how",
            "what",
            "when",
            "where",
            "who",
            "do",
            "does",
            "can",
            "is",
            "are",
            "tell me",
        )
        if any(w in q for w in question_words):
            return False
        try:
            hits = self.knowledge_base.query(question, top_k=1)
            if not hits:
                return True
            return hits[0]["distance"] > 0.75
        except Exception:
            return False

    def _safe_hailo(self, audio: np.ndarray) -> str:
        """Hailo transcription with automatic CPU fallback on any error."""
        if self.hailo is None:
            return ""
        try:
            return self.hailo.transcribe(audio)
        except Exception as e:
            print(f"  (hailo error: {e} - falling back to CPU Whisper)")
            self.hailo = None
            self.wake.hailo = None
            return ""

    def _save_debug_audio(
        self, audio: np.ndarray, suffix: str = "", samplerate: int = 16000
    ):
        """Save the captured question WAV for debugging (stt.debug_audio: true)."""
        try:
            import wave

            path = (
                Path(__file__).parent.parent
                / "logs"
                / "audio"
                / f"q-{time.strftime('%Y%m%d-%H%M%S')}{suffix}.wav"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(samplerate)
                w.writeframes(pcm.tobytes())
            print(
                f"  \U0001f399 debug audio saved: {path.name} "
                f"({len(audio)/samplerate:.1f}s, peak={float(np.abs(audio).max()):.3f})"
            )
        except Exception as e:
            print(f"  (debug audio save failed: {e})")

    def _normalize(
        self, audio: np.ndarray, target_peak: float = 0.9, max_gain: float = 6.0
    ) -> np.ndarray:
        """Raise quiet question audio to a comfortable level for Whisper.

        Bounded gain (max 6x) helps quiet speech without turning room
        noise into a wall of sound. Audio already at/above target is
        passed through untouched.

        The capture starts with the wake word, which kids shout right
        into the mic (peak ~0.9) while the actual question lands at
        0.2-0.4. So: find the first quiet gap after startup voice and
        drop everything before it (pre-wake room noise + the wake word
        itself), then scale the remainder to target. One-breath
        "buddy <question>" has no gap and is left whole.
        """
        peak = float(np.abs(audio).max())
        if peak < 1e-4:
            return audio
        sr = 16000
        n = len(audio)
        if n > 2 * sr:  # >2s: there is a wake word to skip past
            frame = sr // 10  # 0.1s
            env = [
                float(np.abs(audio[i * frame : (i + 1) * frame]).max())
                for i in range(min(40, n // frame))
            ]
            for i in range(len(env) - 1):
                if env[i] > 0.15 and env[i + 1] < 0.10:  # voice -> gap
                    start = (i + 1) * frame
                    if start > 0.3 * sr and n - start > 0.5 * sr:
                        audio = audio[start:]
                    break
        peak = float(np.abs(audio).max())
        if peak < 1e-4 or peak >= target_peak:
            return audio
        gain = min(target_peak / peak, max_gain)
        return np.clip(audio * gain, -1.0, 1.0)

    def _strip_wake(self, text: str) -> str:
        """Remove a leading wake word / filler from a transcript.

        Whisper keeps the 'Buddy,' it heard in the transcript; the Vosk
        path already returns text with the wake word removed.
        """
        t = text.strip()
        while True:
            m = re.match(
                r"^(?:buddy|buddies|button|body|hey|hi|hello|can you|could you|please)[,.!?;\s]*",
                t,
                re.IGNORECASE,
            )
            if not m or m.end() == 0:
                return t.strip()
            t = t[m.end() :]

    def _process_question(self, question: str):
        """Process a question: stream RAG+LLM sentences, speak each as ready."""
        if self._looks_unintelligible(question):
            # A short fragment with no question word and nothing related in
            # the fact base is almost always a misheard utterance. Ask for a
            # repeat instead of answering nonsense ("I'm not sure" is a dead
            # end for a 9-year-old).
            self.led.set_state(LEDState.SPEAKING)
            console.print(
                "[yellow]▸ Sorry, I didn't catch that! Can you say it again?[/yellow]"
            )
            self.tts.speak("Sorry, I didn't catch that! Can you say it again?")
            self.led.set_state(LEDState.IDLE)
            return

        self.led.set_state(LEDState.THINKING)
        console.print("[yellow]Thinking...[/yellow]")

        stop_event = threading.Event()
        self.led.set_state(LEDState.SPEAKING)
        self._speak_streaming(question, stop_event)
        # Echo gate: ignore the acoustic tail of our own TTS (room reverb,
        # same-board speaker) so it can't trip the wake word.
        self.wake.muted_until = time.time() + 0.6

        if stop_event.is_set():
            console.print("[red]Interrupted by 'STOP'[/red]")
            self.led.set_state(LEDState.INTERRUPTED)
        self.led.set_state(LEDState.IDLE)

    def _speak_streaming(self, question: str, stop_event: threading.Event):
        """
        Stream sentences from the LLM; synthesize each in a worker thread;
        play them in order. The first sentence starts playing while the LLM
        is still generating later ones - lower perceived latency.

        The readback ("I heard you say: ...") is enqueued first, so it plays
        while the LLM is still thinking - instant confirmation of what was
        heard, and the answer follows right after.

        A mic-watcher thread listens for 'STOP' during playback and is
        guaranteed to be stopped before this returns (so it never lingers
        on the microphone and conflicts with the next listening cycle).
        """
        import queue

        ready = queue.Queue()

        rb = self._readback_text(question)
        if rb:
            console.print(f"[dim]↺ {rb}[/dim]")
            rb_wav = self.tts.synthesize(rb)
            if rb_wav:
                ready.put(rb_wav)

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
            daemon=True,
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

    @staticmethod
    def _readback_text(question: str) -> str:
        """Readback line spoken before the answer. '' if there's nothing
        sensible to repeat (e.g. Whisper non-speech markers in the text)."""
        q = question.strip()
        if not q or "(" in q:
            return ""
        if not q.endswith((".", "!", "?")):
            q += "."
        return f"I heard you say: {q} My answer is:"

    def _simplify_for_kids(self, text: str) -> str:
        """Keep answers short and friendly."""
        text = text.strip()
        if len(text) > 250:
            cut = text[:250]
            last_period = cut.rfind(". ")
            if last_period > 100:
                text = cut[: last_period + 1]
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
        # Release the Hailo device explicitly: tearing down HailoRT together
        # with ctranslate2/vosk at Python exit segfaults non-deterministically.
        if self.hailo is not None:
            try:
                self.hailo.close()
            except Exception:
                pass
            self.hailo = None
            self.wake.hailo = None
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
