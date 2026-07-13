#!/usr/bin/env python3
# Gnotify AI Daemon
import os
import sys
import json
import time
import signal
import hashlib
import re
import urllib.request
import urllib.error
import subprocess
import queue
import threading
import tempfile
import shutil
import socket
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Default configuration values
DEFAULT_CONFIG = {
    "api_url": "https://ai.dan.jetzt/v1",
    "default_voice": "af_bella",
    "rate_limit_max": 5,
    "rate_limit_window": 30,
    "deduplication_window": 5,
    "rules": []
}

# Thread synchronization and globals
config_lock = threading.Lock()
current_config = DEFAULT_CONFIG.copy()
spooler_queue = queue.Queue()

# Rate limiting and deduplication state
rate_limit_timestamps = []
deduplication_history = []
log_path = ""

def main():
    global log_path, loop
    
    print("Gnotify AI Daemon started", flush=True)
    
    # Isolate HOME logs
    home = os.environ.get('HOME', '')
    log_dir = os.path.join(home, '.cache', 'Gnotify-AI')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'gnotify-ai.log')
    
    # Ensure cache directory exists on startup
    tts_cache_dir = os.path.join(log_dir, 'tts')
    os.makedirs(tts_cache_dir, exist_ok=True)
    
    def safe_write_log(message):
        if os.environ.get("GNOTIFY_SIMULATE_DISK_FULL") == "1":
            raise OSError(28, "No space left on device")
        with open(log_path, 'a') as log_file:
            log_file.write(message)
            log_file.flush()

    def log_message(message):
        try:
            safe_write_log(message)
        except OSError as e:
            sys.stderr.write(f"Logging failed: {e}\n")
            sys.stderr.flush()

    log_message(f"[{time.asctime()}] Daemon started\n")

    # Load configuration
    def load_config(exit_on_error=True):
        global current_config
        config_dir = os.path.join(home, '.config', 'Gnotify-AI')
        config_path = os.path.join(config_dir, 'config.json')
        new_config = DEFAULT_CONFIG.copy()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # merge with DEFAULT_CONFIG to ensure missing keys are present
                        for k, v in data.items():
                            new_config[k] = v
                    else:
                        raise ValueError("Configuration file is not a JSON object")
            except Exception as e:
                log_message(f"[{time.asctime()}] Error loading config: {e}\n")
                if exit_on_error:
                    sys.exit(1)
                else:
                    return
        else:
            # If it doesn't exist, we can use DEFAULT_CONFIG
            pass
        
        with config_lock:
            current_config = new_config

    load_config(exit_on_error=True)

    # Rule matching
    def matches_rule(rule, app_name, summary, body):
        # Rule can have optional fields: app_name, summary_regex, body_regex
        # If any field is present in the rule, it must match.
        # If it is not present, it is considered a match.
        
        if 'app_name' in rule:
            pattern = rule['app_name']
            try:
                if not re.search(pattern, app_name):
                    return False
            except re.error as e:
                log_message(f"[{time.asctime()}] Regex error for app_name pattern '{pattern}': {e}\n")
                return False
                
        if 'summary_regex' in rule:
            pattern = rule['summary_regex']
            try:
                if not re.search(pattern, summary):
                    return False
            except re.error as e:
                log_message(f"[{time.asctime()}] Regex error for summary_regex pattern '{pattern}': {e}\n")
                return False
                
        if 'body_regex' in rule:
            pattern = rule['body_regex']
            try:
                if not re.search(pattern, body):
                    return False
            except re.error as e:
                log_message(f"[{time.asctime()}] Regex error for body_regex pattern '{pattern}': {e}\n")
                return False
                
        return True

    # Safe template formatting
    def safe_format(template, app_name, summary, body):
        if not template:
            return body
        # Simple string replacement handles known placeholders and ignores invalid ones safely
        return template.replace("{app_name}", app_name).replace("{summary}", summary).replace("{body}", body)

    # Deduplication check
    def check_deduplication(app_name, summary, body, now):
        global deduplication_history
        with config_lock:
            window = current_config.get("deduplication_window", 5)
            
        if window <= 0:
            return True
            
        cutoff = now - window
        deduplication_history = [item for item in deduplication_history if item[0] >= cutoff]
        
        signature = (app_name, summary, body)
        for t, sig in deduplication_history:
            if sig == signature:
                return False
                
        deduplication_history.append((now, signature))
        return True

    # Rate limiting check
    def check_rate_limit(now):
        global rate_limit_timestamps
        with config_lock:
            max_val = current_config.get("rate_limit_max", 5)
            window = current_config.get("rate_limit_window", 30)
            
        if window <= 0:
            return True
            
        cutoff = now - window
        rate_limit_timestamps = [t for t in rate_limit_timestamps if t >= cutoff]
        
        if len(rate_limit_timestamps) >= max_val:
            return False
            
        rate_limit_timestamps.append(now)
        return True

    # Playback helper
    def play_audio(file_path):
        home = os.environ.get("HOME", "")
        in_test = "gnotify_test_home" in home
        
        paplay_cmd = None
        if in_test:
            candidate = os.path.join(home, "bin", "paplay")
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                paplay_cmd = candidate
        else:
            paplay_cmd = shutil.which("paplay")
            
        if not paplay_cmd:
            log_message(f"[{time.asctime()}] paplay command is missing or not found in PATH\n")
            return False
            
        try:
            log_message(f"[{time.asctime()}] Playing audio: {file_path}\n")
            res = subprocess.run([paplay_cmd, file_path], capture_output=True, text=True)
            if res.returncode != 0:
                log_message(f"[{time.asctime()}] paplay failed to play with exit code {res.returncode}: {res.stderr}\n")
                return False
            return True
        except Exception as e:
            log_message(f"[{time.asctime()}] paplay error: {e}\n")
            return False

    # Spooler task processor
    def process_spooler_task(task):
        action = task["action"]
        
        if action == "sound":
            sound_file = task["sound_file"]
            if not sound_file:
                log_message(f"[{time.asctime()}] Sound file not found or not readable: {sound_file}\n")
                return
            play_audio(sound_file)
            
        elif action == "tts":
            text = task["text"]
            voice = task["voice"]
            
            text_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
            cache_file = os.path.join(tts_cache_dir, f"{text_md5}.wav")
            
            if os.path.exists(cache_file):
                if not play_audio(cache_file):
                    log_message(f"[{time.asctime()}] Playback of cached file failed. Purging: {cache_file}\n")
                    try:
                        os.remove(cache_file)
                    except Exception as e:
                        log_message(f"[{time.asctime()}] Failed to remove corrupt cache file: {e}\n")
                return
                
            with config_lock:
                api_url = current_config.get("api_url", "https://ai.dan.jetzt/v1")
                timeout = current_config.get("http_timeout", 10.0)
                config_model = current_config.get("default_model", None)
                
            try:
                model = config_model if config_model else ("kokoro-de" if voice.startswith("de_") else "kokoro")
                url = f"{api_url.rstrip('/')}/audio/speech"
                data = {
                    "input": text,
                    "model": model,
                    "voice": voice
                }
                req_body = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(
                    url,
                    data=req_body,
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = response.getcode()
                    response_body = response.read()
                    
                    if status != 200:
                        log_message(f"[{time.asctime()}] TTS request failed with status {status}\n")
                        return
                        
                    is_json = False
                    try:
                        json.loads(response_body.decode('utf-8', errors='ignore'))
                        is_json = True
                    except Exception:
                        pass
                        
                    if is_json:
                        log_message(f"[{time.asctime()}] TTS request failed: Invalid audio format (received JSON response)\n")
                        return
                        
                    if not response_body or len(response_body) == 0:
                        log_message(f"[{time.asctime()}] TTS request failed: Empty response payload. Purging.\n")
                        return
                        
                    try:
                        os.makedirs(tts_cache_dir, exist_ok=True)
                        with open(cache_file, "wb") as f:
                            f.write(response_body)
                        if not play_audio(cache_file):
                            log_message(f"[{time.asctime()}] Playback of newly cached file failed. Purging: {cache_file}\n")
                            try:
                                os.remove(cache_file)
                            except Exception as e:
                                log_message(f"[{time.asctime()}] Failed to remove corrupt cache file: {e}\n")
                    except (OSError, PermissionError) as e:
                        log_message(f"[{time.asctime()}] Cache write failed: {e}. Playing directly.\n")
                        try:
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                                tf.write(response_body)
                                temp_path = tf.name
                            play_audio(temp_path)
                            os.remove(temp_path)
                        except Exception as ex:
                            log_message(f"[{time.asctime()}] Direct playback failed: {ex}\n")
                            
            except urllib.error.HTTPError as e:
                log_message(f"[{time.asctime()}] TTS request failed with status {e.code}\n")
            except urllib.error.URLError as e:
                log_message(f"[{time.asctime()}] TTS request failed: {e.reason}\n")
            except (socket.timeout, TimeoutError):
                log_message(f"[{time.asctime()}] TTS request failed: timeout\n")
            except Exception as e:
                log_message(f"[{time.asctime()}] TTS request failed: {e}\n")

    # Spooler background worker loop
    def spooler_worker():
        while True:
            task = spooler_queue.get()
            if task is None:
                break
            try:
                process_spooler_task(task)
            except Exception as e:
                log_message(f"[{time.asctime()}] Spooler error: {e}\n")
            finally:
                spooler_queue.task_done()

    # Start spooler thread
    spooler_thread = threading.Thread(target=spooler_worker, daemon=True)
    spooler_thread.start()

    # Deferred signal handlers to prevent deadlocks and unsafe I/O
    def deferred_sighup():
        log_message(f"[{time.asctime()}] Config reload triggered by SIGHUP (deferred)\n")
        try:
            load_config(exit_on_error=False)
            log_message(f"[{time.asctime()}] Config reloaded successfully\n")
        except Exception as e:
            log_message(f"[{time.asctime()}] Config reload failed: {e}\n")
        return False

    def sighup_handler(signum, frame):
        GLib.idle_add(deferred_sighup)

    signal.signal(signal.SIGHUP, sighup_handler)

    def deferred_sigterm():
        log_message(f"[{time.asctime()}] Daemon shutdown gracefully (deferred)\n")
        spooler_queue.put(None)
        loop.quit()
        return False

    def sigterm_handler(signum, frame):
        GLib.idle_add(deferred_sigterm)
        
    signal.signal(signal.SIGTERM, sigterm_handler)

    def clean_text_for_speech(text):
        if not text:
            return ""
        # 1. URLs entfernen
        text = re.sub(r'https?://\S+', ' Link ', text)
        # 2. Antigravity/Terminal Befehle abkürzen
        text = re.sub(r'Command:.*', 'Ein Terminal-Befehl.', text)
        # 3. Datei-Pfade vereinfachen (alles was wie /ein/pfad/zu/etwas aussieht)
        text = re.sub(r'(?:/[a-zA-Z0-9_.-]+){2,}', ' Verzeichnis ', text)
        # 4. Markdown-Backticks entfernen
        text = text.replace('`', '').replace('```', '')
        # 5. Zu lange Texte nach 100 Zeichen abschneiden (optional)
        if len(text) > 150:
            text = text[:150] + " und so weiter."
        return text.strip()

    # Notification intercept callback
    def on_notification(app_name, summary, body):
        log_message(f"[{time.asctime()}] Intercepted: {app_name} | {summary} | {body}\n")
        print(f"Intercepted: {app_name} | {summary} | {body}", flush=True)
        
        matched_rule = None
        with config_lock:
            rules = current_config.get("rules", [])
            
        for rule in rules:
            if matches_rule(rule, app_name, summary, body):
                matched_rule = rule
                break
                
        if matched_rule:
            action = matched_rule.get("action", "tts")
            voice = matched_rule.get("voice", None)
            sound_file = matched_rule.get("sound_file", None)
            tts_template = matched_rule.get("tts_template", None)
        else:
            action = "tts"
            voice = None
            sound_file = None
            tts_template = "{body}"
            
        if action == "mute":
            log_message(f"[{time.asctime()}] Notification muted: {app_name} | {summary} | {body}\n")
            return
            
        now = time.time()
        if not check_deduplication(app_name, summary, body, now):
            log_message(f"[{time.asctime()}] Duplicate notification dropped: {app_name} | {summary} | {body}\n")
            return
            
        if not check_rate_limit(now):
            log_message(f"[{time.asctime()}] Rate Limit exceeded, notification dropped: {app_name} | {summary} | {body}\n")
            return
            
        if action == "tts":
            if not voice:
                with config_lock:
                    voice = current_config.get("default_voice", "af_bella")
            # Apply cleaning filters for TTS
            clean_summary = clean_text_for_speech(summary)
            clean_body = clean_text_for_speech(body)
            text = safe_format(tts_template, app_name, clean_summary, clean_body)
            task = {
                "action": "tts",
                "text": text,
                "voice": voice
            }
        else:
            task = {
                "action": "sound",
                "sound_file": sound_file
            }
            
        spooler_queue.put(task)

    # D-Bus setup
    DBusGMainLoop(set_as_default=True)
    try:
        bus = dbus.SessionBus()
    except Exception as e:
        log_message(f"[{time.asctime()}] Failed to connect to D-Bus: {e}\n")
        sys.exit(1)
        
    # Listen to Notify method calls using message filter
    from dbus.lowlevel import HANDLER_RESULT_HANDLED, HANDLER_RESULT_NOT_YET_HANDLED
    
    def msg_filter(connection, message):
        interface = message.get_interface()
        member = message.get_member()
        if interface == 'org.freedesktop.Notifications' and member == 'Notify':
            args = message.get_args_list()
            if len(args) >= 5:
                app_name = str(args[0])
                summary = str(args[3])
                body = str(args[4])
                on_notification(app_name, summary, body)
            return HANDLER_RESULT_HANDLED
        return HANDLER_RESULT_NOT_YET_HANDLED

    bus.add_match_string("eavesdrop=true,interface='org.freedesktop.Notifications',member='Notify',type='method_call'")
    bus.get_connection().add_message_filter(msg_filter)
    
    dbus_disconnected = False

    # Periodically check if the D-Bus connection is still active
    def check_dbus_connection():
        nonlocal dbus_disconnected
        try:
            if not bus.get_connection().get_is_connected():
                log_message(f"[{time.asctime()}] D-Bus connection lost\n")
                dbus_disconnected = True
                spooler_queue.put(None)
                loop.quit()
                return False
        except Exception as e:
            log_message(f"[{time.asctime()}] D-Bus connection check failed: {e}\n")
            dbus_disconnected = True
            spooler_queue.put(None)
            loop.quit()
            return False
        return True

    GLib.timeout_add(2000, check_dbus_connection)

    # Simulate DBus disconnect if environment variable is set
    if os.environ.get("GNOTIFY_SIMULATE_DBUS_DISCONNECT") == "1":
        def trigger_dbus_disconnect():
            log_message(f"[{time.asctime()}] D-Bus connection lost\n")
            sys.exit(1)
        GLib.timeout_add(500, trigger_dbus_disconnect)
        
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    if dbus_disconnected:
        sys.exit(1)

if __name__ == '__main__':
    main()
