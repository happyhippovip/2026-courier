import sys, time
from courier_core.provider_cli_guard import *
S = [
 # bypass candidates (should hit)
 'git status; codex exec "x"',
 '& "C:\\Program Files\\nodejs\\codex.cmd" exec hi',
 '& codex exec hi',
 'Start-Process codex -ArgumentList "exec"',
 'Start-Process -FilePath codex',
 'cmd /c "codex exec hi"',
 'powershell -NoProfile -Command "claude -p hi"',
 'if ($true) { claude -p hi }',
 'Get-ChildItem | ForEach-Object { gemini -p $_ }',
 'foreach ($f in $files) { codex exec $f }',
 '$out = claude -p "hi"',
 '$out = & claude -p "hi"',
 'Write-Output (codex exec hi)',
 'claude -p hi > out.txt',
 'npx @anthropic-ai/claude-code -p hi',
 'npx -y @openai/codex exec hi',
 'npm exec -- @openai/codex exec',
 'bunx @google/gemini-cli',
 'pwsh -c claude -p hi',
 'sudo -E codex',
 'env -i PATH=/usr/bin codex',
 'xargs -n1 codex < list',
 'watch codex',
 'git commit -m "x" && codex',
 'Invoke-Expression "codex exec hi"',
 'iex "claude -p hi"',
 '. codex',
 'C:/Users/me/AppData/Roaming/npm/codex.ps1 exec',
 'start "" codex',
 'start /b codex',
 'cmd.exe /S /C "codex exec"',
 'codex.CMD exec',
 '"codex" exec',
 'ssh host codex',
 'wsl codex exec',
 'wsl -e codex',
 'bash -lc "codex exec"',
 'time codex',
 'strace codex',
 'gemini.exe',
 'claude-code',
 'cursor-agent',
 'gh copilot suggest x',
 'npx --yes -p @anthropic-ai/claude-code claude',
 'python -c "import subprocess; subprocess.run([\'codex\',\'exec\'])"',
 'python -c "import os; os.system(\'claude -p hi\')"',
 'node -e "require(\'child_process\').execSync(\'codex exec\')"',
 '$env:X=1; codex',
 'set X=1 && codex',
 # false positives (should be None)
 'git commit -m "fix codex adapter; claude docs"',
 'git commit -m "codex & claude"',
 'echo "use claude (later)"',
 'echo codex',
 'Write-Host "running codex"',
 'grep -r claude .',
 'grep -r "codex|claude" .',
 'cat C:\\work\\codex\\notes.txt',
 'cd C:\\Users\\me\\.codex; dir',
 'python -c "print(\'claude\')"',
 'python -c "names=[\'codex\',\'claude\']"',
 'python -c "d={\'agent\': \'claude\'}"',
 'pytest -k "codex and not claude"',
 'git log --grep="amp (fix)"',
 'Select-String -Pattern "codex" -Path *.py',
 'git checkout -b feat/codex',
 'echo $(date) codex',
 'echo "a; claude"',
 'echo \'a; claude\'',
 'git commit -m "x; codex: tidy"',
 'Get-Content "C:\\Program Files\\codex\\log.txt"',
 'rg "\\bgoose\\b" src',
 'echo hi & echo amp',
 'git commit -m "(goose) fix"',
 'echo "`ncodex"',
 'mkdir amp',
]
for s in S:
    try:
        print(repr(provider_in_script(s)).ljust(30), s)
    except Exception as e:
        print("EXC", type(e).__name__, e, s)
print("--- argv")
A = [["git","commit","-m","fix; codex"],["sh","-c","echo codex"],["bash","-c","git commit -m 'x; claude'"],
     ["python","-c","x='codex'"],["python","-c","print(\"claude -p\")"],[""],[],["env"],["timeout"],["npx"],["cmd","/c"],
     ["powershell","-Command"],["env","-S"],["sudo","-u"],["python","-c"],["cmd","/C","echo","codex & dir"],
     ["git","commit","-m","x && codex"],["powershell","-Command","Write-Host 'a; claude'"],
     ["cmd","/c","echo","a","&","codex"], ["xargs","codex"],["time","-p","codex"],["nice","-10","codex"],["timeout","--preserve-status","5","codex"],
     ["pwsh","-NoLogo","-File","x.ps1"],["powershell","Get-Date;","claude"],["cmd","/c","git commit -m \"a & claude\""]]
for a in A:
    try: print(repr(provider_in_argv(a)).ljust(30), a)
    except Exception as e: print("EXC", type(e).__name__, e, a)
print("--- odd")
for s in ['"'*1001, "'unbalanced codex", '(' * 5000 + 'codex', 'sh -c "'*50 + 'codex', '\x00codex', None, 123, "&&&&", "$($($(codex)))"]:
    t=time.time()
    try: r = provider_in_script(s)
    except Exception as e: r = "EXC %s %s" % (type(e).__name__, e)
    print(repr(r)[:60], repr(s)[:40], round(time.time()-t,3))
t=time.time()
try: print(provider_in_argv(["sh","-c"]*500+["codex"]))
except Exception as e: print("EXC",type(e).__name__)
for a in [[None],[b"codex"],["@"],["@/"],["-"],["="],["x=y"]]:
    try: print(provider_in_argv(a), a)
    except Exception as e: print("EXC", type(e).__name__, e, a)
print("--- env")
for n in ["OPENAI_API_KEY","github_token","Path","PWD","pwd","ApiKey","myApiKey","HF_TOKEN","NPM_TOKEN","SECRET_KEY_BASE","DATABASE_URL","PGPASSWORD","MYSQL_PWD","AUTHORITY","OAUTH","AUTH_HEADER","PASSPHRASE","SSH_PASSPHRASE","COURIER_SERVER_KEY","SERVER_KEY","APPDATA","USERPROFILE","SESSION","ACCESS_KEY_ID","AWSSECRET","PRIVATEKEY","KEYBOARD","PASS_THROUGH","BYPASS","COMPASS","TOKENIZERS_PARALLELISM","PATHEXT","HOMEPATH","HOMEDRIVE","LOGONSERVER","USERDOMAIN","ONEDRIVE","SystemRoot","ComSpec","HUGGING_FACE_HUB_TOKEN","GOOGLE_APPLICATION_CREDENTIALS","OLLAMA_HOST","MISTRAL_API_KEY","DEEPSEEK_API_KEY","OPENROUTER_API_KEY","GROQ_API_KEY","HF_HOME","CARGO_REGISTRY_TOKEN","BEARER","JWT","SESSIONID","CLIENT_ID","APP_PASSWORD","GIT_CREDENTIAL_HELPER","GCM_INTERACTIVE","SSL_KEY_FILE"]:
    print(n.ljust(30), is_credential_name(n), is_login_pointer(n))
for v in ["http://u:p@proxy:8080","http://user@proxy","https://tok@github.com/x","postgres://u:p@h/db","C:\\a:b@c","git@github.com:x/y","http://:p@h","http://u:p%40x@h"]:
    print(v.ljust(30), has_userinfo(v))
