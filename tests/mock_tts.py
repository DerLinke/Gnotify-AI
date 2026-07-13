import os
import sys
import json
import time
import struct
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_minimal_wave_bytes(duration_sec=1.0, sample_rate=44100, num_channels=1, bits_per_sample=16):
    num_samples = int(duration_sec * sample_rate)
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    data = b'\x00' * data_size
    return header + data

class TTSMockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging to console to keep test output clean
        pass

    def do_POST(self):
        home = os.environ.get('HOME', '')
        if os.path.exists('/tmp/active_gnotify_test_home.txt'):
            try:
                with open('/tmp/active_gnotify_test_home.txt', 'r') as f:
                    home = f.read().strip()
            except Exception:
                pass
        config_path = os.path.join(home, 'mock_tts_config.json')
        delay = 0.0
        status_code = 200
        content_type = 'audio/x-wav'
        corrupt_wav = False
        non_wav_json = False
        empty_body = False
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    cfg = json.load(f)
                    delay = cfg.get('delay', 0.0)
                    status_code = cfg.get('status_code', 200)
                    content_type = cfg.get('response_content_type', 'audio/x-wav')
                    corrupt_wav = cfg.get('corrupt_wav', False)
                    non_wav_json = cfg.get('non_wav_json', False)
                    empty_body = cfg.get('empty_body', False)
            except Exception:
                pass

        if delay > 0:
            time.sleep(delay)

        # Log the request
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        request_log_path = os.path.join(home, 'tts_requests.log')
        try:
            req_info = {
                "timestamp": time.time(),
                "headers": dict(self.headers),
                "body": post_data.decode('utf-8', errors='ignore')
            }
            with open(request_log_path, 'a') as f:
                f.write(json.dumps(req_info) + '\n')
        except Exception:
            pass

        if status_code != 200:
            self.send_response(status_code)
            self.end_headers()
            self.wfile.write(b"Error simulated by mock")
            return

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()

        if non_wav_json:
            self.wfile.write(b'{"error": "invalid format"}')
        elif corrupt_wav:
            self.wfile.write(b"NOT A WAVE FILE BYTES")
        elif empty_body:
            pass
        else:
            self.wfile.write(get_minimal_wave_bytes())

def run(port=8089):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, TTSMockHandler)
    print(f"Mock TTS HTTP Server running on port {port}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8089
    run(port)
