import sys
import py_compile
import os

def main():
    files_to_check = [
        "mock_dbus.py",
        "mock_tts.py",
        "conftest.py",
        "test_tier1.py",
        "test_tier2.py",
        "test_tier3.py",
        "test_tier4.py",
        "test_tier5.py",
        "run_tests.py",
        "../gnotify_ai_daemon.py",
        "../gnotify_ai_gui.py"
    ]
    
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    all_ok = True
    
    for f in files_to_check:
        path = os.path.normpath(os.path.join(tests_dir, f))
        try:
            py_compile.compile(path, doraise=True)
            print(f"OK: {f} is syntactically valid.")
        except py_compile.PyCompileError as e:
            print(f"ERROR: {f} has syntax errors: {e}", file=sys.stderr)
            all_ok = False
            
    if all_ok:
        print("All files compiled successfully.")
        sys.exit(0)
    else:
        print("Some files failed compilation.", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
