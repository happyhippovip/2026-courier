import pytest
from pathlib import Path
from scripts.installer_framework import InstallerBuilder

def test_generate_nsi_script(tmp_path):
    output_dir = tmp_path / "build"
    builder = InstallerBuilder("TestApp", "1.0", str(output_dir))
    
    files = ["C:\\dummy\\file1.txt", "C:\\dummy\\file2.txt"]
    target_dir = "$PROGRAMFILES\\TestApp"
    
    script_path = builder.generate_nsi_script(files, target_dir)
    assert Path(script_path).exists()
    
    script_content = Path(script_path).read_text()
    assert '!define APPNAME "TestApp"' in script_content
    assert 'File "C:\\dummy\\file1.txt"' in script_content
    assert 'WriteUninstaller "$INSTDIR\\uninstall.exe"' in script_content
    assert 'Delete "$INSTDIR\\file1.txt"' in script_content
