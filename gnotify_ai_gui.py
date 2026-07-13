#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Gnotify AI GUI
# Version: 1.0.0

import os
import sys
import json
import shutil
import subprocess
import threading
import time
import re
import signal
import urllib.request
import urllib.error
import customtkinter as ctk
from tkinter import messagebox, filedialog

SCRIPTNAME = "Gnotify-AI GUI"
VERSION = "1.0.0"

# ANSI Colors for DerLinke Branding
C_RED = "\033[38;2;255;0;0m"
C_PINK = "\033[38;2;161;0;94m"
C_BLUE = "\033[38;2;0;0;255m"
NC = "\033[0m"
BOLD = "\033[1m"

def show_banner():
    print(f"      {C_PINK}██{NC}   {C_BLUE}█████{NC}")
    print(f"   {C_RED}██{NC}             {C_BLUE}██{NC}")
    print(f"{C_RED}██{NC}          {C_BLUE}██{NC} {BOLD}{SCRIPTNAME} v{VERSION}{NC}")
    print(f"   {C_RED}██{NC}             {C_BLUE}██{NC}")
    print(f"      {C_PINK}██{NC}   {C_BLUE}█████{NC}\n")

def show_footer():
    print(f"\n{C_BLUE}----------------------------------------------------{NC}")
    print(f"  {BOLD}{SCRIPTNAME} v{VERSION}{NC}")
    print(f"  \033[2mWeb:\033[0m {C_BLUE}\033[4mhttps://derlinke.github.io/\033[0m")
    print(f"  {C_RED}██{C_PINK}██{C_BLUE}██{NC}")
    print(f"{C_BLUE}===================================================={NC}\n")

DEFAULT_CONFIG = {
    "api_url": "https://ai.dan.jetzt/v1",
    "default_voice": "af_bella",
    "rate_limit_max": 5,
    "rate_limit_window": 30,
    "deduplication_window": 5,
    "debug": False,
    "rules": []
}

class LogTailer(threading.Thread):
    def __init__(self, log_path, callback):
        super().__init__(daemon=True)
        self.log_path = log_path
        self.callback = callback
        self._stop_event = threading.Event()
        
    def stop(self):
        self._stop_event.set()
        
    def run(self):
        # Ensure log directory exists
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'w') as f:
                    pass
            except Exception:
                pass
                
        # Read last 100 lines on startup if log exists
        if os.path.exists(self.log_path):
            try:
                from collections import deque
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    last_lines = deque(f, maxlen=100)
                for line in last_lines:
                    self.callback(line)
            except Exception:
                pass

        while not self._stop_event.is_set():
            if not os.path.exists(self.log_path):
                time.sleep(0.5)
                continue
            try:
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Seek to end on start
                    f.seek(0, os.SEEK_END)
                    while not self._stop_event.is_set():
                        curr_pos = f.tell()
                        # Check truncation
                        try:
                            if os.path.getsize(self.log_path) < curr_pos:
                                f.seek(0)
                        except OSError:
                            pass
                            
                        line = f.readline()
                        if line:
                            self.callback(line)
                        else:
                            time.sleep(0.2)
            except Exception as e:
                time.sleep(1.0)

class RuleDialog(ctk.CTkToplevel):
    def __init__(self, parent, rule=None, on_save=None):
        super().__init__(parent)
        self.title("Edit Rule" if rule else "Add Rule")
        self.geometry("550x620")
        
        # Modal setup
        self.transient(parent)
        self.grab_set()
        
        self.rule = rule or {}
        self.on_save = on_save
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_lbl = ctk.CTkLabel(self.main_frame, text="Rule Editor", font=ctk.CTkFont(size=18, weight="bold"))
        title_lbl.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
        
        # App Name Pattern
        ctk.CTkLabel(self.main_frame, text="App Name Pattern (Regex):").grid(row=1, column=0, sticky="w", pady=5)
        self.app_name_entry = ctk.CTkEntry(self.main_frame, placeholder_text="e.g. Slack (optional)")
        self.app_name_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.app_name_entry.insert(0, self.rule.get("app_name", ""))
        
        # Summary Regex
        ctk.CTkLabel(self.main_frame, text="Summary Regex:").grid(row=2, column=0, sticky="w", pady=5)
        self.summary_regex_entry = ctk.CTkEntry(self.main_frame, placeholder_text="e.g. .* or specific text (optional)")
        self.summary_regex_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        self.summary_regex_entry.insert(0, self.rule.get("summary_regex", ""))
        
        # Body Regex
        ctk.CTkLabel(self.main_frame, text="Body Regex:").grid(row=3, column=0, sticky="w", pady=5)
        self.body_regex_entry = ctk.CTkEntry(self.main_frame, placeholder_text="e.g. .* or specific text (optional)")
        self.body_regex_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)
        self.body_regex_entry.insert(0, self.rule.get("body_regex", ""))
        
        # Action OptionMenu
        ctk.CTkLabel(self.main_frame, text="Action:").grid(row=4, column=0, sticky="w", pady=5)
        self.action_var = ctk.StringVar(value=self.rule.get("action", "tts"))
        self.action_menu = ctk.CTkOptionMenu(self.main_frame, values=["tts", "sound", "mute"], variable=self.action_var, command=self.on_action_change)
        self.action_menu.grid(row=4, column=1, sticky="w", pady=5, padx=5)
        
        # Action-specific frame layout
        # TTS fields container
        self.tts_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.tts_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.tts_frame, text="TTS Template:").grid(row=0, column=0, sticky="w", pady=5)
        self.tts_template_entry = ctk.CTkEntry(self.tts_frame, placeholder_text="e.g. Slack from {summary}: {body}")
        self.tts_template_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.tts_template_entry.insert(0, self.rule.get("tts_template", "{body}"))
        
        ctk.CTkLabel(self.tts_frame, text="Voice:").grid(row=1, column=0, sticky="w", pady=5)
        self.voice_combobox = ctk.CTkComboBox(self.tts_frame, values=["af_bella", "af_sarah", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis", "de_martin", "ff_siwis", "ef_dora", "em_alex", "if_sara", "im_nicola", "pf_dora", "pm_alex"])
        self.voice_combobox.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.voice_combobox.set(self.rule.get("voice", ""))
        
        # Sound fields container
        self.sound_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.sound_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.sound_frame, text="Sound File Path:").grid(row=0, column=0, sticky="w", pady=5)
        self.sound_file_entry = ctk.CTkEntry(self.sound_frame, placeholder_text="/path/to/sound.wav")
        self.sound_file_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.sound_file_entry.insert(0, self.rule.get("sound_file", ""))
        
        browse_btn = ctk.CTkButton(self.sound_frame, text="Browse...", width=80, command=self.browse_sound_file)
        browse_btn.grid(row=0, column=2, pady=5, padx=5)
        
        # Buttons Container (Cancel/Save)
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.grid(row=7, column=0, columnspan=2, pady=(30, 0), sticky="ew")
        self.btn_frame.grid_columnconfigure((0, 1), weight=1)
        
        cancel_btn = ctk.CTkButton(self.btn_frame, text="Cancel", fg_color="#7f8c8d", hover_color="#95a5a6", command=self.destroy)
        cancel_btn.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        
        save_btn = ctk.CTkButton(self.btn_frame, text="Save Rule", fg_color="#2ecc71", hover_color="#27ae60", command=self.save_rule)
        save_btn.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.on_action_change(self.action_var.get())
        
    def on_action_change(self, action):
        if action == "tts":
            self.sound_frame.grid_forget()
            self.tts_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        elif action == "sound":
            self.tts_frame.grid_forget()
            self.sound_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=10)
        else: # mute
            self.tts_frame.grid_forget()
            self.sound_frame.grid_forget()
            
    def browse_sound_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Sound File",
            filetypes=[("Audio Files", "*.wav *.ogg *.mp3"), ("All Files", "*.*")]
        )
        if file_path:
            self.sound_file_entry.delete(0, "end")
            self.sound_file_entry.insert(0, file_path)
            
    def save_rule(self):
        app_name = self.app_name_entry.get().strip()
        summary_regex = self.summary_regex_entry.get().strip()
        body_regex = self.body_regex_entry.get().strip()
        action = self.action_var.get()
        
        # Validations
        for field, pattern in [("App Name Pattern", app_name), ("Summary Regex", summary_regex), ("Body Regex", body_regex)]:
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as e:
                    messagebox.showerror("Invalid Regex", f"The pattern for '{field}' is not a valid regular expression:\n{e}")
                    return
                    
        rule_data = {"action": action}
        if app_name:
            rule_data["app_name"] = app_name
        if summary_regex:
            rule_data["summary_regex"] = summary_regex
        if body_regex:
            rule_data["body_regex"] = body_regex
            
        if action == "tts":
            template = self.tts_template_entry.get().strip()
            voice = self.voice_combobox.get().strip()
            if template:
                rule_data["tts_template"] = template
            if voice:
                rule_data["voice"] = voice
        elif action == "sound":
            sound_file = self.sound_file_entry.get().strip()
            if not sound_file:
                messagebox.showerror("Missing Field", "Please select a sound file.")
                return
            rule_data["sound_file"] = sound_file
            
        if self.on_save:
            self.on_save(rule_data)
            
        self.destroy()

class GnotifyGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Gnotify AI Control Center")
        self.geometry("1000x750")
        
        self.config_path = os.path.expanduser("~/.config/Gnotify-AI/config.json")
        self.log_path = os.path.expanduser("~/.cache/Gnotify-AI/gnotify-ai.log")
        self.config_data = self.load_config()
        
        # Setup layouts
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # 1. Header Frame (Service Monitor / Commands)
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        self.title_lbl = ctk.CTkLabel(self.header_frame, text="GNOTIFY AI", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_lbl.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        self.status_lbl = ctk.CTkLabel(self.header_frame, text="Service Status: CHECKING...", font=ctk.CTkFont(size=14, weight="bold"))
        self.status_lbl.grid(row=0, column=1, padx=20, pady=15, sticky="e")
        
        self.ai_status_lbl = ctk.CTkLabel(self.header_frame, text="AI Server: CHECKING...", font=ctk.CTkFont(size=14, weight="bold"))
        self.ai_status_lbl.grid(row=0, column=2, padx=20, pady=15, sticky="e")
        
        self.start_btn = ctk.CTkButton(self.header_frame, text="Start", width=80, fg_color="#2ecc71", hover_color="#27ae60", command=self.start_service)
        self.start_btn.grid(row=0, column=3, padx=5, pady=15)
        
        self.stop_btn = ctk.CTkButton(self.header_frame, text="Stop", width=80, fg_color="#e74c3c", hover_color="#c0392b", command=self.stop_service)
        self.stop_btn.grid(row=0, column=4, padx=5, pady=15)
        
        self.restart_btn = ctk.CTkButton(self.header_frame, text="Restart", width=80, command=self.restart_service)
        self.restart_btn.grid(row=0, column=5, padx=10, pady=15)
        
        # 2. Main Tab View
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 10))
        
        self.tab_config = self.tabview.add("Configuration & Rules")
        self.tab_logs = self.tabview.add("Live Logs")
        self.tab_test = self.tabview.add("Test Suite")
        
        # Setup Tab 1: Configuration & Rules
        self.setup_config_tab()
        
        # Setup Tab 2: Logs
        self.setup_logs_tab()
        
        # Setup Tab 3: Test Suite
        self.setup_test_tab()
        
        # 3. Footer Branding Bar
        self.footer_frame = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color="transparent")
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.footer_lbl = ctk.CTkLabel(self.footer_frame, text="DerLinke Software Zentrale | Web: https://derlinke.github.io/", font=ctk.CTkFont(size=11))
        self.footer_lbl.pack(pady=5)
        
        # Start Log Tailer
        self.log_tailer = LogTailer(self.log_path, self.queue_log_update)
        self.log_tailer.start()
        
        # Start Service Status Loop
        self.refresh_systemd_status()
        self.refresh_ai_status()
        
        # Handle cleanup
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def load_config(self):
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            try:
                tmp_path = self.config_path + ".tmp"
                with open(tmp_path, "w") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
                os.replace(tmp_path, self.config_path)
            except Exception:
                pass
            return DEFAULT_CONFIG.copy()
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                for k, v in data.items():
                    config[k] = v
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
            
    def save_config_file(self):
        tmp_path = self.config_path + ".tmp"
        f = None
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            f = open(tmp_path, "w")
            json.dump(self.config_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            f.close()
            f = None
            os.replace(tmp_path, self.config_path)
        except Exception as e:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise e

    def save_config(self):
        try:
            self.save_config_file()
            self.reload_daemon()
            self.write_log_message("GUI config saved & daemon reload signaled.")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{e}")
            return False
            
    def reload_daemon(self):
        def run():
            reloaded = False
            try:
                res = subprocess.run(["systemctl", "--user", "is-active", "gnotify-ai"], capture_output=True, text=True)
                if res.stdout.strip() == "active":
                    subprocess.run(["systemctl", "--user", "kill", "-s", "SIGHUP", "gnotify-ai"], check=True)
                    reloaded = True
            except Exception:
                pass
                
            if not reloaded:
                # Fallback to direct PID killing
                try:
                    res = subprocess.run(["pgrep", "-f", "gnotify_ai_daemon.py"], capture_output=True, text=True)
                    pids = [int(pid) for pid in res.stdout.splitlines() if pid.strip()]
                    my_pid = os.getpid()
                    for pid in pids:
                        if pid != my_pid:
                            os.kill(pid, signal.SIGHUP)
                except Exception as e:
                    self.after(0, lambda err=e: self.write_log_message(f"Failed to reload daemon: {err}"))
        threading.Thread(target=run, daemon=True).start()

    def write_log_message(self, text):
        try:
            with open(self.log_path, 'a') as f:
                f.write(f"[{time.asctime()}] [GUI] {text}\n")
        except Exception:
            pass

    # Dynamic status monitoring
    def refresh_ai_status(self):
        def run():
            api_url = self.config_data.get("api_url", "https://ai.dan.jetzt/v1")
            status_text = "AI Server: OFFLINE"
            color = "#e74c3c"
            try:
                req = urllib.request.Request(f"{api_url.rstrip('/')}/models")
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.getcode() == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        models = [m.get("id", "") for m in data.get("data", [])]
                        if "kokoro-de" in models:
                            status_text = "AI Server: ONLINE (kokoro-de)"
                            color = "#2ecc71"
                        elif "kokoro" in models:
                            status_text = "AI Server: ONLINE (kokoro)"
                            color = "#2ecc71"
                        else:
                            status_text = "AI Server: ONLINE (No TTS)"
                            color = "#f1c40f"
            except Exception:
                pass
            self.after(0, lambda: self.ai_status_lbl.configure(text=status_text, text_color=color))
            self.after(5000, self.refresh_ai_status)
        threading.Thread(target=run, daemon=True).start()

    def refresh_systemd_status(self):
        def run():
            try:
                res_active = subprocess.run(["systemctl", "--user", "is-active", "gnotify-ai"], capture_output=True, text=True)
                active_status = res_active.stdout.strip()
            except Exception:
                active_status = "unknown"
                
            try:
                res_detail = subprocess.run(["systemctl", "--user", "status", "gnotify-ai"], capture_output=True, text=True)
                detail_status = res_detail.stdout
            except Exception:
                detail_status = "unknown"
                
            self.after(0, self.update_status_ui, active_status, detail_status)
        threading.Thread(target=run, daemon=True).start()

    def update_status_ui(self, status, detail_status):
        if status == "active":
            self.status_lbl.configure(text="Service Status: ACTIVE", text_color="#2ecc71")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.restart_btn.configure(state="normal")
        elif status == "inactive":
            self.status_lbl.configure(text="Service Status: INACTIVE", text_color="#e74c3c")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.restart_btn.configure(state="disabled")
        elif status == "failed":
            self.status_lbl.configure(text="Service Status: FAILED", text_color="#e67e22")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.restart_btn.configure(state="normal")
        else:
            self.status_lbl.configure(text=f"Service Status: {status.upper()}", text_color="#95a5a6")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="normal")
            self.restart_btn.configure(state="normal")
            
        if hasattr(self, "status_txt") and self.status_txt:
            try:
                self.status_txt.configure(state="normal")
                self.status_txt.delete("1.0", "end")
                self.status_txt.insert("end", detail_status)
                self.status_txt.configure(state="disabled")
            except Exception:
                pass
                
        self.after(3000, self.refresh_systemd_status)

    def start_service(self):
        def run():
            try:
                subprocess.run(["systemctl", "--user", "start", "gnotify-ai"], check=True)
                self.after(0, lambda: self.write_log_message("Started service gnotify-ai."))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", f"Failed to start service: {err}"))
        threading.Thread(target=run, daemon=True).start()
            
    def stop_service(self):
        def run():
            try:
                subprocess.run(["systemctl", "--user", "stop", "gnotify-ai"], check=True)
                self.after(0, lambda: self.write_log_message("Stopped service gnotify-ai."))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", f"Failed to stop service: {err}"))
        threading.Thread(target=run, daemon=True).start()
            
    def restart_service(self):
        def run():
            try:
                subprocess.run(["systemctl", "--user", "restart", "gnotify-ai"], check=True)
                self.after(0, lambda: self.write_log_message("Restarted service gnotify-ai."))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Error", f"Failed to restart service: {err}"))
        threading.Thread(target=run, daemon=True).start()

    # Tab 1: Layout & logic
    def setup_config_tab(self):
        self.tab_config.grid_columnconfigure(0, weight=1)
        self.tab_config.grid_columnconfigure(1, weight=2)
        self.tab_config.grid_rowconfigure(0, weight=1)
        
        # Left Panel: General config settings
        self.gen_frame = ctk.CTkFrame(self.tab_config)
        self.gen_frame.grid(row=0, column=0, padx=(5, 10), pady=10, sticky="nsew")
        self.gen_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.gen_frame, text="General Settings", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=15, sticky="w")
        
        # API URL
        ctk.CTkLabel(self.gen_frame, text="API URL:").grid(row=1, column=0, padx=15, pady=8, sticky="w")
        self.api_url_ent = ctk.CTkEntry(self.gen_frame)
        self.api_url_ent.grid(row=1, column=1, padx=15, pady=8, sticky="ew")
        self.api_url_ent.insert(0, self.config_data.get("api_url", ""))
        
        # Default Voice
        ctk.CTkLabel(self.gen_frame, text="Default Voice:").grid(row=2, column=0, padx=15, pady=8, sticky="w")
        self.voice_ent = ctk.CTkComboBox(self.gen_frame, values=["af_bella", "af_sarah", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis", "de_martin", "ff_siwis", "ef_dora", "em_alex", "if_sara", "im_nicola", "pf_dora", "pm_alex"])
        self.voice_ent.grid(row=2, column=1, padx=15, pady=8, sticky="ew")
        self.voice_ent.set(self.config_data.get("default_voice", "af_bella"))
        
        # Rate Limit Max
        ctk.CTkLabel(self.gen_frame, text="Rate Limit Max:").grid(row=3, column=0, padx=15, pady=8, sticky="w")
        self.rl_max_ent = ctk.CTkEntry(self.gen_frame)
        self.rl_max_ent.grid(row=3, column=1, padx=15, pady=8, sticky="ew")
        self.rl_max_ent.insert(0, str(self.config_data.get("rate_limit_max", 5)))
        
        # Rate Limit Window
        ctk.CTkLabel(self.gen_frame, text="Rate Limit Window (s):").grid(row=4, column=0, padx=15, pady=8, sticky="w")
        self.rl_win_ent = ctk.CTkEntry(self.gen_frame)
        self.rl_win_ent.grid(row=4, column=1, padx=15, pady=8, sticky="ew")
        self.rl_win_ent.insert(0, str(self.config_data.get("rate_limit_window", 30)))
        
        # Deduplication Window
        ctk.CTkLabel(self.gen_frame, text="Deduplication Window (s):").grid(row=5, column=0, padx=15, pady=8, sticky="w")
        self.dedup_ent = ctk.CTkEntry(self.gen_frame)
        self.dedup_ent.grid(row=5, column=1, padx=15, pady=8, sticky="ew")
        self.dedup_ent.insert(0, str(self.config_data.get("deduplication_window", 5)))
        
        # Debug Mode Switch
        ctk.CTkLabel(self.gen_frame, text="Debug Mode:").grid(row=6, column=0, padx=15, pady=8, sticky="w")
        self.debug_var = ctk.BooleanVar(value=self.config_data.get("debug", False))
        self.debug_sw = ctk.CTkSwitch(self.gen_frame, text="", variable=self.debug_var, command=self.on_debug_toggle)
        self.debug_sw.grid(row=6, column=1, padx=15, pady=8, sticky="w")
        
        # Save Settings Button
        self.save_settings_btn = ctk.CTkButton(self.gen_frame, text="Save General Settings", command=self.save_general_settings)
        self.save_settings_btn.grid(row=7, column=0, columnspan=2, padx=15, pady=25, sticky="ew")
        
        # Right Panel: Rule list editor
        self.rules_frame = ctk.CTkFrame(self.tab_config)
        self.rules_frame.grid(row=0, column=1, padx=(10, 5), pady=10, sticky="nsew")
        self.rules_frame.grid_columnconfigure(0, weight=1)
        self.rules_frame.grid_rowconfigure(1, weight=1)
        
        self.rules_header = ctk.CTkFrame(self.rules_frame, fg_color="transparent")
        self.rules_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.rules_header.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.rules_header, text="Matching Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w")
        self.add_rule_btn = ctk.CTkButton(self.rules_header, text="+ Add Rule", width=100, fg_color="#2ecc71", hover_color="#27ae60", command=self.open_add_rule_dialog)
        self.add_rule_btn.grid(row=0, column=1, sticky="e")
        
        # Scrollable Rules container
        self.rules_scroll = ctk.CTkScrollableFrame(self.rules_frame)
        self.rules_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.rules_scroll.grid_columnconfigure(0, weight=1)
        
        self.rebuild_rules_list()
        
    def save_general_settings(self):
        # Validate inputs
        try:
            rl_max = int(self.rl_max_ent.get().strip())
            rl_win = int(self.rl_win_ent.get().strip())
            dedup = int(self.dedup_ent.get().strip())
            if rl_max < 0 or rl_win < 0 or dedup < 0:
                raise ValueError("Values must be positive integers.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check limits/windows input:\n{e}")
            return
            
        self.config_data["api_url"] = self.api_url_ent.get().strip()
        self.config_data["default_voice"] = self.voice_ent.get().strip()
        self.config_data["rate_limit_max"] = rl_max
        self.config_data["rate_limit_window"] = rl_win
        self.config_data["deduplication_window"] = dedup
        self.config_data["debug"] = self.debug_var.get()
        
        if self.save_config():
            messagebox.showinfo("Success", "General configuration saved and daemon reloaded.")
            
    def on_debug_toggle(self):
        self.config_data["debug"] = self.debug_var.get()
        self.save_config()
        self.write_log_message(f"Debug Mode toggled to {self.debug_var.get()}")
        
    def rebuild_rules_list(self):
        for widget in self.rules_scroll.winfo_children():
            widget.destroy()
            
        rules = self.config_data.get("rules", [])
        if not rules:
            no_rules_lbl = ctk.CTkLabel(self.rules_scroll, text="No rules defined yet.", font=ctk.CTkFont(slant="italic"), text_color="gray")
            no_rules_lbl.pack(pady=40)
            return
            
        for i, rule in enumerate(rules):
            card = ctk.CTkFrame(self.rules_scroll, border_width=1, border_color="#34495e")
            card.pack(fill="x", padx=5, pady=5)
            card.grid_columnconfigure(0, weight=1)
            
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=0, padx=10, pady=8, sticky="w")
            
            # Rule Title
            rule_title = f"#{i+1} | "
            if "app_name" in rule:
                rule_title += f"App: '{rule['app_name']}'"
            else:
                rule_title += "Any Application"
            title_lbl = ctk.CTkLabel(info_frame, text=rule_title, font=ctk.CTkFont(weight="bold"))
            title_lbl.pack(anchor="w")
            
            # Details details
            regex_text = []
            if "summary_regex" in rule:
                regex_text.append(f"Summary matches '{rule['summary_regex']}'")
            if "body_regex" in rule:
                regex_text.append(f"Body matches '{rule['body_regex']}'")
            if regex_text:
                det_lbl = ctk.CTkLabel(info_frame, text=" & ".join(regex_text), font=ctk.CTkFont(size=12), text_color="#bdc3c7")
                det_lbl.pack(anchor="w")
                
            # Action details
            action = rule.get("action", "tts")
            action_desc = f"Action: {action.upper()}"
            if action == "tts":
                voice = rule.get("voice", "default voice")
                tpl = rule.get("tts_template", "{body}")
                action_desc += f" | Template: \"{tpl}\" | Voice: {voice}"
            elif action == "sound":
                action_desc += f" | Sound: {os.path.basename(rule.get('sound_file', ''))}"
            act_lbl = ctk.CTkLabel(info_frame, text=action_desc, font=ctk.CTkFont(size=12), text_color="#bdc3c7")
            act_lbl.pack(anchor="w")
            
            # Controls buttons
            ctrl_frame = ctk.CTkFrame(card, fg_color="transparent")
            ctrl_frame.grid(row=0, column=1, padx=10, pady=8, sticky="e")
            
            # Up Button
            up_btn = ctk.CTkButton(ctrl_frame, text="▲", width=30, command=lambda idx=i: self.move_rule_up(idx))
            up_btn.grid(row=0, column=0, padx=2)
            if i == 0:
                up_btn.configure(state="disabled")
                
            # Down Button
            down_btn = ctk.CTkButton(ctrl_frame, text="▼", width=30, command=lambda idx=i: self.move_rule_down(idx))
            down_btn.grid(row=0, column=1, padx=2)
            if i == len(rules) - 1:
                down_btn.configure(state="disabled")
                
            # Edit Button
            edit_btn = ctk.CTkButton(ctrl_frame, text="Edit", width=50, fg_color="#3498db", hover_color="#2980b9", command=lambda idx=i: self.open_edit_rule_dialog(idx))
            edit_btn.grid(row=0, column=2, padx=2)
            
            # Delete Button
            del_btn = ctk.CTkButton(ctrl_frame, text="Delete", width=50, fg_color="#e74c3c", hover_color="#c0392b", command=lambda idx=i: self.delete_rule(idx))
            del_btn.grid(row=0, column=3, padx=2)

    def move_rule_up(self, idx):
        if idx > 0:
            rules = self.config_data["rules"]
            rules[idx], rules[idx-1] = rules[idx-1], rules[idx]
            self.save_config()
            self.rebuild_rules_list()
            
    def move_rule_down(self, idx):
        rules = self.config_data["rules"]
        if idx < len(rules) - 1:
            rules[idx], rules[idx+1] = rules[idx+1], rules[idx]
            self.save_config()
            self.rebuild_rules_list()
            
    def delete_rule(self, idx):
        if messagebox.askyesno("Delete Rule", "Are you sure you want to delete this matching rule?"):
            self.config_data["rules"].pop(idx)
            self.save_config()
            self.rebuild_rules_list()
            
    def open_add_rule_dialog(self):
        RuleDialog(self, on_save=self.add_rule_callback)
        
    def add_rule_callback(self, new_rule):
        self.config_data["rules"].append(new_rule)
        self.save_config()
        self.rebuild_rules_list()
        
    def open_edit_rule_dialog(self, idx):
        rule = self.config_data["rules"][idx]
        RuleDialog(self, rule=rule, on_save=lambda updated_rule: self.edit_rule_callback(idx, updated_rule))
        
    def edit_rule_callback(self, idx, updated_rule):
        self.config_data["rules"][idx] = updated_rule
        self.save_config()
        self.rebuild_rules_list()

    # Tab 2: Live Logs
    def setup_logs_tab(self):
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        self.log_frame = ctk.CTkFrame(self.tab_logs)
        self.log_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_frame.grid_columnconfigure(0, weight=2)
        self.log_frame.grid_columnconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(2, weight=1)
        self.log_frame.grid_rowconfigure(0, weight=1)
        
        # Log Text Box
        self.log_txt = ctk.CTkTextbox(self.log_frame, font=ctk.CTkFont(family="monospace", size=12))
        self.log_txt.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        self.log_txt.configure(state="disabled")
        
        # Pre-populate log text box
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.log_txt.configure(state="normal")
                self.log_txt.insert("end", content)
                self.log_txt.configure(state="disabled")
                self.log_txt.see("end")
            except Exception:
                pass
                
        # Service Status Text Box
        self.status_txt = ctk.CTkTextbox(self.log_frame, font=ctk.CTkFont(family="monospace", size=12))
        self.status_txt.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        self.status_txt.configure(state="disabled")
        
        # Logging controls
        self.autoscroll_var = ctk.BooleanVar(value=True)
        self.autoscroll_cb = ctk.CTkCheckBox(self.log_frame, text="Autoscroll", variable=self.autoscroll_var)
        self.autoscroll_cb.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.clear_log_btn = ctk.CTkButton(self.log_frame, text="Clear Log File", fg_color="#e74c3c", hover_color="#c0392b", command=self.clear_log_file)
        self.clear_log_btn.grid(row=1, column=1, padx=10, pady=10, sticky="e")
        
        self.export_log_btn = ctk.CTkButton(self.log_frame, text="Export Logs...", command=self.export_logs)
        self.export_log_btn.grid(row=1, column=2, padx=10, pady=10, sticky="e")
        
    def queue_log_update(self, line):
        self.after(0, self.append_log, line)
        
    def append_log(self, text):
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", text)
        self.log_txt.configure(state="disabled")
        if self.autoscroll_var.get():
            self.log_txt.see("end")
            
    def clear_log_file(self):
        if messagebox.askyesno("Clear Logs", "Are you sure you want to empty the daemon log file?"):
            try:
                with open(self.log_path, 'w') as f:
                    pass
                self.log_txt.configure(state="normal")
                self.log_txt.delete("1.0", "end")
                self.log_txt.configure(state="disabled")
                self.write_log_message("Daemon log file truncated by user.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear log file: {e}")
                
    def export_logs(self):
        file_path = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                shutil.copyfile(self.log_path, file_path)
                messagebox.showinfo("Success", f"Logs exported to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export logs:\n{e}")

    # Tab 3: Test Suite
    def setup_test_tab(self):
        self.tab_test.grid_columnconfigure(0, weight=1)
        
        self.test_frame = ctk.CTkFrame(self.tab_test)
        self.test_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.test_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.test_frame, text="D-Bus Notification Generator", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=15, sticky="w")
        
        ctk.CTkLabel(self.test_frame, text="App Name:").grid(row=1, column=0, padx=15, pady=8, sticky="w")
        self.test_app_ent = ctk.CTkEntry(self.test_frame)
        self.test_app_ent.grid(row=1, column=1, padx=15, pady=8, sticky="ew")
        self.test_app_ent.insert(0, "Slack")
        
        ctk.CTkLabel(self.test_frame, text="Summary (Title):").grid(row=2, column=0, padx=15, pady=8, sticky="w")
        self.test_sum_ent = ctk.CTkEntry(self.test_frame)
        self.test_sum_ent.grid(row=2, column=1, padx=15, pady=8, sticky="ew")
        self.test_sum_ent.insert(0, "Dan")
        
        ctk.CTkLabel(self.test_frame, text="Body:").grid(row=3, column=0, padx=15, pady=8, sticky="w")
        self.test_body_ent = ctk.CTkEntry(self.test_frame)
        self.test_body_ent.grid(row=3, column=1, padx=15, pady=8, sticky="ew")
        self.test_body_ent.insert(0, "Hi, this is a test notification.")
        
        self.trigger_btn = ctk.CTkButton(self.test_frame, text="Send Test Notification", fg_color="#3498db", hover_color="#2980b9", command=self.send_test_notification)
        self.trigger_btn.grid(row=4, column=0, columnspan=2, padx=15, pady=25, sticky="ew")
        
    def send_test_notification(self):
        app = self.test_app_ent.get().strip()
        summary = self.test_sum_ent.get().strip()
        body = self.test_body_ent.get().strip()
        
        if not app or not summary or not body:
            messagebox.showerror("Error", "Please fill out all fields.")
            return
            
        try:
            # Using notify-send command
            subprocess.run(["notify-send", "-a", app, summary, body], check=True)
            self.write_log_message(f"Sent simulated notification: {app} | {summary} | {body}")
        except FileNotFoundError:
            messagebox.showerror("Error", "The command 'notify-send' was not found.\nPlease make sure libnotify-bin is installed on your system.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test notification:\n{e}")

    def on_closing(self):
        # Stop log tailer thread
        self.log_tailer.stop()
        self.destroy()
        show_footer()

def main():
    show_banner()
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    
    app = GnotifyGUI()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.on_closing()

if __name__ == "__main__":
    main()
