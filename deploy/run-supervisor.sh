#!/bin/bash
source venv/bin/activate
exec gunicorn -w 4 -b 0.0.0.0:8080 server.app:app
