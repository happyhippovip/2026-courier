import sys, os, traceback, subprocess
sys.path.insert(0, os.path.abspath('.'))
with open('server/crash.log', 'w') as f:
    sys.stdout = f
    sys.stderr = f
    try:
        import logging
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        from waitress import serve
        from server import app
        f.write('Starting verifier subprocess...\n')
        f.flush()
        env = os.environ.copy()
        env["COURIER_SERVER"] = "http://127.0.0.1:8081"
        verifier_proc = subprocess.Popen(
            [sys.executable, "scripts/courier_verifier.py"],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        f.write('Starting server...\n')
        f.write('App file is: ' + str(app.__file__) + '\n')
        f.flush()
        serve(app.app, host='0.0.0.0', port=8081)
    except BaseException as e:
        f.write(traceback.format_exc())
    finally:
        if 'verifier_proc' in locals():
            verifier_proc.terminate()
