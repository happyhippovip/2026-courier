import os
import platform
from pathlib import Path

# Die Standard-Workspace-Pfade
WS_PFAD = Path(__file__).resolve().parent.parent

# Geschützte Dateien/Ordner, die nicht manipuliert werden dürfen
PROTECT = [
    ".git",
    ".env",
    "app/cannon.html",
    "app/cannon.css",
    "app/cannon.js",
    "app/ui.js",
    "app/style.css"
]

def check_ws(target_path, ws_pfad=None):
    """
    Prüft, ob target_path sicher innerhalb von ws_pfad liegt und nicht
    in der PROTECT-Liste enthalten ist. Verhindert Path-Traversal,
    Symlink-Ausbrüche und Backslash-Tricks.
    """
    if ws_pfad is None:
        ws_pfad = WS_PFAD
    
    ws_pfad = Path(ws_pfad).resolve()
    
    # Backslashes ablehnen oder normalisieren (hier wandeln wir sie mit Path() um)
    # Aber um ganz sicher zu gehen, lehnen wir rohe ".." Strings ab
    target_str = str(target_path)
    if ".." in target_str.replace("\\", "/").split("/"):
        raise ValueError("Path-Traversal (..) ist nicht erlaubt.")
        
    try:
        # Resolve löst Symlinks auf
        target = Path(target_path).resolve()
    except Exception as e:
        raise ValueError(f"Ungültiger Pfad: {e}")
        
    # Darf nicht außerhalb des Workspaces liegen
    if not target.is_relative_to(ws_pfad):
        raise ValueError("Pfad liegt außerhalb des Workspaces (WS_PFAD).")
        
    # Groß-/Kleinschreibung & PROTECT-Liste prüfen
    # Da Windows case-insensitive ist, machen wir den Check robuster:
    rel_path = target.relative_to(ws_pfad)
    rel_parts = rel_path.parts
    
    for protected in PROTECT:
        prot_path = Path(protected)
        # Wenn der relative Pfad mit einem geschützten Pfad beginnt
        if len(rel_parts) >= len(prot_path.parts):
            # Check case-insensitive auf Windows, case-sensitive auf Mac
            if platform.system() == "Windows":
                match = (Path(*rel_parts[:len(prot_path.parts)]).as_posix().lower() == prot_path.as_posix().lower())
            else:
                match = (Path(*rel_parts[:len(prot_path.parts)]).as_posix() == prot_path.as_posix())
                
            if match:
                raise ValueError(f"Zugriff auf geschützten Pfad verweigert: {protected}")
                
    return target

