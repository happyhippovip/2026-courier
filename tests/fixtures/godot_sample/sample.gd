extends Node2D

const DURATION := 3.0
const CAPTURE_FPS := 30

var _frame := 0

func _process(_delta: float) -> void:
	_frame += 1
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(0, 0, 720, 1280), Color(0.94, 0.93, 0.90))
	var x := 36.0 + float(_frame) * 6.0
	var y := 480.0 + float(_frame) * 4.0
	draw_rect(Rect2(x, y, 180, 180), Color(0.12, 0.34, 0.72))
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(48, 220), "Sample", HORIZONTAL_ALIGNMENT_LEFT, -1, 72, Color(0.12, 0.12, 0.14))
