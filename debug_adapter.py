import os, sys, tempfile, json, runpy
from unittest import mock
tmp_path = tempfile.mkdtemp()
os.chdir(tmp_path)
mock_process = mock.Mock()
mock_process.communicate.return_value = ('```json\n{"status": "SUCCESS"}\n```', '')
with mock.patch('subprocess.Popen', return_value=mock_process):
    sys.argv = ['gemini_worker_adapter.py', 'positive']
    runpy.run_path('C:/Users/lol/2026-workspace/2026-courier/scripts/gemini_worker_adapter.py', run_name='__main__')
print(os.listdir('.'))
