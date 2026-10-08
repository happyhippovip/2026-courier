# Render node

A render node runs `scripts/render_godot_movie.py` once per heavy job. The
wrapper reads `DURATION` and `CAPTURE_FPS` from the scene script, then starts
Godot Movie Maker. It does not pass `--headless`. Headless Godot does not
produce an image.

## Software

- Godot 4 stable, official Linux x86_64 binary. This proof used
  `4.7.2.stable.official.ed1daf0bf` from
  `Godot_v4.7.2-stable_linux.x86_64.zip`.
- ffmpeg and ffprobe on `PATH`.
- A display. Either a GPU with OpenGL 3, or Xvfb plus Mesa's llvmpipe
  (`libgl1-mesa-dri`). The software path used here is:

```
LIBGL_ALWAYS_SOFTWARE=1
GALLIUM_DRIVER=llvmpipe
xvfb-run -a -s "-screen 0 800x1400x24" python3 scripts/render_godot_movie.py ...
```

The Xvfb screen must be at least the project window. The sample scene is
720 by 1280, so the screen above is 800 by 1400.

## Command the wrapper builds

Godot is started as:

```
godot --rendering-driver opengl3 --rendering-method gl_compatibility \
  --path <project> --write-movie <output>/render.avi \
  --fixed-fps <fps> --quit-after <frames> -d <scene>
```

Pass `--godot`, `--ffmpeg`, `--ffprobe`, `--width`, and `--height` so the
MP4 check matches the project viewport. One host lock is held for the whole
render. If the lock is already held, the process exits 3 and starts nothing.
The default lock is `$HOME/.courier/locks/heavy_job.lock`. `--lock-file`
overrides it.

## Sample scene

`tests/fixtures/godot_sample/` is a read-only project: a rectangle that moves
and the word Sample, 3 seconds at 30 fps, viewport 720 by 1280. Godot writes
its import cache into the project directory, so copy the fixture to a
temporary directory before rendering.

## Optional test

`tests/test_render_godot_real.py` is marked `godot_real`. It skips when the
`godot` executable is absent, or when `COURIER_GODOT` is unset and `godot` is
not on `PATH`. A machine without Godot, including CI, stays green. Run it
where the tools above are installed:

```
python3 -m pytest -q tests/test_render_godot_real.py -m godot_real -s
```
