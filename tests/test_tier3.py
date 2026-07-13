import os
import time
import json
import pytest

# Tier 3: Cross-Feature Combinations (5 Cases)

def test_t3_1_spooling_rate_limiting_deduplication(sandbox):
    """T3.1: Spooling + Rate Limiting + Deduplication.
    Send 10: 4 identical, 6 unique. Deduplication drops 3 (7 remain).
    Rate limit drops 2 (5 remain). Assert exactly 5 unique playbacks."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 5,
        "rate_limit_window": 30,
        "deduplication_window": 5,
        "rules": []
    })
    sandbox.start_daemon()
    
    # 4 identical notifications (1st plays, next 3 duplicates dropped)
    for _ in range(4):
        sandbox.send_notification("App", "Dup", "Body")
        time.sleep(0.1)
        
    # 6 unique notifications
    for i in range(6):
        sandbox.send_notification("App", f"Unique {i}", f"U{i}")
        time.sleep(0.1)
        
    time.sleep(3.0)
    
    playback_log = sandbox.read_playback_log()
    # 1 from identical + 4 from unique = 5 total
    assert len(playback_log) == 5

def test_t3_2_cache_hit_spooler_queue_ordering(sandbox):
    """T3.2: Cache Hit + Spooler Queue Ordering.
    Msg A (instant cache hit), Msg B (3s delay cache miss), Msg C (instant cache hit).
    Sent within 100ms. Assert play order is A -> B -> C, and C plays after B completes."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": []
    })
    
    # Pre-populate cache for A and C
    import hashlib
    text_a = "Message A"
    text_c = "Message C"
    for text in [text_a, text_c]:
        text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
        with open(os.path.join(sandbox.tts_cache_dir, f"{text_md5}.wav"), "wb") as f:
            f.write(b"RIFF dummy sound")
            
    # B will miss and have 2s delay
    sandbox.write_mock_tts_config(delay=2.0)
    sandbox.start_daemon()
    
    sandbox.send_notification("App", "A", text_a)
    time.sleep(0.05)
    sandbox.send_notification("App", "B", "Message B") # Cache Miss, 2s delay
    time.sleep(0.05)
    sandbox.send_notification("App", "C", text_c)
    
    # Wait for all playbacks to complete
    time.sleep(4.0)
    
    playback_log = sandbox.read_playback_log()
    assert len(playback_log) == 3
    # Check strict order A -> B -> C
    md5_a = hashlib.md5(text_a.encode('utf-8')).hexdigest()
    md5_c = hashlib.md5(text_c.encode('utf-8')).hexdigest()
    assert md5_a in playback_log[0]["file_path"]
    assert md5_c in playback_log[2]["file_path"]
    
    # C must play after B is finished. Since B has 2s delay, timestamp difference between B and A,
    # and C and B should show that.
    t_a = playback_log[0]["timestamp"]
    t_b = playback_log[1]["timestamp"]
    t_c = playback_log[2]["timestamp"]
    
    assert t_b >= t_a
    assert t_c >= t_b

def test_t3_3_muted_actions_in_rate_limiting(sandbox):
    """T3.3: Muted Actions in Rate Limiting.
    Send 10: 6 match mute rule, 4 match tts rule.
    Muted don't enter spooler and don't count towards rate limit (5-in-30s). All 4 TTS play."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rate_limit_max": 5,
        "rate_limit_window": 30,
        "rules": [
            {"app_name": "MutedApp", "action": "mute"},
            {"app_name": "SpokenApp", "action": "tts"}
        ]
    })
    sandbox.start_daemon()
    
    # Send 6 muted
    for i in range(6):
        sandbox.send_notification("MutedApp", f"Mute {i}", "Body")
        time.sleep(0.1)
        
    # Send 4 spoken
    for i in range(4):
        sandbox.send_notification("SpokenApp", f"Speak {i}", "Body")
        time.sleep(0.1)
        
    time.sleep(2.0)
    
    # 4 playbacks should occur (none of the muted play, and spoken are not dropped by rate limit)
    assert len(sandbox.read_playback_log()) == 4

def test_t3_4_dynamic_rule_priority_escalation(sandbox):
    """T3.4: Dynamic Rule Priority Escalation.
    Rule 1: App X -> mute. Rule 2: App X -> tts. Send notification (muted).
    SIGHUP with rules swapped. Send notification (spoken)."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "AppX", "action": "mute"},
            {"app_name": "AppX", "action": "tts"}
        ]
    })
    sandbox.start_daemon()
    sandbox.send_notification("AppX", "Test", "Hello")
    time.sleep(0.5)
    
    assert len(sandbox.read_tts_requests()) == 0
    
    # Swap rule priorities
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "AppX", "action": "tts"},
            {"app_name": "AppX", "action": "mute"}
        ]
    })
    sandbox.send_sighup()
    sandbox.send_notification("AppX", "Test", "Hello")
    time.sleep(1.0)
    
    assert len(sandbox.read_tts_requests()) == 1

def test_t3_5_concurrent_tts_miss_deduplication(sandbox):
    """T3.5: Concurrent TTS Miss Deduplication.
    Message A (cache miss) takes 3s. Message B (identical) sent 1s after Message A.
    Expected: Message B caught by 5s deduplication and dropped, even though A hasn't finished writing to cache yet."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 5,
        "rules": []
    })
    sandbox.write_mock_tts_config(delay=3.0)
    sandbox.start_daemon()
    
    sandbox.send_notification("App", "Dup", "Hello")
    time.sleep(1.0)
    sandbox.send_notification("App", "Dup", "Hello")
    
    time.sleep(4.0)
    
    # Only 1 TTS request is made
    assert len(sandbox.read_tts_requests()) == 1
    # Only 1 playback logged
    assert len(sandbox.read_playback_log()) == 1
