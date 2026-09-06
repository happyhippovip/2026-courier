#!/usr/bin/env python3
"""Regression tests for bounded Movie Maker output-path handling."""
import tempfile
import unittest
from pathlib import Path

from scripts.render_godot_movie import movie_command


class RenderGodotMoviePathTests(unittest.TestCase):
    def test_movie_command_keeps_absolute_avi_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            avi = (Path(temporary) / "courier-output" / "render.avi").resolve()
            command = movie_command("/Applications/Godot", project, "res://scene.tscn", avi, 24, 192)
            self.assertIn("--fixed-fps", command)
            self.assertEqual(command[command.index("--fixed-fps") + 1], "24")
            self.assertEqual(command[command.index("--quit-after") + 1], "192")
            self.assertEqual(command[command.index("--write-movie") + 1], str(avi))
            self.assertTrue(Path(command[command.index("--write-movie") + 1]).is_absolute())


if __name__ == "__main__":
    unittest.main()
