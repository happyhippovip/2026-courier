import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('video_server', Path(__file__).parents[1] / 'video_server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ProxyTests(unittest.TestCase):
    def test_fixed_get_source_and_no_control_credentials(self):
        raw = {'token': 'SECRET', 'workspace': '/private/example',
               'session': {'count': 999991, 'mode': 'BEGRENZT'},
               'state': {'status': 'RUNNING', 'lanes': {'one': {'task': {'task_id': 'task-a', 'token': 'SECRET'}}}}}
        with patch.object(server, 'urlopen', return_value=io.BytesIO(json.dumps(raw).encode())) as fetch:
            result = server.read_status()
        fetch.assert_called_once_with(server.SOURCE, timeout=2)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('/private/example', json.dumps(result))
        self.assertEqual(result['cannon']['state']['tasks'], ['task-a'])

    def test_malformed_or_large_source_never_live(self):
        for raw in [b'{}', b'not json', b'x'*65537]:
            with patch.object(server, 'urlopen', return_value=io.BytesIO(raw)):
                with self.assertRaises((ValueError, KeyError)):
                    server.read_status()

    def test_no_write_handler(self):
        for method in ('do_POST', 'do_PUT', 'do_PATCH', 'do_DELETE'):
            self.assertFalse(hasattr(server.Handler, method))


if __name__ == '__main__':
    unittest.main()
