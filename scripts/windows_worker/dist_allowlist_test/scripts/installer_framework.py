import os
import subprocess
from pathlib import Path

class InstallerBuilder:
    def __init__(self, app_name: str, version: str, output_dir: str):
        self.app_name = app_name
        self.version = version
        self.output_dir = Path(output_dir)
        self.nsi_script_path = self.output_dir / f"{app_name}.nsi"
        self.installer_exe_path = self.output_dir / f"{app_name}_installer.exe"
        
    def generate_nsi_script(self, files_to_install: list, target_install_dir: str) -> str:
        """Generates a basic NSIS script."""
        script = f"""
!define APPNAME "{self.app_name}"
!define APPVERSION "{self.version}"

OutFile "{self.installer_exe_path}"
InstallDir "{target_install_dir}"

Section "Install"
  SetOutPath $INSTDIR
"""
        for file in files_to_install:
            script += f'  File "{file}"\n'
            
        script += """
  WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\\uninstall.exe"
"""
        for file in files_to_install:
            filename = os.path.basename(file)
            script += f'  Delete "$INSTDIR\\{filename}"\n'
            
        script += """
  RMDir "$INSTDIR"
SectionEnd
"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.nsi_script_path.write_text(script)
        return str(self.nsi_script_path)

    def compile_nsis(self):
        """Compiles the NSI script into an exe using makensis (if available)."""
        makensis_path = r"C:\\Program Files (x86)\\NSIS\\makensis.exe"
        if not os.path.exists(makensis_path):
            raise FileNotFoundError("makensis.exe not found. Cannot build real installer.")
        
        result = subprocess.run([makensis_path, str(self.nsi_script_path)], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"NSIS Compilation failed:\\n{result.stderr}")
        return str(self.installer_exe_path)
