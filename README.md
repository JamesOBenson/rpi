# Raspberry Pi Projects

Home for all Raspberry Pi projects. Each project lives in its own subfolder.

## Projects

| Folder | Description |
|--------|-------------|
| [`voice-assistant/`](voice-assistant/) | **STEM Buddy** — offline voice assistant: always-on wake word, RAG knowledge base, local LLM, text-to-speech, voice interrupt. Runs fully offline on a Pi 5. |
| [`leaked-password/`](leaked-password/) | **Leaked Password Checker** — Flask web app + CLI for password strength analysis (entropy, patterns) and HIBP breach checks, online or fully offline against a local copy of the HIBP database. `deploy.sh` runs it locally or on a Pi 5, optionally as a fullscreen browser kiosk (`--remote --kiosk`). |

## Conventions

- **Source code** is versioned here.
- **Large binaries** (models, weights, voices) are *not* committed. Download them
  with each project's setup script (e.g. `voice-assistant/download_models.sh`).
- **Python virtualenvs** live on the target device, not in this repo.
- Add a new project as a new subfolder and list it in the table above.