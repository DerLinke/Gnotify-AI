import os
import time
import json
import pytest
import hashlib

# Tier 4: Real-World Application Scenarios (5 Cases)

def test_t4_1_simulated_developer_workday(sandbox):
    """T4.1: Simulated Developer Workday.
    Timeline:
    - 0s: Slack message from Boss (Action: TTS Voice A)
    - 5s: Git push notification (Action: Sound Alert)
    - 10s: Low Battery warning (Action: TTS Voice B)
    - 30s: Slack message from Boss (Action: TTS Voice A - Cache Hit)
    - 45s: Git push notification (Action: Sound Alert - Playback)
    - 60s: Standard cron job log alert (Action: Mute)
    Verify 5 playbacks, 2 unique TTS requests."""
    sound_path = os.path.join(sandbox.home, "git_push.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "voice-a",
        "deduplication_window": 1,
        "rules": [
            {"app_name": "Slack", "action": "tts", "voice": "voice-a"},
            {"app_name": "Git", "action": "sound", "sound_file": sound_path},
            {"app_name": "System", "summary_regex": "Low Battery", "action": "tts", "voice": "voice-b"},
            {"app_name": "Cron", "action": "mute"}
        ]
    })
    
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.start_daemon()
    
    # 0s: Slack message
    sandbox.send_notification("Slack", "Boss", "Get to work")
    time.sleep(1.0)
    
    # 5s: Git push
    sandbox.send_notification("Git", "Push", "Branch main")
    time.sleep(1.0)
    
    # 10s: Low Battery
    sandbox.send_notification("System", "Low Battery", "Plug in")
    time.sleep(1.0)
    
    # 20s-30s: Slack message (cache hit)
    sandbox.send_notification("Slack", "Boss", "Get to work")
    time.sleep(1.0)
    
    # 45s: Git push
    sandbox.send_notification("Git", "Push", "Branch main")
    time.sleep(1.0)
    
    # 60s: Cron alert (mute)
    sandbox.send_notification("Cron", "Alert", "Job finished")
    time.sleep(1.0)
    
    # Total playback count:
    # 1 Slack (Miss) + 1 Git (Sound) + 1 System (Miss) + 1 Slack (Hit) + 1 Git (Sound) = 5
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 5
    
    # Total TTS Requests:
    # 1 Slack Boss + 1 System Low Battery = 2
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) == 2

def test_t4_2_chat_spam_storm(sandbox):
    """T4.2: Chat Spam Storm.
    Send 20 messages in 15 seconds. First 5 play, remaining 15 dropped by rate limiting."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 5,
        "rate_limit_window": 30,
        "rules": []
    })
    sandbox.start_daemon()
    
    for i in range(20):
        sandbox.send_notification("ChatApp", f"User {i}", f"Message body {i}")
        time.sleep(0.1)
        
    time.sleep(3.0)
    
    # Assert playbacks = 5
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 5
    
    # Assert log shows rate limit drops
    log_content = sandbox.read_daemon_log()
    assert "Rate Limit" in log_content

def test_t4_3_flight_mode_offline_state_transition(sandbox):
    """T4.3: Flight Mode (Offline State transition).
    1. Online: Send Msg A (cache miss) -> plays.
    2. Offline: Send Msg B (cache miss, TTS fails/503) -> logs fail, doesn't block.
    3. Offline: Send Msg A again -> plays from cache (offline capability).
    4. Online: Send Msg C (cache miss) -> plays."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 1,
        "rules": []
    })
    sandbox.start_daemon()
    
    # 1. Online: Send A
    sandbox.send_notification("App", "Msg A", "A")
    time.sleep(1.0)
    
    # 2. Go Offline: Mock TTS returns 503 Service Unavailable
    sandbox.write_mock_tts_config(status_code=503)
    sandbox.send_notification("App", "Msg B", "B")
    time.sleep(1.0)
    
    # 3. Send Msg A again (should play from cache)
    sandbox.send_notification("App", "Msg A", "A")
    time.sleep(1.0)
    
    # 4. Go Online: Mock TTS returns 200
    sandbox.write_mock_tts_config(status_code=200)
    sandbox.send_notification("App", "Msg C", "C")
    time.sleep(1.0)
    
    # Playbacks: Msg A (miss, plays), Msg B (offline, fails/no play), Msg A (hit, plays), Msg C (miss, plays) = 3 total playbacks
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 3
    
    # Verifying Msg A played twice and Msg C once
    paths = [p["file_path"] for p in playbacks]
    md5_a = hashlib.md5("A".encode('utf-8')).hexdigest()
    md5_c = hashlib.md5("C".encode('utf-8')).hexdigest()
    
    assert paths.count(os.path.join(sandbox.tts_cache_dir, f"{md5_a}.wav")) == 2
    assert paths.count(os.path.join(sandbox.tts_cache_dir, f"{md5_c}.wav")) == 1

def test_t4_4_customtkinter_gui_configuration_lifecycle(sandbox):
    """T4.4: CustomTkinter GUI Configuration Lifecycle.
    GUI updates rules config -> SIGHUP -> Trigger notify -> plays sound."""
    sandbox.start_daemon()
    
    sound_path = os.path.join(sandbox.home, "game.wav")
    # Simulate GUI modifying config.json
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Lutris", "action": "sound", "sound_file": sound_path}
        ]
    })
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    # Trigger config reload in daemon
    sandbox.send_sighup()
    
    sandbox.send_notification("Lutris", "Launch", "Game started")
    time.sleep(1.0)
    
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 1
    assert sound_path in playbacks[0]["file_path"]

def test_t4_5_system_restart_cache_persistence(sandbox):
    """T4.5: System Restart Cache Persistence.
    Start Daemon, play X (cached). Restart Daemon. Play X again.
    Plays from cache with 0 new TTS requests. Total TTS requests = 1."""
    sandbox.start_daemon()
    sandbox.send_notification("App", "Persist", "Persistent Text")
    time.sleep(1.0)
    
    # Stop daemon
    sandbox.stop_daemon()
    time.sleep(0.5)
    
    # Restart daemon
    sandbox.start_daemon()
    sandbox.send_notification("App", "Persist", "Persistent Text")
    time.sleep(1.0)
    
    # Total TTS requests across the same sandbox home should be 1
    assert len(sandbox.read_tts_requests()) == 1
    
    # Total playbacks should be 2
    assert len(sandbox.read_playback_log()) == 2
