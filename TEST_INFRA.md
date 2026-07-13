# E2E Test Infra: Gnotify AI

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | Notification Matching | gnotify_original_request.md | 5 | 5 | ✓ |
| 2 | Speech Synthesis (TTS) | gnotify_original_request.md | 5 | 5 | ✓ |
| 3 | Audio Caching | gnotify_original_request.md | 5 | 5 | ✓ |
| 4 | Notification Spooling | gnotify_original_request.md | 5 | 5 | ✓ |
| 5 | Rate Limiting | gnotify_original_request.md | 5 | 5 | ✓ |
| 6 | Deduplication | gnotify_original_request.md | 5 | 5 | ✓ |

## Test Architecture
- Test runner: `tests/run_tests.py`, runs within a private D-Bus session (`dbus-run-session`).
- Test cases: divided across `tests/test_tier1.py`, `tests/test_tier2.py`, `tests/test_tier3.py`, and `tests/test_tier4.py`.
- Mocks:
  - D-Bus: `tests/mock_dbus.py` simulating standard org.freedesktop.Notifications.
  - TTS: `tests/mock_tts.py` simulating Kokoro TTS API.
  - paplay: mock executable injected via path.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Simulated Developer Workday | Matching, Spooling, Caching, TTS | Medium |
| 2 | Chat Spam Storm | Rate Limiting, Deduplication, Spooling | High |
| 3 | Flight Mode | Caching, Offline Failures, Fallback | High |
| 4 | CustomTkinter GUI Lifecycle | Hot-Reloading, SIGHUP, Configuration | High |
| 5 | System Restart Cache Persistence | Caching, Restart Persistence | Medium |

## Coverage Thresholds
- Tier 1: ≥5 per feature (Total 26 cases)
- Tier 2: ≥5 per feature (Total 26 cases)
- Tier 3: pairwise coverage of major feature interactions (Total 5 cases)
- Tier 4: ≥5 realistic application scenarios (Total 5 cases)
