import subprocess
cmd = [
    "agy", 
    "-p", "test prompt",
    "--dangerously-skip-permissions"
]
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
stdout, stderr = process.communicate()
print("RC:", process.returncode)
print("STDOUT:", stdout)
print("STDERR:", stderr)
