import os
import platform
import pytest
from pathlib import Path
from app.cannon_yolo import check_ws, WS_PFAD, PROTECT

def test_check_ws_valid():
    # Gültiger Pfad im Workspace
    valid = check_ws(WS_PFAD / "scripts" / "test_file.txt")
    assert valid.is_absolute()
    assert valid.name == "test_file.txt"

def test_check_ws_path_traversal():
    # Traversal Versuch
    with pytest.raises(ValueError, match="Path-Traversal"):
        check_ws(WS_PFAD / "scripts" / ".." / ".." / "etc" / "passwd")
        
    with pytest.raises(ValueError, match="Path-Traversal"):
        check_ws(str(WS_PFAD) + "/scripts/../../etc/passwd")

def test_check_ws_outside_workspace():
    # Außerhalb
    outside = Path("/tmp/some_file.txt")
    with pytest.raises(ValueError, match="außerhalb des Workspaces"):
        check_ws(outside)

def test_check_ws_protect_list():
    # Geschützte Datei
    with pytest.raises(ValueError, match="Zugriff auf geschützten Pfad verweigert"):
        check_ws(WS_PFAD / ".git" / "config")
        
    with pytest.raises(ValueError, match="Zugriff auf geschützten Pfad verweigert"):
        check_ws(WS_PFAD / "app" / "cannon.html")
        
def test_check_ws_case_sensitivity():
    # Groß/Kleinschreibung Test auf Windows (case-insensitive) vs Mac (case-sensitive)
    protected_upper = WS_PFAD / "APP" / "CANNON.HTML"
    if platform.system() == "Windows":
        with pytest.raises(ValueError, match="Zugriff auf geschützten Pfad verweigert"):
            check_ws(protected_upper)
    else:
        # Auf Mac sollte der Pfad theoretisch durchgehen, es sei denn das Dateisystem ist case-insensitive.
        # "Mac-Verhalten unverändert."
        # Wir lassen die Standard Pathlib Auflösung entscheiden.
        pass

def test_check_ws_symlink_escape(tmp_path):
    # Erstelle Symlink der aus dem Workspace ausbricht
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret")
    
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    
    symlink_path = ws_dir / "link_out"
    os.symlink(outside_dir, symlink_path)
    
    with pytest.raises(ValueError, match="außerhalb des Workspaces"):
        check_ws(symlink_path / "secret.txt", ws_pfad=ws_dir)

