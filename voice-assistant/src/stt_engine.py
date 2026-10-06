#!/usr/bin/env python3
"""
Speech-to-Text Engine
=====================
Offline speech recognition using Vosk.
Fast, accurate, and works completely offline.
"""

import json
import os
import re
import time
from collections import deque
import numpy as np
import sounddevice as sd
from pathlib import Path
from typing import Optional
from vosk import Model, KaldiRecognizer

# ASR non-speech marker spans: '[Music]', '(clanking)',
# '(speaking in foreign language)', '[BLANK_AUDIO]', ...
_MARKER_SPAN = re.compile(r"[\[\(][^\]\)]*[\]\)]")


def is_nonspeech(text: str) -> bool:
    """True if the transcript has <2 real words left after removing ASR
    non-speech markers. Whisper's no_speech_prob can't catch music - it
    scores music like speech (measured 0.17 on a pure-music file vs 0.09
    on real speech) - so marker detection is the only honest signal."""
    if not text or not text.strip():
        return True
    stripped = _MARKER_SPAN.sub(" ", text)
    words = [w for w in stripped.split() if any(c.isalpha() for c in w)]
    return len(words) < 2


def strip_markers(text: str) -> str:
    """Remove ASR marker spans so they never reach the LLM or TTS readback."""
    return re.sub(r"\s+", " ", _MARKER_SPAN.sub(" ", text)).strip()

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Available Vosk models (config: stt.model_size)
#   small = ~68MB, fastest   |   large = ~1.3GB, much more accurate
# Both stream in real time on a Raspberry Pi 5.
VOSK_MODELS = {
    "small": "vosk-model-small-en-us-0.15",
    "large": "vosk-model-en-us-0.22",
}


class SpeechToText:
    """Offline speech recognition with Vosk."""
    
    def __init__(
        self,
        model_name: str = "vosk-model-small-en-us-0.15",
        sample_rate: int = 16000
    ):
        self.model_name = model_name
        self.sample_rate = sample_rate
        self.recognizer = None
        self.model_path = PROJECT_ROOT / "models" / model_name
        
        self._init_vosk()
        
    def _init_vosk(self):
        """Initialize Vosk recognizer."""
        try:
            from vosk import Model, KaldiRecognizer
            
            # Check if model exists
            if not self.model_path.exists():
                self._download_model()
                
            # Load model (suppress noisy Kaldi C++ logs)
            import os
            devnull = os.open(os.devnull, os.O_WRONLY)
            saved = os.dup(2)
            os.dup2(devnull, 2)
            try:
                model = Model(str(self.model_path))
            finally:
                os.dup2(saved, 2)
                os.close(saved)
                os.close(devnull)
            self.recognizer = KaldiRecognizer(model, self.sample_rate)
            self.recognizer.SetWords(True)
            print(f"✓ Vosk STT initialized")
            
        except ImportError:
            print("✗ Install Vosk: pip install vosk")
            raise
        except Exception as e:
            print(f"✗ Vosk error: {e}")
            raise
            
    def _download_model(self):
        """Download Vosk model."""
        print(f"⬇️  Downloading model: {self.model_name}")
        print(f"   From: https://alphacephei.com/vosk/models/")
        print(f"   To: {self.model_path}")
        
        # For RPi, download manually:
        # wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
        # unzip vosk-model-small-en-us-0.15.zip -d models/
        
        raise FileNotFoundError(
            f"Model not found. Download from:\n"
            f"https://alphacephei.com/vosk/models/{self.model_name}.zip"
        )
        
    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio: NumPy array (16kHz, mono, float32)
            
        Returns:
            Transcribed text
        """
        if self.recognizer is None:
            raise RuntimeError("Vosk not initialized")
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Feed in ~0.1s chunks (1600 samples at 16kHz)
        chunk_size = 1600
        for i in range(0, len(audio_int16), chunk_size):
            chunk = audio_int16[i:i + chunk_size].tobytes()
            self.recognizer.AcceptWaveform(chunk)
        
        # Get final result
        result = json.loads(self.recognizer.FinalResult())
        return result.get("text", "")
        
    def transcribe_streaming(
        self,
        duration: float = 10.0,
        silence_threshold: float = 0.01
    ) -> str:
        """
        Transcribe streaming audio from microphone.
        
        Args:
            duration: Max listening time in seconds
            silence_threshold: Stop on silence below this
            
        Returns:
            Transcribed text
        """
        import time
        
        print("🎤 Listening...")
        start_time = time.time()
        audio_buffer = []
        silence_count = 0
        heard_speech = False
        
        # Record in chunks.
        # Waits up to `duration` for speech to START, then stops 0.8s after
        # speech ENDS (so it doesn't cut off before you begin talking).
        while time.time() - start_time < duration:
            chunk = sd.rec(
                int(0.1 * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocking=True
            )
            
            audio_buffer.append(chunk)
            
            energy = np.mean(np.abs(chunk))
            if energy >= silence_threshold:
                heard_speech = True
                silence_count = 0
            else:
                silence_count += 1
                # Only stop early once we've heard you, then 0.8s of silence
                if heard_speech and silence_count > 8:
                    print("  (end of speech)")
                    break
                
        # Combine and transcribe
        audio = np.concatenate(audio_buffer)
        result = self.transcribe(audio)
        
        if result:
            print(f"  → '{result}'")
            
        return result
        
    def reset(self):
        """Reset recognizer state."""
        if self.recognizer:
            self.recognizer.Reset()


class WakeWordListener:
    """
    Continuous wake-word detector.

    Stays on the mic at all times. The instant it hears the wake word
    ("buddy") it captures the question - either from the same utterance
    ("buddy what is a black hole") or the next one ("buddy" ... "what
    is a black hole"). This is like Alexa/Siri: always listening.
    """

    FILLERS = ("buddy", "buddies", "hey", "hi", "hello", "uh", "can you",
               "could you", "please", "what do you want to know",
               "what would you like to know")

    def __init__(
        self,
        model_path: str = None,
        model_size: str = "small",
        wake_word: str = "buddy",
        sample_rate: int = 16000,
        question_timeout: float = 12.0,
        hybrid: bool = False,
        debug_audio: bool = False,
        framework: str = "fallback",
        sensitivity: float = 0.6,
        access_key: str = "",
        keyword: str = "",
        keyword_path: str = "",
        wake_confidence: float = 0.3,
    ):
        if model_path is None:
            model_name = VOSK_MODELS.get(model_size, model_size)
            model_path = PROJECT_ROOT / "models" / model_name
            if not model_path.exists():
                fallback = PROJECT_ROOT / "models" / VOSK_MODELS["small"]
                if fallback.exists():
                    print(f"⚠  Vosk model '{model_name}' not found - falling back to small model")
                    model_path = fallback
            model_path = str(model_path)
        self.model_name = Path(model_path).name
        self.wake_word = wake_word.lower()
        # Words Whisper/Hailo might produce for the wake word (they hear
        # 'buddy' as 'button' or 'body' for some speakers). Vosk can't be
        # trusted for this - a strong engine is the wake-word judge.
        self.wake_variants = tuple(dict.fromkeys([
            self.wake_word,
            self.wake_word.rstrip("y") + "ies" if self.wake_word.endswith("y")
            else self.wake_word + "s",
            "button", "body",
        ]))
        self.whisper = None  # set by main.py (wake-word judge + fallback)
        self.hailo = None
        # Which engine produced the last wake-word-confirmed transcript
        # ("hailo" | "whisper" | None) - lets main.py skip a redundant
        # short-window re-judge when Whisper already did the work.
        self.last_source = None    # set by main.py when question_engine=hailo
        # Audio of the utterance that contained the wake word (the kid who
        # said "buddy") - speaker-lock reference for SpeakerFilter. Float32
        # 16k, starts at the utterance, ~3s max, set in wait_for_question.
        self.last_wake_audio = None
        # Directed questions are short; longer voiced windows are treated as
        # background conversation and skipped (avoids 17-25s Whisper decodes
        # that would block the wake loop).
        # Skip very long dense-voiced windows (TV, news, long rambles).
        # Kept at 10s, not less: users who don't hear a response repeat
        # their question, and repeated attempts fuse into 5-12s voiced
        # windows that a tighter threshold swallows (measured in the field
        # on 2026-10-01: seven repeat attempts skipped at 4.5s).
        self.max_question_sec = 10.0
        self.sample_rate = sample_rate
        self.question_timeout = question_timeout
        # Hybrid mode: keep raw audio around so a stronger engine (Whisper)
        # can transcribe the question after Vosk hears the wake word.
        self.hybrid = hybrid
        self.debug_audio = debug_audio
        self._ring = deque(maxlen=120)  # last 12s of 0.1s chunks
        self._cap = []  # audio captured since the wake word
        # Porcupine: dedicated keyword spotter for the wake word. Runs on
        # every idle chunk (32ms frames), costs ~no CPU, and ignores
        # background speech (TV) that Whisper would transcribe for 5-20s.
        # If unavailable (not installed / no access key) the Whisper
        # wake-word judge keeps working - graceful degradation.
        self.porcupine = None
        self._pv_buf = np.zeros(0, dtype=np.int16)
        # Grammar-constrained wake word: a second recognizer that can ONLY
        # output the wake word (or nothing). TV sentences map to ""; a real
        # "buddy" near the mic maps to "buddy" with a word confidence. No
        # transcription of idle audio at all - the 5-36s Whisper/Hailo
        # decodes of TV speech are gone. Runs on the already-loaded Vosk
        # model, so it costs almost nothing.
        self.wake_rec = None
        self.wake_conf = wake_confidence
        if framework == "porcupine":
            try:
                import pvporcupine
                kw = {"access_key": access_key,
                      "sensitivities": [sensitivity]}
                if keyword_path:
                    p = Path(keyword_path)
                    if not p.is_absolute():
                        p = PROJECT_ROOT / p
                    if not p.exists():
                        raise RuntimeError(f"keyword file missing: {p}")
                    kw["keyword_paths"] = [str(p)]
                elif keyword in pvporcupine.KEYWORDS:
                    kw["keywords"] = [keyword]
                else:
                    raise RuntimeError(
                        f"no keyword: '{keyword or wake_word}' is not a "
                        f"built-in (set keyword_path to a .ppn file)")
                # v4 factory: resolves library/model/keyword paths
                # (one-time download on first use, offline after).
                self.porcupine = pvporcupine.create(**kw)
                print(f"\u2713 Porcupine wake word ready "
                      f"(keyword: {keyword or Path(keyword_path).name}, "
                      f"sensitivity {sensitivity})")
            except Exception as e:
                print(f"\u26a0 Porcupine unavailable ({e}) - "
                      f"falling back to Whisper wake-word judge")

        print("Loading wake-word model (Vosk)...")
        # Suppress Kaldi C++ log spam during model load
        _err = os.dup(2)
        _devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(_devnull, 2)
        try:
            self.model = Model(model_path)
        finally:
            os.dup2(_err, 2)
            os.close(_devnull)
            os.close(_err)
        print(f"✓ Wake-word listener ready (Vosk model: {self.model_name}, always listening)")

        if framework == "vosk":
            # Model is loaded now - build the grammar-constrained wake word.
            self.wake_rec = KaldiRecognizer(
                self.model, self.sample_rate,
                json.dumps([self.wake_word, f"hey {self.wake_word}"]))
            self.wake_rec.SetWords(True)
            print(f"\u2713 Grammar wake word ready "
                  f"('{self.wake_word}', conf \u2265 {wake_confidence})")

    def _rec(self):
        return KaldiRecognizer(self.model, self.sample_rate)

    def _clean(self, text: str) -> str:
        return re.sub(r"[^a-z ]", "", text.lower()).strip()

    def _meaningful(self, text: str) -> bool:
        """True if text has at least 2 real (non-filler) words."""
        words = [w for w in self._clean(text).split() if w not in self.FILLERS]
        return len(words) >= 2

    def _after_wake(self, text: str) -> str:
        """Return the words that come after the (last) wake word."""
        clean = self._clean(text)
        # Cut at the FIRST wake-word occurrence: the wake word is said at the
        # start of the utterance. (Cutting at the last one breaks when a
        # variant like 'button' is also misheard later in the question.)
        start, end = -1, 0
        for v in self.wake_variants:
            i = clean.find(v)
            if i >= 0 and (start < 0 or i < start):
                start, end = i, i + len(v)
        after = clean[end:] if start >= 0 else clean
        for _ in range(4):
            new = re.sub(
                r"^(hey|hi|hello|buddy|buddies|button|can you|could you|please)\s+",
                "", after)
            if new == after:
                break
            after = new
        return after.strip()

    def _trim_silence(self, audio: Optional[np.ndarray],
                      frame_ms: int = 50, peak_ratio: float = 0.15,
                      floor: float = 30.0) -> Optional[np.ndarray]:
        """
        Trim leading/trailing silence from int16 16kHz audio.
        Returns float32 (-1..1), or None if there's no real speech.
        """
        if audio is None or len(audio) < self.sample_rate // 2:
            return None
        frame = max(1, self.sample_rate * frame_ms // 1000)
        n = len(audio) // frame
        if n < 3:
            return None
        energies = np.abs(audio[: n * frame].reshape(n, frame).astype(np.float32)).mean(axis=1)
        peak = float(energies.max())
        if peak < floor:  # ~-40dBFS: nothing was said
            return None
        thr = max(floor, peak_ratio * peak)
        voiced = np.nonzero(energies >= thr)[0]
        if len(voiced) == 0:
            return None
        # Tail is more forgiving than head: a word's ending (the nasal
        # in "-ing", rising question intonation) often drops below 15%
        # of peak relative to a loud "Hey buddy" at the start, and a
        # tight tail-trim clips the last word mid-syllable.
        thr_tail = max(floor, 0.05 * peak)
        tail = np.nonzero(energies >= thr_tail)[0]
        lo = max(0, int(voiced[0]) - 3)   # 0.15s pad before first speech
        hi = min(n, int(tail[-1]) + 6)    # 0.30s pad after last soft speech
        out = audio[lo * frame: hi * frame].astype(np.float32) / 32768.0
        # < 0.5s after trim = nothing real was said (blip + padding)
        return out if len(out) >= self.sample_rate // 2 else None

    def wait_for_question(self, stream):
        """
        Block on an open sounddevice InputStream until the wake word is
        heard and a question is captured.

        Returns (question_text, question_audio):
          - question_text: Vosk's transcript (always available)
          - question_audio: 16kHz mono float32 of the question, or None in
            non-hybrid mode. In hybrid mode a stronger engine (Whisper)
            transcribes this and its text usually wins.
        """
        rec = self._rec()
        state = "idle"  # or "question"
        state_start = time.time()
        chunk_frames = self.sample_rate // 10  # 0.1s

        while True:
            data, _overflow = stream.read(chunk_frames)
            pcm = (data.flatten() * 32767).astype(np.int16)
            chunk = pcm.tobytes()
            now = time.time()

            if self.hybrid:
                self._ring.append(pcm)
                if state == "question":
                    self._cap.append(pcm)

            if self.porcupine is not None and state == "idle":
                # Porcupine wants fixed 512-sample (32ms) frames; a 0.1s
                # chunk isn't a whole number of them, so carry the remainder.
                buf = np.concatenate([self._pv_buf, pcm])
                fl = self.porcupine.frame_length
                n = (len(buf) // fl) * fl
                self._pv_buf = buf[n:].copy()
                for f in range(n // fl):
                    if self.porcupine.process(buf[f * fl:(f + 1) * fl]) >= 0:
                        # Wake word heard. Capture the rest of the
                        # utterance (the question) until the next Vosk
                        # endpoint. Last 1.5s of the ring holds the wake
                        # word itself - speaker-lock reference.
                        tail = np.concatenate(list(self._ring)[-15:])
                        self.last_wake_audio = (tail / 32768.0
                                                ).astype(np.float32)
                        print("  \u2713 Wake word! Say your question")
                        state = "question"
                        state_start = now
                        self._cap = []
                        break

            if self.wake_rec is not None and state == "idle":
                # Grammar recognizer endpointing is independent of rec's.
                if self.wake_rec.AcceptWaveform(chunk):
                    res = json.loads(self.wake_rec.FinalResult())
                    self.wake_rec.Reset()
                    text = res.get("text", "")
                    if self.wake_word in text.split():
                        confs = [r.get("conf", 0.0)
                                 for r in res.get("result", [])]
                        conf = max(confs) if confs else 0.0
                        if conf >= self.wake_conf:
                            if self.hybrid:
                                # Speaker-lock reference: the ring's last
                                # 1.5s holds the wake word itself.
                                tail = np.concatenate(
                                    list(self._ring)[-15:])
                                self.last_wake_audio = (tail / 32768.0
                                                        ).astype(np.float32)
                                self._cap = []
                            print(f"  \u2713 Wake word! (conf {conf:.2f}) "
                                  f"Say your question")
                            state = "question"
                            state_start = now

            has_final = rec.AcceptWaveform(chunk)

            if not has_final:
                continue

            final = json.loads(rec.FinalResult()).get("text", "") or ""
            rec.Reset()
            now = time.time()

            if state == "idle":
                if (self.hybrid and self.whisper is not None
                        and self.porcupine is None and self.wake_rec is None
                        and final.strip()):
                    # Hybrid: Vosk only does endpointing ("someone spoke").
                    # Whisper hears the wake word where Vosk fails, so it
                    # gets the last word on whether this was 'buddy'.
                    window = np.concatenate(list(self._ring)[-60:])
                    audio = self._normalize_for_asr(
                        self._trim_silence(window))
                    if audio is None:
                        continue
                    # Directed questions are short. Long dense speech is
                    # background conversation - decoding it takes 17-25s and
                    # would block the wake loop, so skip it.
                    if len(audio) / self.sample_rate > self.max_question_sec:
                        print("  (long background speech - skipped)")
                        continue
                    # Hailo first (~0.6s): if it hears the wake word we're
                    # done. If not (misheard, or no Hailo), Whisper is the
                    # final judge - it still gets the last word, exactly as
                    # before.
                    text = ""
                    self.last_source = None
                    if self.hailo is not None:
                        try:
                            text = self.hailo.transcribe(audio)
                            if text:
                                self.last_source = "hailo"
                        except Exception as e:
                            print(f"  (hailo error: {e})")
                            text = ""
                    if not self._has_wake(text):
                        if text and is_nonspeech(text):
                            # Hailo only heard music/noise: whisper will
                            # hallucinate on it (measured 5-17s of fluent
                            # garbage, still no wake word). Skip the decode.
                            print("  (music/noise - skipping)")
                            self._save_idle_audio()
                            continue
                        text = self.whisper.transcribe(audio)
                        self.last_source = "whisper"
                    if self._has_wake(text):
                        # The trimmed window starts at the kid's utterance
                        # ("buddy ..."): keep it as the speaker reference.
                        self.last_wake_audio = audio[: int(3 * self.sample_rate)]
                        q = self._after_wake(text)
                        if self._meaningful(q):
                            # Wake word + question in ONE utterance. Text is
                            # already Whisper's - no second decode needed.
                            return q, audio
                        print("  ✓ Buddy! Say your question")
                        state = "question"
                        state_start = now
                        self._cap = []
                    else:
                        # Not addressed to us - show what we heard
                        print(f"  (heard: {text!r})")
                        self._save_idle_audio()
                elif self.wake_word in self._clean(final).split():
                    # Vosk-only mode: trust Vosk's wake detection
                    q = self._after_wake(final)
                    if self._meaningful(q):
                        # Wake word + question in ONE utterance
                        return q, None
                    print("  ✓ Buddy! Say your question")
                    state = "question"
                    state_start = now
                    if self.hybrid:
                        self._cap = []
                elif final.strip() and self.porcupine is None \
                        and self.wake_rec is None:
                    # Transparency: show what we heard when it wasn't the
                    # wake word (helps debug missed wake words / mic
                    # placement). Skipped in Porcupine mode: idle speech is
                    # deliberately NOT transcribed (that's the point).
                    print(f"  (heard: {final!r})")
                    self._save_idle_audio()
            else:  # already heard wake word, waiting for the question
                if self._meaningful(final):
                    audio = None
                    if self.hybrid and self._cap:
                        audio = self._normalize_for_asr(
                            self._trim_silence(np.concatenate(self._cap)))
                    if self.hybrid and audio is not None:
                        # Return empty text: main.py transcribes the capture
                        # (the wake word itself isn't in this audio).
                        return "", audio
                    return final, audio
                state_start = now  # was noise, keep waiting

            # Timeout: heard 'buddy' but no question
            if state == "question" and (now - state_start) > self.question_timeout:
                print("  (no question heard - back to listening for 'Buddy')")
                state = "idle"
                state_start = now
                if self.hybrid:
                    self._cap = []

    def _has_wake(self, text: str) -> bool:
        """True if any wake-word variant appears in the transcript."""
        return any(w in self.wake_variants for w in self._clean(text).split())

    def _normalize_for_asr(self, audio, target_peak: float = 0.9,
                           max_gain: float = 6.0):
        """Raise quiet audio before transcription (bounded gain)."""
        if audio is None:
            return None
        peak = float(np.abs(audio).max())
        if peak < 1e-4 or peak >= target_peak:
            return audio
        return audio * min(target_peak / peak, max_gain)

    def _save_idle_audio(self):
        """Save the last 6s of audio when a non-wake final arrived (debug)."""
        if not (self.hybrid and self.debug_audio):
            return
        try:
            import wave
            path = Path(__file__).parent.parent / "logs" / "audio" / \
                f"idle-{int(time.time() * 1000)}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            win = np.concatenate(list(self._ring)[-60:])
            pcm = (np.clip(win, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.sample_rate)
                w.writeframes(pcm.tobytes())
            print(f"  \U0001f399 idle audio saved: {path.name}")
        except Exception as e:
            print(f"  (idle audio save failed: {e})")

    def watch_for_stop(self, stream, stop_event, watching):
        """
        Run in a thread while the assistant is speaking. Listens for the
        word 'stop' and sets stop_event when heard. Consumes the stream in
        real time so no audio backlogs up. Stops when `watching` is cleared
        (answer finished) so it never lingers on the mic.
        """
        rec = self._rec()
        chunk_frames = self.sample_rate // 10
        while watching.is_set() and not stop_event.is_set():
            try:
                data, _overflow = stream.read(chunk_frames)
            except Exception:
                break
            chunk = (data.flatten() * 32767).astype(np.int16).tobytes()
            has_final = rec.AcceptWaveform(chunk)
            text = ""
            if has_final:
                text = json.loads(rec.FinalResult()).get("text", "") or ""
                rec.Reset()
            else:
                text = json.loads(rec.PartialResult()).get("text", "") or ""
            words = self._clean(text).split()
            # Require a SHORT utterance containing 'stop' - a human says
            # "stop" (1-2 words); our own TTS sentences are much longer.
            if "stop" in words and len(words) <= 4:
                stop_event.set()
                break


# Test
if __name__ == "__main__":
    print("STT Test - Say something...")
    stt = SpeechToText()
    text = stt.transcribe_streaming(duration=10.0)
    print(f"Result: {text}")