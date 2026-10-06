#!/usr/bin/env python3
"""
Whisper HTTP Server
===================
Keeps faster-whisper model loaded in a dedicated process.
Accepts POST /transcribe with audio, returns JSON transcript.

Usage:
    python3 whisper_server.py --port 8765 --model small.en

API:
    POST /transcribe
    Body: {"audio": "<base64-encoded-float32-array>", "prompt": "optional"}
    Response: {"text": "transcript", "duration": 0.123}
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 16000


class WhisperServer:
    """Singleton Whisper model holder."""
    _instance = None
    _model = None
    _initial_prompt = ""

    def __init__(self, model_size: str = "small.en", cpu_threads: int = 4,
                 initial_prompt: str = ""):
        if WhisperServer._instance is not None:
            return
        self.model_size = model_size
        self.initial_prompt = initial_prompt
        print(f"Loading Whisper model ({model_size}, {cpu_threads} threads)...")
        t0 = time.time()
        
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("✗ Install faster-whisper: pip install faster-whisper")
            sys.exit(1)
        
        self.model = WhisperModel(
            model_size, device="cpu", compute_type="int8",
            cpu_threads=cpu_threads,
        )
        print(f"✓ Whisper model ready in {time.time() - t0:.1f}s")
        WhisperServer._instance = self
        WhisperServer._model = self.model
        WhisperServer._initial_prompt = initial_prompt

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe 16kHz mono float32 audio."""
        if audio is None or len(audio) < SAMPLE_RATE // 10:
            return ""
        
        t0 = time.time()
        kwargs = {}
        if self.initial_prompt:
            kwargs["initial_prompt"] = self.initial_prompt
        
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            **kwargs,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        n_sec = len(audio) / SAMPLE_RATE
        print(f"  ⏱ whisper: {n_sec:.1f}s audio -> {time.time() - t0:.2f}s -> {text!r}")
        return text


class TranscribeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for transcription."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Health check."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Transcribe audio."""
        if self.path != "/transcribe":
            self.send_response(404)
            self.end_headers()
            return
        
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return
        
        # Decode audio
        try:
            audio_b64 = data.get("audio", "")
            audio_bytes = base64.b64decode(audio_b64)
            audio = np.frombuffer(audio_bytes, dtype=np.float32)
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        
        # Transcribe
        if WhisperServer._instance is None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Model not loaded"}).encode())
            return
        
        text = WhisperServer._instance.transcribe(audio)
        
        # Send response
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"text": text, "duration": len(audio) / SAMPLE_RATE}
        self.wfile.write(json.dumps(response).encode())


def main():
    parser = argparse.ArgumentParser(description="Whisper HTTP Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--model", default="small.en", help="Whisper model size")
    parser.add_argument("--threads", type=int, default=4, help="CPU threads")
    parser.add_argument("--prompt", default="", help="Initial prompt for domain bias")
    args = parser.parse_args()
    
    # Initialize model (singleton)
    WhisperServer(
        model_size=args.model,
        cpu_threads=args.threads,
        initial_prompt=args.prompt,
    )
    
    # Start HTTP server
    host = "127.0.0.1"
    port = args.port
    httpd = HTTPServer((host, port), TranscribeHandler)
    print(f"✓ Whisper server listening on http://{host}:{port}")
    print(f"  POST /transcribe - transcribe audio")
    print(f"  GET  /health - health check")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    main()