import sys, os, traceback
sys.path.insert(0, os.path.abspath('.'))
with open('server/crash.log', 'w') as f:
    sys.stdout = f
    sys.stderr = f
    try:
        import logging
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        from waitress import serve
        from server import app
        f.write('Starting server...\n')
        f.flush()
        serve(app.app, host='0.0.0.0', port=8080)
    except BaseException as e:
        f.write(traceback.format_exc())
