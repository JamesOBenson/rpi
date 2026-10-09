#!/usr/bin/env python3
"""
Piper TTS HTTP Server
=====================
Keeps Piper TTS loaded in a dedicated process.
Accepts POST /synthesize with text, returns WAV audio.

Usage:
    python3 tts_server.py --voice en_US-amy-medium --port 8766

API:
    POST /synthesize
    Body: {"text": "hello world"}
    Response: WAV audio (binary)
    
    GET /health
    Response: {"status": "ok"}
"""

import argparse
import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 22050  # Piper default


class TTS:
    """Piper TTS singleton."""

    _instance = None
    _piper_path = None
    _voice_path = None
    _voice_config = None

    def __init__(self, voice: str = "en_US-amy-medium", port: int = 8766):
        if TTS._instance is not None:
            return

        self.voice = voice
        self.port = port

        # Find piper binary
        self.piper_path = self._find_piper()
        if not self.piper_path:
            raise RuntimeError("Piper binary not found - install piper-tts")

        # Find voice model
        voice_dir = PROJECT_ROOT / "voices" / voice
        if not voice_dir.exists():
            # Try alternative location
            voice_dir = PROJECT_ROOT / "models" / "piper" / voice

        self.voice_path = None
        self.voice_config = None

        # Look for .onnx model
        for f in voice_dir.glob("*.onnx"):
            self.voice_path = f
            break

        if not self.voice_path:
            raise RuntimeError(f"Voice model not found: {voice}")

        # Look for .onnx.json config
        for f in voice_dir.glob("*.onnx.json"):
            self.voice_config = f
            break

        print(f"✓ Piper TTS ready (voice: {voice})")
        TTS._instance = self

    def _find_piper(self) -> Path:
        """Find piper binary."""
        # Check common locations
        locations = [
            PROJECT_ROOT / "bin" / "piper",
            Path("/usr/local/bin/piper"),
            Path("/usr/bin/piper"),
            Path.home() / "piper" / "bin" / "piper",
        ]

        for loc in locations:
            if loc.exists() and loc.is_file():
                return loc

        # Check PATH
        import shutil

        piper = shutil.which("piper")
        if piper:
            return Path(piper)

        return None

    def synthesize(
        self, text: str, speed: float = 0.9, length_scale: float = 1.0
    ) -> bytes:
        """
        Synthesize text to WAV audio.

        Args:
            text: Text to synthesize
            speed: Overall speed multiplier (default 0.9)
            length_scale: Speech rate control (default 1.0, lower = faster)

        Returns:
            WAV audio bytes
        """
        import subprocess

        cmd = [
            str(self.piper_path),
            "-m",
            str(self.voice_path),
        ]

        if self.voice_config:
            cmd.extend(["-c", str(self.voice_config)])

        # Add optional parameters
        cmd.extend(["-s", str(speed), "-l", str(length_scale), "-f", "-"])

        try:
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                print(f"  ✗ Piper error: {result.stderr.decode()}")
                return b""

            return result.stdout

        except subprocess.TimeoutExpired:
            print("  ✗ Piper timeout")
            return b""
        except Exception as e:
            print(f"  ✗ Piper failed: {e}")
            return b""


class TTSHandler(BaseHTTPRequestHandler):
    """HTTP request handler for TTS."""

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
        """Synthesize text to speech."""
        if self.path != "/synthesize":
            self.send_response(404)
            self.end_headers()
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
            text = data.get("text", "")
            speed = data.get("speed", 0.9)
            length_scale = data.get("length_scale", 1.0)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        if not text.strip():
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Empty text"}).encode())
            return

        # Synthesize
        if TTS._instance is None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "TTS not loaded"}).encode())
            return

        audio = TTS._instance.synthesize(text, speed, length_scale)

        if not audio:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Synthesis failed"}).encode())
            return

        # Send WAV audio
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.end_headers()
        self.wfile.write(audio)


def main():
    parser = argparse.ArgumentParser(description="Piper TTS HTTP Server")
    parser.add_argument("--port", type=int, default=8766, help="Port to listen on")
    parser.add_argument("--voice", default="en_US-amy-medium", help="Piper voice model")
    args = parser.parse_args()

    # Initialize TTS
    try:
        tts = TTS(voice=args.voice, port=args.port)
    except RuntimeError as e:
        print(f"✗ {e}")
        sys.exit(1)

    # Start HTTP server
    host = "127.0.0.1"
    port = args.port
    httpd = HTTPServer((host, port), TTSHandler)
    print(f"✓ TTS server listening on http://{host}:{port}")
    print("  POST /synthesize - synthesize text to speech")
    print("  GET  /health - health check")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
