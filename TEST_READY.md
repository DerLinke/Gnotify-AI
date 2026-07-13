# Gnotify AI — E2E Testing Track Ready

This directory contains the complete End-to-End (E2E) testing suite, mocks, and runner for the **Gnotify AI** system. The infrastructure is designed to isolate the daemon under test, simulate all external dependencies, and assert behavior against the opaque-box interface constraints.

---

## 1. Mock Infrastructure

We have implemented three custom mock components under `tests/` to eliminate external dependencies and side-effects:

1. **Mock D-Bus Notification Service (`tests/mock_dbus.py`)**:
   - Registers the `org.freedesktop.Notifications` bus name on a private session bus.
   - Emulates `GetServerInformation()`, `GetCapabilities()`, and `Notify()` calls.
   - Returns monotonically increasing notification IDs.
   
2. **Mock LocalAI HTTP Server (`tests/mock_tts.py`)**:
   - A lightweight HTTP server running on a background process.
   - Exposes `POST /v1/audio/speech`.
   - Validates payload headers and content-types.
   - Generates minimal valid WAVE bytes (PCM format) to simulate synthesis outputs.
   - Supports controllable delays, status overrides (error injection), and content-type overrides via a file-based control structure (`mock_tts_config.json`).
   - Appends all incoming request logs to `tts_requests.log`.

3. **Mock `paplay` executable (`conftest.py` dynamic bin)**:
   - Written to the sandbox path `bin/paplay` and prepended to the daemon's `PATH`.
   - Captures playbacks, parses targets, calculates file MD5 checksums, and appends logs to `test_playback.log`.
   - Supports controllable exits via `mock_paplay_config.json`.

---

## 2. Sandboxing & Isolation

- **D-Bus Isolation**: All tests are run inside a private D-Bus session created by `dbus-run-session`.
- **Directory Isolation**: Every test case runs in a unique temporary `$HOME` folder. This isolates:
  - Configuration rules (`~/.config/Gnotify-AI/config.json`).
  - TTS Cache (`~/.cache/Gnotify-AI/tts/`).
  - Application logs (`~/.cache/Gnotify-AI/gnotify-ai.log`).
  - Mocks logging (`tts_requests.log`, `test_playback.log`).

---

## 3. Test Catalog (62 Cases)

The tests are categorized into four tiers across four files:

### Tier 1: Feature Coverage (26 Cases) — `tests/test_tier1.py`
- Happy-path validation for:
  - D-Bus notification eavesdropping.
  - Configuration parsing and exact/regex rule matching.
  - Multi-placeholder rendering.
  - Cache hits, cache misses, and fallback default rules.
  - Spooler sequential queuing, rate limiting (5 messages in 30s), and deduplication (5s window).
  - Directory auto-creation and graceful exit.

### Tier 2: Boundary & Corner (26 Cases) — `tests/test_tier2.py`
- Handles edge cases and error paths:
  - Empty or unicode notification fields, extremely long bodies (10k chars), and injection patterns.
  - Invalid config JSON, missing parameters, and missing APIs.
  - LocalAI failures (HTTP 500, timeouts, invalid wave headers, JSON error replies, connection refused).
  - Playback failures (sound file missing, no permission, missing `paplay`, `paplay` returning code 1).
  - Boundary settings (deduplication window = 0, rate limit window = 0).
  - SIGHUP configuration hot-reloading, pathological regex rules, and disk full simulations.

### Tier 3: Cross-Feature Combinations (5 Cases) — `tests/test_tier3.py`
- Complex cross-feature interactions:
  - Spooling + Rate Limiting + Deduplication ordering.
  - Cache hits alongside asynchronous spooler queue ordering.
  - Interaction of Mute rules within rate limiting counts.
  - Hot reloading priorities.
  - Concurrent TTS cache misses deduplication.

### Tier 4: Real-World Scenarios (5 Cases) — `tests/test_tier4.py`
- Integration simulation:
  - **T4.1: Simulated Developer Workday**: Timeline of Slack, Git, and Cron alerts.
  - **T4.2: Chat Spam Storm**: Rapid flood of chat notifications.
  - **T4.3: Flight Mode**: Transition from online -> offline (cache hit fallback) -> online.
  - **T4.4: CustomTkinter GUI Lifecycle**: GUI edits config, sends SIGHUP, daemon reloads rules.
  - **T4.5: System Restart Cache Persistence**: Daemon restart does not trigger duplicate TTS requests.

---

## 4. How to Run the Tests

To run the complete test suite, execute the test runner script from the project root:

```bash
python3 Gnotify-AI/tests/run_tests.py
```

Or run `pytest` directly inside a private D-Bus session:

```bash
dbus-run-session -- python3 -m pytest -v Gnotify-AI/tests/
```

To run syntax verification only:

```bash
python3 Gnotify-AI/tests/verify_syntax.py
```
