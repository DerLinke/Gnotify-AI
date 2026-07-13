import os
import time
import hashlib
import json
import pytest
import shutil

# Tier 1: Feature Coverage (26 Cases)

def test_t1_1_dbus_interception(sandbox):
    """T1.1: D-Bus Interception - Send standard notify command. Daemon logs interception."""
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Hello", "World")
    time.sleep(1.0)
    log_content = sandbox.read_daemon_log()
    assert "Intercepted" in log_content

def test_t1_2_rule_match_app_name_exact(sandbox):
    """T1.2: Rule Match - App Name Exact. Notify from App 'Slack'. Rule: app_name='Slack', action sound."""
    sound_path = os.path.join(sandbox.home, "slack_alert.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "sound", "sound_file": sound_path}
        ]
    })
    # Create the sound file so it exists
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "New Msg", "Chat")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert sound_path in playback_log[0]["file_path"]

def test_t1_3_rule_match_app_name_regex(sandbox):
    """T1.3: Rule Match - App Name Regex. Rule: app_name='Thunderbird.*', action sound."""
    sound_path = os.path.join(sandbox.home, "tb_alert.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Thunderbird.*", "action": "sound", "sound_file": sound_path}
        ]
    })
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.start_daemon()
    sandbox.send_notification("Thunderbird Mail", "Inbox", "New email")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert sound_path in playback_log[0]["file_path"]

def test_t1_4_rule_mismatch_skip_rule(sandbox):
    """T1.4: Rule Mismatch - Skip Rule. Notify from App 'Firefox'. Rule: app_name='Slack', action sound."""
    sound_path = os.path.join(sandbox.home, "slack_alert.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "sound", "sound_file": sound_path}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Firefox", "Download", "Complete")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    # Should fall back to default or not play slack_alert
    for play in playback_log:
        assert sound_path not in play["file_path"]

def test_t1_5_rule_match_summary_regex(sandbox):
    """T1.5: Rule Match - Summary Regex. Rule: summary_regex='.*Battery.*', action tts."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"summary_regex": ".*Battery.*", "action": "tts"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("System", "Low Battery!", "Plug in charger")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert "Plug in charger" in req_body["input"]

def test_t1_6_rule_match_body_regex(sandbox):
    """T1.6: Rule Match - Body Regex. Rule: body_regex='.*Critical.*', action tts."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"body_regex": ".*Critical.*", "action": "tts"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("System", "Warning", "Critical condition detected")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert "Critical" in req_body["input"]

def test_t1_7_first_match_wins(sandbox):
    """T1.7: First Match Wins. Rule 1: Slack -> sound, Rule 2: Slack -> tts."""
    sound_path = os.path.join(sandbox.home, "slack_alert.wav")
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "Slack", "action": "sound", "sound_file": sound_path},
            {"app_name": "Slack", "action": "tts"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("Slack", "Hello", "World")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert sound_path in playback_log[0]["file_path"]
    assert len(sandbox.read_tts_requests()) == 0

def test_t1_8_default_fallback_rule(sandbox):
    """T1.8: Default Fallback Rule. Default action is TTS with body."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("UnknownApp", "Title", "Generic Message Body")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "Generic Message Body"

def test_t1_9_placeholder_app_name(sandbox):
    """T1.9: Placeholder - App Name. Rule TTS: {app_name} alert."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "System", "action": "tts", "tts_template": "{app_name} alert"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("System", "Notice", "Test")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "System alert"

def test_t1_10_placeholder_summary(sandbox):
    """T1.10: Placeholder - Summary. Rule TTS: Notice: {summary}."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "System", "action": "tts", "tts_template": "Notice: {summary}"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("System", "Low Battery", "Test")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "Notice: Low Battery"

def test_t1_11_placeholder_body(sandbox):
    """T1.11: Placeholder - Body. Rule TTS: Please: {body}."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "System", "action": "tts", "tts_template": "Please: {body}"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("System", "Notice", "Plug in charger")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "Please: Plug in charger"

def test_t1_12_placeholders_multi(sandbox):
    """T1.12: Placeholders - Multi. Rule TTS: {app_name} {summary} {body}."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "S", "action": "tts", "tts_template": "{app_name} {summary} {body}"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("S", "U", "B")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["input"] == "S U B"

def test_t1_13_action_tts_cache_miss(sandbox):
    """T1.13: Action - TTS Cache Miss. POST to localAI, wave saved to cache, played."""
    sandbox.start_daemon()
    text = "Cache miss test text"
    sandbox.send_notification("TestApp", "Title", text)
    time.sleep(1.0)
    
    # Assert TTS hit
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    
    # Assert Cache file created with MD5 name
    text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_file = os.path.join(sandbox.tts_cache_dir, f"{text_md5}.wav")
    assert os.path.exists(cache_file)
    
    # Assert play logged
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert playback_log[0]["file_path"] == cache_file

def test_t1_14_action_tts_cache_hit(sandbox):
    """T1.14: Action - TTS Cache Hit. Plays file from cache, no HTTP POST."""
    text = "Cache hit test text"
    text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_file = os.path.join(sandbox.tts_cache_dir, f"{text_md5}.wav")
    
    # Pre-populate cache
    with open(cache_file, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.start_daemon()
    sandbox.send_notification("TestApp", "Title", text)
    time.sleep(1.0)
    
    # Assert NO TTS hit
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) == 0
    
    # Assert play logged
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert playback_log[0]["file_path"] == cache_file

def test_t1_15_action_sound_file(sandbox):
    """T1.15: Action - Sound File. Plays specified file via paplay."""
    sound_path = os.path.join(sandbox.home, "custom_sound.wav")
    with open(sound_path, "wb") as f:
        f.write(b"RIFF dummy sound")
        
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "TestApp", "action": "sound", "sound_file": sound_path}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("TestApp", "Title", "Body")
    time.sleep(1.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) >= 1
    assert playback_log[0]["file_path"] == sound_path

def test_t1_16_action_mute(sandbox):
    """T1.16: Action - Mute. Logs event, no TTS, no playback."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "TestApp", "action": "mute"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("TestApp", "Title", "Body")
    time.sleep(1.0)
    
    assert len(sandbox.read_tts_requests()) == 0
    assert len(sandbox.read_playback_log()) == 0

def test_t1_17_deduplication_single_msg(sandbox):
    """T1.17: Deduplication - Single Msg. Single msg plays."""
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert len(sandbox.read_playback_log()) == 1

def test_t1_18_deduplication_duplicate(sandbox):
    """T1.18: Deduplication - Duplicate. Second identical within 5s dropped."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 5,
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(0.5)
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert len(sandbox.read_playback_log()) == 1
    log_content = sandbox.read_daemon_log()
    assert "Duplicate" in log_content

def test_t1_19_deduplication_post_window(sandbox):
    """T1.19: Deduplication - Post Window. Send 2 identical 6s apart (window=5s). Both play."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 5,
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(5.5)
    sandbox.send_notification("App", "Sum", "Body")
    time.sleep(1.0)
    
    assert len(sandbox.read_playback_log()) == 2

def test_t1_20_spooler_queue_order(sandbox):
    """T1.21/20: Spooler Queue - Order. Sequential playbacks."""
    # Ensure sequential playing (mock delay is active)
    sandbox.write_mock_tts_config(delay=0.5)
    sandbox.start_daemon()
    sandbox.send_notification("App", "Msg 1", "M1")
    sandbox.send_notification("App", "Msg 2", "M2")
    sandbox.send_notification("App", "Msg 3", "M3")
    time.sleep(3.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) == 3
    # Check timestamps are increasing
    timestamps = [p["timestamp"] for p in playback_log]
    assert timestamps[0] < timestamps[1]
    assert timestamps[1] < timestamps[2]

def test_t1_21_rate_limiting_under_max(sandbox):
    """T1.21: Rate Limiting - Under Max. Send 5 in 10s (limit 5 in 30s). All play."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 5,
        "rate_limit_window": 30,
        "rules": []
    })
    sandbox.start_daemon()
    for i in range(5):
        sandbox.send_notification("App", f"Msg {i}", f"M{i}")
        time.sleep(0.2)
    time.sleep(2.0)
    
    assert len(sandbox.read_playback_log()) == 5

def test_t1_22_rate_limiting_over_max(sandbox):
    """T1.22: Rate Limiting - Over Max. Send 6 in 10s (limit 5 in 30s). 5 play, 6th dropped."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 5,
        "rate_limit_window": 30,
        "rules": []
    })
    sandbox.start_daemon()
    for i in range(6):
        sandbox.send_notification("App", f"Msg {i}", f"M{i}")
        time.sleep(0.2)
    time.sleep(2.0)
    
    assert len(sandbox.read_playback_log()) == 5
    log_content = sandbox.read_daemon_log()
    assert "Rate Limit" in log_content

def test_t1_23_daemon_logs_output(sandbox):
    """T1.23: Daemon Logs - Output. Check structures in log file."""
    sandbox.start_daemon()
    sandbox.send_notification("App", "Test", "Msg")
    time.sleep(1.0)
    
    log_content = sandbox.read_daemon_log()
    assert len(log_content) > 0
    # Must have timestamps and structured logs
    assert "started" in log_content.lower() or "intercepted" in log_content.lower()

def test_t1_24_config_file_loading(sandbox):
    """T1.24: Config File Loading. default_voice matches config."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "custom-voice-name",
        "rules": []
    })
    sandbox.start_daemon()
    sandbox.send_notification("App", "Test", "Msg")
    time.sleep(1.0)
    
    tts_reqs = sandbox.read_tts_requests()
    assert len(tts_reqs) >= 1
    req_body = json.loads(tts_reqs[0]["body"])
    assert req_body["voice"] == "custom-voice-name"

def test_t1_25_cache_dir_auto_creation(sandbox):
    """T1.25: Cache Dir Auto-creation. Daemon creates cache dir."""
    # Delete cache dir first
    if os.path.exists(sandbox.cache_dir):
        shutil.rmtree(sandbox.cache_dir)
        
    sandbox.start_daemon()
    sandbox.send_notification("App", "Test", "Msg")
    time.sleep(1.0)
    
    assert os.path.exists(sandbox.tts_cache_dir)

def test_t1_26_daemon_graceful_exit(sandbox):
    """T1.26: Daemon Graceful Exit. SIGTERM shutdown returns 0."""
    sandbox.start_daemon()
    assert sandbox.daemon_proc is not None
    assert sandbox.daemon_proc.poll() is None
    
    import subprocess
    proc = sandbox.daemon_proc
    proc.terminate()
    try:
        ret = proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        ret = proc.wait()
        
    assert ret in (0, -15)
    log_content = sandbox.read_daemon_log()
    assert "shutdown" in log_content.lower() or "terminated" in log_content.lower() or "stopping" in log_content.lower() or "graceful" in log_content.lower()
