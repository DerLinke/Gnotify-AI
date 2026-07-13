import os
import sys
import time
import json
import socket
import shutil
import tempfile
import subprocess
import pytest

def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

class GnotifySandbox:
    def __init__(self, tts_port):
        self.temp_dir = tempfile.mkdtemp(prefix="gnotify_test_home_")
        self.home = self.temp_dir
        self.tts_port = tts_port
        
        try:
            with open('/tmp/active_gnotify_test_home.txt', 'w') as f:
                f.write(self.home)
        except Exception:
            pass
        
        # Create folder structure
        self.config_dir = os.path.join(self.home, ".config", "Gnotify-AI")
        self.cache_dir = os.path.join(self.home, ".cache", "Gnotify-AI")
        self.tts_cache_dir = os.path.join(self.cache_dir, "tts")
        self.bin_dir = os.path.join(self.home, "bin")
        
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.tts_cache_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)
        
        self.write_mock_paplay()
        
        # Initialize default config
        self.write_config({
            "api_url": f"http://127.0.0.1:{self.tts_port}/v1",
            "default_voice": "en-us-speaker",
            "rate_limit_max": 5,
            "rate_limit_window": 30,
            "deduplication_window": 5,
            "rules": []
        })
        
        self.daemon_proc = None

    def write_mock_paplay(self):
        paplay_path = os.path.join(self.bin_dir, "paplay")
        content = """#!/usr/bin/env python3
import os
import sys
import json
import time
import hashlib

def main():
    home = os.environ.get('HOME', '')
    
    # Read exit code config
    exit_code = 0
    config_path = os.path.join(home, 'mock_paplay_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                exit_code = cfg.get('exit_code', 0)
        except Exception:
            pass

    # Find wave file
    wav_path = ""
    for arg in sys.argv[1:]:
        if not arg.startswith('-'):
            wav_path = arg
            break

    file_md5 = ""
    if wav_path and os.path.exists(wav_path):
        try:
            with open(wav_path, 'rb') as f:
                file_md5 = hashlib.md5(f.read()).hexdigest()
        except Exception:
            pass

    playback_log_path = os.path.join(home, '.cache', 'Gnotify-AI', 'test_playback.log')
    os.makedirs(os.path.dirname(playback_log_path), exist_ok=True)
    
    log_entry = {
        "timestamp": time.time(),
        "args": sys.argv[1:],
        "file_path": wav_path,
        "md5": file_md5,
        "exit_code": exit_code
    }
    
    try:
        with open(playback_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\\n')
    except Exception:
        pass

    sys.exit(exit_code)

if __name__ == '__main__':
    main()
"""
        with open(paplay_path, "w") as f:
            f.write(content)
        os.chmod(paplay_path, 0o755)

    def write_config(self, config_dict):
        config_path = os.path.join(self.config_dir, "config.json")
        tmp_path = config_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(config_dict, f, indent=2)
        os.replace(tmp_path, config_path)

    def write_mock_tts_config(self, delay=0.0, status_code=200, content_type='audio/x-wav', corrupt_wav=False, non_wav_json=False, empty_body=False):
        cfg = {
            "delay": delay,
            "status_code": status_code,
            "response_content_type": content_type,
            "corrupt_wav": corrupt_wav,
            "non_wav_json": non_wav_json,
            "empty_body": empty_body
        }
        config_path = os.path.join(self.home, "mock_tts_config.json")
        tmp_path = config_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_path, config_path)

    def write_mock_paplay_config(self, exit_code=0):
        cfg = {"exit_code": exit_code}
        config_path = os.path.join(self.home, "mock_paplay_config.json")
        tmp_path = config_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_path, config_path)

    def start_daemon(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        daemon_path = os.path.join(os.path.dirname(tests_dir), "gnotify_ai_daemon.py")
        env = os.environ.copy()
        env["HOME"] = self.home
        env["PATH"] = self.bin_dir + os.path.pathsep + env.get("PATH", "")
        
        try:
            self.daemon_proc = subprocess.Popen(
                ["python3", daemon_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Allow initialization time
            time.sleep(0.5)
        except Exception as e:
            print(f"Exception spawning daemon: {e}", file=sys.stderr)
            self.daemon_proc = None

    def stop_daemon(self):
        if self.daemon_proc:
            self.daemon_proc.terminate()
            try:
                self.daemon_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.daemon_proc.kill()
                self.daemon_proc.wait()
            self.daemon_proc = None

    def send_sighup(self):
        if self.daemon_proc:
            import signal
            self.daemon_proc.send_signal(signal.SIGHUP)
            time.sleep(0.2)

    def send_notification(self, app_name, summary, body, replaces_id=0, app_icon="", actions=[], hints={}, expire_timeout=-1):
        import dbus
        session_bus = dbus.SessionBus(private=True)
        try:
            obj = session_bus.get_object('org.freedesktop.Notifications', '/org/freedesktop/Notifications')
            interface = dbus.Interface(obj, 'org.freedesktop.Notifications')
            
            dbus_hints = {}
            for k, v in hints.items():
                if isinstance(v, str):
                    dbus_hints[k] = dbus.String(v)
                elif isinstance(v, int):
                    dbus_hints[k] = dbus.Int32(v)
                elif isinstance(v, bool):
                    dbus_hints[k] = dbus.Boolean(v)
                else:
                    dbus_hints[k] = v
            
            nid = interface.Notify(
                app_name,
                dbus.UInt32(replaces_id),
                app_icon,
                summary,
                body,
                dbus.Array(actions, signature='s'),
                dbus.Dictionary(dbus_hints, signature='sv'),
                dbus.Int32(expire_timeout)
            )
            return nid
        finally:
            session_bus.close()

    def read_daemon_log(self):
        log_path = os.path.join(self.cache_dir, "gnotify-ai.log")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""

    def read_playback_log(self):
        log_path = os.path.join(self.cache_dir, "test_playback.log")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return [json.loads(line.strip()) for line in lines if line.strip()]
        return []

    def read_tts_requests(self):
        log_path = os.path.join(self.home, "tts_requests.log")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return [json.loads(line.strip()) for line in lines if line.strip()]
        return []

    def clean(self):
        log_path = os.path.join(self.cache_dir, "gnotify-ai.log")
        if os.path.exists(log_path):
            print("\n--- DAEMON LOG ---", flush=True)
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                print(f.read(), flush=True)
            print("------------------", flush=True)
        if self.daemon_proc:
            try:
                out, err = self.daemon_proc.communicate(timeout=0.2)
                if out:
                    print("\n--- DAEMON STDOUT ---", flush=True)
                    print(out, flush=True)
                if err:
                    print("\n--- DAEMON STDERR ---", flush=True)
                    print(err, flush=True)
            except Exception:
                pass
        self.stop_daemon()
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

@pytest.fixture(scope="session")
def tts_port():
    return get_free_port()

@pytest.fixture(scope="session", autouse=True)
def mock_servers(tts_port):
    # Start a private, completely isolated dbus-daemon session
    dbus_daemon_proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--print-address", "--nofork"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )
    
    # Read the printed address from stdout
    dbus_addr = dbus_daemon_proc.stdout.readline().strip()
    if not dbus_addr:
        status = dbus_daemon_proc.poll()
        raise RuntimeError(f"Failed to start isolated dbus-daemon. Status: {status}")
    
    # Set the environment variable to this private address
    old_dbus_addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_addr

    tests_dir = os.path.dirname(os.path.abspath(__file__))
    dbus_mock_path = os.path.join(tests_dir, "mock_dbus.py")
    tts_mock_path = os.path.join(tests_dir, "mock_tts.py")
    
    # We must preserve the environment, especially DBUS_SESSION_BUS_ADDRESS
    dbus_proc = subprocess.Popen(["python3", dbus_mock_path])
    tts_proc = subprocess.Popen(["python3", tts_mock_path, str(tts_port)])
    
    time.sleep(1.0)
    
    dbus_status = dbus_proc.poll()
    tts_status = tts_proc.poll()
    if dbus_status is not None:
        raise RuntimeError(f"Mock D-Bus server failed to start. Exit code: {dbus_status}")
    if tts_status is not None:
        raise RuntimeError(f"Mock TTS server failed to start. Exit code: {tts_status}")
        
    yield
    
    dbus_proc.terminate()
    tts_proc.terminate()
    dbus_daemon_proc.terminate()
    try:
        dbus_proc.wait(timeout=2)
        tts_proc.wait(timeout=2)
        dbus_daemon_proc.wait(timeout=2)
    except Exception:
        dbus_proc.kill()
        tts_proc.kill()
        dbus_daemon_proc.kill()
        
    if old_dbus_addr is not None:
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = old_dbus_addr
    else:
        os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)

@pytest.fixture
def sandbox(tts_port):
    sb = GnotifySandbox(tts_port)
    yield sb
    sb.clean()
