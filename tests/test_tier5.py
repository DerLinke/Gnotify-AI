import os
import sys
import time
import json
import hashlib
import pytest
from unittest.mock import patch, MagicMock

# Define Tier 5: Adversarial Coverage Hardening (5 Cases)

# Test 1: Invalid rules type in configuration
def test_t5_1_invalid_config_rules_type(sandbox):
    """T5.1: Invalid Config Rules Type.
    Write rules as an integer (invalid type). Start daemon and send notification.
    The daemon should log the error/TypeError in DBus callback, but remain running."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": 42  # Invalid type: should be a list
    })
    sandbox.start_daemon()
    assert sandbox.daemon_proc is not None
    assert sandbox.daemon_proc.poll() is None

    # Send a notification. The DBus filter callback will execute and raise TypeError inside msg_filter.
    # We verify that this callback exception is caught or handled without crashing the daemon.
    sandbox.send_notification("Slack", "Subject", "Body")
    time.sleep(1.0)

    # Verify daemon did not crash
    assert sandbox.daemon_proc.poll() is None


# Test 2: Empty/Zero-byte TTS audio response payload
def test_t5_2_empty_tts_response(sandbox):
    """T5.2: Empty TTS Response.
    Configure mock TTS to return an empty body. Verify cache file is purged after playback fails."""
    sandbox.write_mock_tts_config(empty_body=True)
    sandbox.start_daemon()

    text = "Empty response text"
    sandbox.send_notification("TestApp", "Title", text)
    time.sleep(1.5)

    # Assert cache file does not exist (it should be deleted because play_audio failed on an empty WAV)
    text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
    cache_file = os.path.join(sandbox.tts_cache_dir, f"{text_md5}.wav")
    assert not os.path.exists(cache_file)

    # Playback log should be empty (since playing empty WAV failed)
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 0

    # Verify daemon log mentions purging the corrupt file
    log_content = sandbox.read_daemon_log()
    assert "playback of newly cached file failed" in log_content.lower() or "purging" in log_content.lower()


# Test 3: Intermittent failures of TTS server
def test_t5_3_tts_intermittent_failures(sandbox):
    """T5.3: Intermittent TTS Server Failures.
    1. Online: Notification A plays.
    2. Offline (503): Notification B fails.
    3. Online: Notification C plays.
    Verify spooler remains active and processes all items."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "deduplication_window": 1,
        "rules": []
    })
    sandbox.start_daemon()

    # 1. Notification A (succeeds)
    sandbox.send_notification("App", "Msg A", "A")
    time.sleep(1.0)

    # 2. Set mock TTS to fail (HTTP 500)
    sandbox.write_mock_tts_config(status_code=500)
    sandbox.send_notification("App", "Msg B", "B")
    time.sleep(1.0)

    # 3. Set mock TTS to succeed (HTTP 200)
    sandbox.write_mock_tts_config(status_code=200)
    sandbox.send_notification("App", "Msg C", "C")
    time.sleep(1.0)

    # Verify playbacks (A and C should be played, B should not)
    playbacks = sandbox.read_playback_log()
    assert len(playbacks) == 2

    # Verify B failed and was logged
    log_content = sandbox.read_daemon_log()
    assert "status 500" in log_content

    # Ensure daemon is still running
    assert sandbox.daemon_proc.poll() is None


# Test 4: Unknown action and missing properties in rules
def test_t5_4_unknown_rule_action(sandbox):
    """T5.4: Unknown rule action or missing action properties.
    Verify daemon handles unknown actions or invalid sound rules without crashing."""
    sandbox.write_config({
        "api_url": f"http://127.0.0.1:{sandbox.tts_port}/v1",
        "default_voice": "en-us-speaker",
        "rules": [
            {"app_name": "App1", "action": "unknown_action"},  # Unknown action
            {"app_name": "App2", "action": "sound", "sound_file": None}  # Missing sound_file
        ]
    })
    sandbox.start_daemon()

    # Send Notification to trigger App1
    sandbox.send_notification("App1", "Title", "Body")
    time.sleep(1.0)

    # Send Notification to trigger App2
    sandbox.send_notification("App2", "Title", "Body")
    time.sleep(1.0)

    # Verify daemon did not crash
    assert sandbox.daemon_proc.poll() is None

    # Verify warning/error logs
    log_content = sandbox.read_daemon_log()
    assert "sound file not found or not readable" in log_content.lower()


# Test 5: GUI Config operations white-box headless tests
def test_t5_5_gui_config_operations(sandbox):
    """T5.5: Headless white-box tests of GnotifyGUI config management logic."""
    # Mock customtkinter and tkinter elements to avoid X11 connection errors
    mock_ctk = MagicMock()
    
    class DummyCTk:
        def __init__(self, *args, **kwargs): pass
        def title(self, *args): pass
        def geometry(self, *args): pass
        def grid_columnconfigure(self, *args, **kwargs): pass
        def grid_rowconfigure(self, *args, **kwargs): pass
        def after(self, *args, **kwargs): pass
        def protocol(self, *args, **kwargs): pass
        def destroy(self): pass

    mock_ctk.CTk = DummyCTk
    mock_ctk.CTkFrame = lambda *a, **kw: MagicMock()
    mock_ctk.CTkLabel = lambda *a, **kw: MagicMock()
    mock_ctk.CTkButton = lambda *a, **kw: MagicMock()
    mock_ctk.CTkTabview = lambda *a, **kw: MagicMock()
    mock_ctk.CTkTextbox = lambda *a, **kw: MagicMock()
    mock_ctk.CTkCheckBox = lambda *a, **kw: MagicMock()
    mock_ctk.CTkEntry = lambda *a, **kw: MagicMock()
    mock_ctk.CTkComboBox = lambda *a, **kw: MagicMock()
    mock_ctk.CTkSwitch = lambda *a, **kw: MagicMock()
    mock_ctk.CTkFont = lambda *a, **kw: MagicMock()
    mock_ctk.BooleanVar = MagicMock
    mock_ctk.StringVar = MagicMock

    mock_tk = MagicMock()
    mock_tk.messagebox = MagicMock()
    mock_tk.messagebox.askyesno = MagicMock(return_value=True)

    try:
        with patch.dict(sys.modules, {
            'customtkinter': mock_ctk,
            'tkinter': mock_tk,
            'tkinter.messagebox': mock_tk.messagebox,
            'tkinter.filedialog': mock_tk.filedialog
        }):
            # Mock LogTailer and GnotifyGUI.refresh_systemd_status to prevent background tasks
            class MockLogTailer:
                def __init__(self, *args, **kwargs): pass
                def start(self): pass
                def stop(self): pass

            with patch('gnotify_ai_gui.LogTailer', MockLogTailer), \
                 patch('gnotify_ai_gui.GnotifyGUI.refresh_systemd_status', lambda self: None), \
                 patch('os.path.expanduser', side_effect=lambda p: p.replace("~", sandbox.home)):
                 
                from gnotify_ai_gui import GnotifyGUI

                # Instantiate GnotifyGUI. Expanduser patch redirects config/logs to sandbox home.
                gui = GnotifyGUI()

                # Ensure default config is loaded correctly
                assert gui.config_data["default_voice"] == "en-us-speaker"

                # 1. Test add_rule_callback
                new_rule = {"app_name": "Slack", "action": "tts", "voice": "en-us-female"}
                gui.add_rule_callback(new_rule)
                assert len(gui.config_data["rules"]) == 1
                assert gui.config_data["rules"][0]["app_name"] == "Slack"

                # 2. Test edit_rule_callback
                updated_rule = {"app_name": "Slack", "action": "mute"}
                gui.edit_rule_callback(0, updated_rule)
                assert gui.config_data["rules"][0]["action"] == "mute"

                # 3. Test move rules up/down
                gui.add_rule_callback({"app_name": "AppB", "action": "tts"})
                assert len(gui.config_data["rules"]) == 2
                # Swapping rules
                gui.move_rule_down(0)
                assert gui.config_data["rules"][0]["app_name"] == "AppB"
                gui.move_rule_up(1)
                assert gui.config_data["rules"][0]["app_name"] == "Slack"

                # 4. Test delete_rule
                gui.delete_rule(0)
                assert len(gui.config_data["rules"]) == 1
                assert gui.config_data["rules"][0]["app_name"] == "AppB"

                # 5. Test save_general_settings validation and persistence
                gui.rl_max_ent.get = MagicMock(return_value="15")
                gui.rl_win_ent.get = MagicMock(return_value="45")
                gui.dedup_ent.get = MagicMock(return_value="10")
                gui.api_url_ent.get = MagicMock(return_value="http://localhost:8089/v1")
                gui.voice_ent.get = MagicMock(return_value="en-us-male")
                gui.debug_var.get = MagicMock(return_value=True)

                gui.save_general_settings()

                # Load the config file directly from sandbox to verify it saved
                config_file_path = os.path.join(sandbox.config_dir, "config.json")
                with open(config_file_path, "r") as f:
                    saved_config = json.load(f)

                assert saved_config["rate_limit_max"] == 15
                assert saved_config["rate_limit_window"] == 45
                assert saved_config["deduplication_window"] == 10
                assert saved_config["default_voice"] == "en-us-male"
                assert saved_config["debug"] is True
    finally:
        # Clean up cached modules to avoid side-effects on other tests
        sys.modules.pop('gnotify_ai_gui', None)
