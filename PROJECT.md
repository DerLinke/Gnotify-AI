# Project: Gnotify AI

## Architecture
Gnotify AI is a desktop notification audio solution containing a server-side TTS engine (LocalAI/Kokoro TTS) and client-side modules:
1. **LocalAI Server (Docker)**: Runs Kokoro TTS on `cosmos-root`, exposing `/v1/audio/speech`.
2. **Cosmos Routing**: Routes `https://ai.dan.jetzt` -> `http://localhost:8089` (internal LocalAI port).
3. **Client-Daemon (`gnotify_ai_daemon.py`)**:
   - D-Bus eavesdropping client listening to `org.freedesktop.Notifications`.
   - Pattern matches notifications using configurable regex rules (first-match-wins).
   - Rate-limits notifications (max 5 in 30s) and deduplicates identical ones within a 5-second window.
   - Outputs audio via a spooler thread to ensure sequential play (via `paplay`).
   - Caches audio in `~/.cache/Gnotify-AI/tts/` based on MD5 hash of final text.
4. **Native GUI (`gnotify_ai_gui.py`)**:
   - Built with CustomTkinter.
   - Edits configuration, visualizes and reorders rules.
   - Monitors/controls the systemd user service.
   - Displays real-time logs in a non-blocking background thread.
5. **Installer (`install.sh`)**: Sets up Python venv, downloads/links systemd service, and ensures all dependencies are met.

## Code Layout
- `/home/dan/Projekte/autoAudioProfile/Gnotify-AI/` (Project Root)
  - `gnotify_ai_daemon.py` (Background Daemon)
  - `gnotify_ai_gui.py` (CustomTkinter GUI)
  - `config.json` (Configuration & Rules)
  - `install.sh` (Installation script)
  - `gnotify-ai.service` (Systemd User Service template)
  - `requirements.txt` (Python dependencies)
  - `tests/` (E2E and unit tests folder)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Server Setup & Routing | Set up CPU-optimized LocalAI Docker with Kokoro TTS on `cosmos-root` and configure Cosmos routing for `https://ai.dan.jetzt` | None | DONE |
| 2 | E2E Testing Track | Design and implement the E2E testing framework (Tiers 1-4) in `tests/`, producing `TEST_READY.md` | None | DONE |
| 3 | Client-Daemon | Build `gnotify_ai_daemon.py` with D-Bus eavesdropping, matching, spooling, deduplication, caching, and playback | M1 | DONE |
| 4 | Native GUI | Build `gnotify_ai_gui.py` using CustomTkinter with config, rules editor, service control, and live logging | M3 | IN_PROGRESS |
| 5 | Installer | Build `install.sh` to set up venv, systemd service, verify the E2E flow, and deploy | M4 | PLANNED |

## Interface Contracts
### Daemon ↔ Config (`config.json`)
The daemon and GUI exchange configuration and rules via a shared `config.json` file.
Structure:
```json
{
  "api_url": "https://ai.dan.jetzt/v1",
  "default_voice": "en-us-speaker",
  "rate_limit_max": 5,
  "rate_limit_window": 30,
  "deduplication_window": 5,
  "rules": [
    {
      "app_name": "Slack",
      "summary_regex": ".*",
      "body_regex": ".*",
      "action": "tts",
      "tts_template": "Slack message from {summary}: {body}"
    },
    {
      "app_name": "Thunderbird",
      "summary_regex": ".*",
      "body_regex": ".*",
      "action": "sound",
      "sound_file": "/path/to/mail.wav"
    },
    {
      "app_name": "System",
      "summary_regex": "Low Battery",
      "body_regex": ".*",
      "action": "mute"
    }
  ]
}
```

### LocalAI Speech API
- Endpoint: `POST https://ai.dan.jetzt/v1/audio/speech`
- Request Header: `Content-Type: application/json`
- Request Body:
  ```json
  {
    "input": "<text to speak>",
    "model": "kokoro",
    "voice": "<voice_name>"
  }
  ```
- Response: Audio data (WAV/MP3 format, content-type `audio/x-wav` or similar)
