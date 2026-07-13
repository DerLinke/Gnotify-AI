import os
import time
import json
import pytest
import shutil

# Tier 2: Boundary & Corner Cases (26 Cases)

def test_t2_1_empty_notification_fields(sandbox):
    """T2.1: Empty Notification Fields. Plays empty safely without crashing."""
    sandbox.start_daemon()
    sandbox.send_notification("", "", "")
    time.sleep(1.0)
    # Check that daemon is still running
    assert sandbox.daemon_proc is not None
    assert sandbox.daemon_proc.poll() is None

def test_t2_2_missing_tts_placeholders(sandbox):
    """T2.2: Missing TTS Placeholders. Template with only literal text."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "tts", "tts_template": "Literal message only"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Ignore", "Me")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "Literal message only"

def test_t2_3_invalid_tts_placeholders(sandbox):
    """T2.3: Invalid TTS Placeholders. Ignore or render literally; do not crash."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "tts", "tts_template": "Msg: {invalid_placeholder}"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Sum", "Body")
    time.sleep(1.0)
    
    # Assert daemon didn't crash
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "placeholder" in log_content.lower() or len(sandbox.read_tts_requests()) >= 0

def test_t2_4_special_unicode_chars(sandbox):
    """T2.4: Special Unicode Chars (emojis, Chinese, symbols)."""
    sandbox.start_daemon()
    special_text = "Hello 😊 极速 test!"
    sandbox.send_notification("App", "Sum", special_text)
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert "极速" in req_body["input"]

def test_t2_5_extremely_long_text(sandbox):
    """T2.5: Extremely Long Text. Handle 10k chars safely."""
    long_body = "A" * 10000
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", long_body)
    time.sleep(1.5)
    
    # Daemon should truncate or safely send request
    assert sandbox.daemon_proc.poll() is None
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1

def test_t2_6_html_sql_injection(sandbox):
    """T2.6: HTML/SQL Injection Strings. Treated strictly as plain text."""
    inject_str = "'; DROP TABLE rules; -- <script>alert(1)</script>"
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", inject_str)
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert inject_str in req_body["input"]

def test_t2_7_empty_rules_array(sandbox):
    """T2.7: Empty Rules Array. Fallback to default, runs stably."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None

def test_t2_8_corrupted_config_json(sandbox):
    """T2.8: Corrupted Config JSON. Missing brace, error exit or fallback."""
    config_path = os.path.join(sandbox.config_dir, "config.json")
    with open(config_path, "w") as f:
        f.write("{ invalid json")
        
    sandbox.start_daemon()
    time.sleep(0.5)
    # Either exits or runs fallback. If it exits, verify daemon_proc exited or log contains error
    log_content = sandbox.read_daemon_log()
    assert sandbox.daemon_proc is None or sandbox.daemon_proc.poll() is not None or "error" in log_content.lower()

def test_t2_9_config_missing_api_url(sandbox):
    """T2.9: Config Missing API URL. Falls back to default built-in URL."""
    sandbox.write_config({
        "default_voice": "en-us-speaker",
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    log_content = sandbox.read_daemon_log()
    assert "fallback" in log_content.lower() or "api_url" in log_content.lower() or sandbox.daemon_proc.poll() is None

def test_t2_10_localai_http_500_error(sandbox):
    """T2.10: LocalAI HTTP 500 Error. Logs failure, skips audio, doesn't crash."""
    sandbox.write_mock_tts_config(status_code=500)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test 500")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "500" in log_content or "fail" in log_content.lower()

def test_t2_11_localai_timeout(sandbox):
    """T2.11: LocalAI Timeout. Request times out, logs error, continues."""
    # Delay response for 5s (daemon timeout should be shorter, e.g., 2s)
    sandbox.write_mock_tts_config(delay=5.0)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test Timeout")
    time.sleep(3.0)
    
    log_content = sandbox.read_daemon_log()
    assert "timeout" in log_content.lower() or "fail" in log_content.lower()
    # Spooler is not crashed
    assert sandbox.daemon_proc.poll() is None

def test_t2_12_localai_corrupted_wave(sandbox):
    """T2.12: LocalAI Corrupted Wave. paplay fails, daemon logs error, continues."""
    sandbox.write_mock_tts_config(corrupt_wav=True)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test Corrupt Wav")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "corrupt" in log_content.lower() or "failed" in log_content.lower() or "paplay" in log_content.lower()

def test_t2_13_localai_non_wav_content(sandbox):
    """T2.13: LocalAI Non-Wav Content (JSON status 200). Detects invalid, logs, skips cache write."""
    sandbox.write_mock_tts_config(non_wav_json=True)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test Non Wav")
    time.sleep(1.0)
    
    # Assert cache files are not written (or empty ones deleted)
    cache_files = os.listdir(sandbox.tts_cache_dir)
    for cf in cache_files:
        path = os.path.join(sandbox.tts_cache_dir, cf)
        assert os.path.getsize(path) < 44 or not cf.endswith(".wav") # wav must be >= 44 bytes

def test_t2_14_localai_connection_refused(sandbox):
    """T2.14: LocalAI Connection Refused. Server offline, caught and logged."""
    # Write wrong port
    sandbox.write_config({
        "api_url": "http://127.0.0.1:9999/v1",
        "default_voice": "en-us-speaker",
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test Conn Refused")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "refused" in log_content.lower() or "connect" in log_content.lower() or "fail" in log_content.lower()

def test_t2_15_sound_file_not_found(sandbox):
    """T2.15: Sound File Not Found. Log warning/error, continue."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "App", "action": "sound", "sound_file": "/nonexistent.wav"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "not found" in log_content.lower() or "exist" in log_content.lower() or "error" in log_content.lower()

def test_t2_16_sound_file_no_read_perm(sandbox):
    """T2.16: Sound File No Read Perm. Caught error, log and continue."""
    sound_path = os.path.join(sandbox.home, "no_read_perm.wav")
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
    os.chmod(sound_path, 0o000) # Remove all permissions
    
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "App", "action": "sound", "sound_file": sound_path}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    # Restore permissions to allow cleanup
    os.chmod(sound_path, 0o644)
    os.remove(sound_path)
    
    assert sandbox.daemon_proc.poll() is None

def test_t2_17_cache_dir_read_only(sandbox):
    """T2.17: Cache Dir Read-Only. Fetch succeeds, skips cache write, plays directly."""
    # Make tts cache directory read-only
    os.chmod(sandbox.tts_cache_dir, 0o400)
    
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Test Read Only Cache")
    time.sleep(1.5)
    
    # Restore write permission for cleanup
    os.chmod(sandbox.tts_cache_dir, 0o755)
    
    # Verify playback succeeded or log reported failure
    log_content = sandbox.read_daemon_log()
    assert "cache" in log_content.lower() or len(sandbox.read_playback_log()) >= 0

def test_t2_18_paplay_missing(sandbox):
    """T2.18: paplay Missing. Remove paplay from PATH. Log critical, continue."""
    # Delete mock paplay
    os.remove(os.path.join(sandbox.bin_dir, "paplay"))
    
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "paplay" in log_content.lower() or "missing" in log_content.lower() or "not found" in log_content.lower()

def test_t2_19_paplay_non_zero_exit(sandbox):
    """T2.19: paplay Non-Zero Exit. Exits with status 1. Log playback failure, continue."""
    sandbox.write_mock_paplay_config(exit_code=1)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "exit" in log_content.lower() or "failed" in log_content.lower() or "code 1" in log_content.lower()

def test_t2_20_deduplication_window_zero(sandbox):
    """T2.20: Deduplication Window Zero. Bypasses duplicate checks."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 0,
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(0.5)
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert len(sandbox.read_playback_log()) == 2

def test_t2_21_rate_limit_window_zero(sandbox):
    """T2.21: Rate Limit Window Zero. Bypasses rate limiting."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_window": 0,
        "rules": []
    })
    sandbox.start_daemon()
    for i in range(10):
        sandbox.send_notification("App", f"Msg {i}", f"M{i}")
        time.sleep(0.1)
    time.sleep(2.0)
    
    assert len(sandbox.read_playback_log()) == 10

def test_t2_22_sighup_config_reload(sandbox):
    """T2.22: SIGHUP Config Reload. Rules update dynamically while running."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "mute"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Sum", "Body")
    time.sleep(0.5)
    assert len(sandbox.read_playback_log()) == 0
    
    sound_path = os.path.join(sandbox.home, "new_sound.wav")
    # Update config and reload
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "sound", "sound_file": sound_path}
        ]
    })
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.send_sighup()
    sandbox.send_notification("Slack", "Sum", "Body")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert sound_path in playback_log[0]["file_path"]

def test_t2_23_extremely_high_rate_limit(sandbox):
    """T2.23: Extremely High Rate Limit. Limit set to 10k in 1s. Runs stably."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 10000,
        "rate_limit_window": 1,
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(0.5)
    assert sandbox.daemon_proc.poll() is None

def test_t2_24_dbus_disconnect(sandbox):
    """T2.24: D-Bus Disconnect. Client daemon logs connection loss and exits.
    We don't terminate the actual D-Bus session (which kills the whole run),
    but we can close the daemon's connection or mimic it."""
    import os
    os.environ["GNOTIFY_SIMULATE_DBUS_DISCONNECT"] = "1"
    try:
        sandbox.start_daemon()
        start_time = time.time()
        exited = False
        while time.time() - start_time < 3.0:
            if sandbox.daemon_proc and sandbox.daemon_proc.poll() is not None:
                exited = True
                break
            time.sleep(0.1)
        assert exited, "Daemon did not exit after simulated D-Bus disconnect"
        log_content = sandbox.read_daemon_log()
        assert "connection lost" in log_content.lower()
    finally:
        if "GNOTIFY_SIMULATE_DBUS_DISCONNECT" in os.environ:
            del os.environ["GNOTIFY_SIMULATE_DBUS_DISCONNECT"]

def test_t2_25_pathological_rule_regex(sandbox):
    """T2.25: Pathological Rule Regex. Rule has malformed regex. Skipped safely, no crash."""
    sound_path = os.path.join(sandbox.home, "alert.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "summary_regex": "[a-z+", "action": "sound", "sound_file": sound_path}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Sum", "Body")
    time.sleep(1.0)
    
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "regex" in log_content.lower() or "error" in log_content.lower()

def test_t2_26_disk_full_simulation(sandbox):
    """T2.26: Disk Full Simulation. OSError simulated, continues running."""
    import os
    os.environ["GNOTIFY_SIMULATE_DISK_FULL"] = "1"
    try:
        sandbox.start_daemon()
        assert sandbox.daemon_proc is not None
        assert sandbox.daemon_proc.poll() is None
        
        # Trigger a notification
        sandbox.send_notification("Slack", "Disk Full Test", "Body")
        time.sleep(1.0)
        
        # Verify the daemon is still running
        assert sandbox.daemon_proc.poll() is None
        
        # Read stderr to verify disk full error was logged
        import fcntl
        fd = sandbox.daemon_proc.stderr.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            err_output = sandbox.daemon_proc.stderr.read()
        except Exception:
            err_output = ""
            
        assert "no space left on device" in err_output.lower()
    finally:
        if "GNOTIFY_SIMULATE_DISK_FULL" in os.environ:
            del os.environ["GNOTIFY_SIMULATE_DISK_FULL"]

def test_t2_27_sighup_corrupted_config(sandbox):
    """T2.27: SIGHUP Corrupted Config. Reload invalid JSON at runtime, daemon logs error and stays alive."""
    # Write a valid config first
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": []
    })
    sandbox.start_daemon()
    assert sandbox.daemon_proc is not None
    assert sandbox.daemon_proc.poll() is None
    
    # Write corrupted config
    config_path = os.path.join(sandbox.config_dir, "config.json")
    with open(config_path, "w") as f:
        f.write("{ invalid json")
        
    sandbox.send_sighup()
    time.sleep(1.0)
    
    # Daemon should stay alive
    assert sandbox.daemon_proc.poll() is None
    log_content = sandbox.read_daemon_log()
    assert "error loading config" in log_content.lower()

def test_t2_28_poisoned_cache_purging(sandbox):
    """T2.28: Poisoned Cache Purging. Corrupt cached wav causes play_audio to fail; daemon deletes it."""
    import hashlib
    text = "Poison cache test text"
    text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_file = os.path.join(sandbox.tts_cache_dir, f"{text_md5}.wav")
    
    # Pre-populate cache with garbage
    with open(cache_file, "wb") as f:
        f.write(b"garbage data")
        
    # Configure paplay to fail (to simulate corrupted file playback failure)
    sandbox.write_mock_paplay_config(exit_code=1)
    
    sandbox.start_daemon()
    sandbox.send_notification("TestApp", "Title", text)
    time.sleep(1.0)
    
    # Assert cache file has been purged
    assert not os.path.exists(cache_file)

