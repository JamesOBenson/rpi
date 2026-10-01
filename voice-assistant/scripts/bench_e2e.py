#!/usr/bin/env python3
"""End-to-end latency bench: from end-of-speech to first audio.

Stages measured:
  1. whisper decode (real captured question audio)
  2. RAG retrieval
  3. LLM prefill + first sentence
  4. TTS synthesize first sentence

Usage:
  bench_e2e.py [--threads N] [--prompt full|short] [--topk K]
"""
import argparse, glob, os, sys, time, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

SHORT_PROMPT = """You are STEM Buddy, a friendly AI for 4th-5th graders.
Answer in 1-2 short sentences, simple words, no labels.
Use the facts below when relevant; ignore them otherwise."""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--prompt", choices=["full", "short"], default="full")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--audio", default=None)
    args = ap.parse_args()

    # Pick the best real capture by default
    audio_path = args.audio
    if not audio_path:
        cands = sorted(glob.glob(f"{ROOT}/logs/audio/q-*.wav"))
        audio_path = cands[-1] if cands else None
    if not audio_path or not os.path.exists(audio_path):
        print("No capture audio found - passing 'why is the sky blue' as text")
        q_audio, question = None, "why is the sky blue"
    else:
        print(f"Using real capture: {os.path.basename(audio_path)}")
        q_audio, question = np.frombuffer(
            wave.open(audio_path, "rb").readframes(
                wave.open(audio_path, "rb").getnframes()),
            dtype=np.int16), None

    print("Loading engines...", flush=True)
    from stt_engine import WakeWordListener
    from whisper_engine import WhisperSTT
    from llm_engine import LocalLLM
    from knowledge_base import KnowledgeBase
    from tts_engine import TextToSpeech

    wake = WakeWordListener(wake_word="buddy", model_size="small", hybrid=True)
    whisper = WhisperSTT(model_size="base.en", cpu_threads=4)
    llm = LocalLLM(n_threads=args.threads)
    if args.prompt == "short":
        llm.system_prompt = SHORT_PROMPT
    llm.initialize()
    kb = KnowledgeBase(); kb.initialize()
    tts = TextToSpeech()

    t0 = time.time()
    # --- Stage 1: STT (same path as production) ---
    if q_audio is not None:
        a16 = q_audio
        window = np.concatenate([a16, np.zeros(16000, dtype=np.int16)])
        audio = wake._normalize_for_asr(wake._trim_silence(window))
        text = whisper.transcribe(audio)
        q = wake._after_wake(text) if wake._has_wake(text) else wake._clean(text)
        question = q or question or "why is the sky blue"
    t_stt = time.time() - t0
    print(f"  STT : {t_stt:5.2f}s  -> {question!r}")

    # --- Stage 2: RAG ---
    t0 = time.time()
    ctx = kb.query(question, top_k=args.topk)
    t_rag = time.time() - t0
    print(f"  RAG : {t_rag:5.2f}s  (top_k={args.topk}, {len(ctx)} chars)")

    # --- Stage 3+4: LLM first sentence + TTS ---
    t0 = time.time()
    t_llm, t_tts = None, None
    first = None
    for sent in llm.query_with_rag_streaming(question, kb, top_k=args.topk):
        if first is None:
            t_llm = time.time() - t0
        wav = tts.synthesize(sent)
        if wav:
            if first is None:
                t_tts = time.time() - t0
                first = (t_llm, t_tts, sent)
            os.unlink(wav)
    if first:
        t_llm, t_tts, first_sent = first
        # t_tts is measured from the LLM-loop start, which includes the
        # in-loop RAG query - exactly one RAG, like production. So:
        total = t_stt + t_tts
        print(f"  LLM : {t_llm:5.2f}s  (first sentence: {first_sent[:60]!r}...)")
        print(f"  LLM+TTS: {t_tts:5.2f}s  (incl. in-loop RAG, gen + synth)")
        print(f"\n  >>> TOTAL end-of-speech -> first audio: {total:.2f}s")
    else:
        print("  LLM produced no sentences!")
    print(f"  (config: threads={args.threads}, prompt={args.prompt}, topk={args.topk})")

main()