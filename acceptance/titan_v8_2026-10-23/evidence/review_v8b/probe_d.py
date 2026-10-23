import sys, os
sys.path.insert(0, "scripts/windows_worker")
os.environ.setdefault("COURIER_API_KEY","x"); os.environ.setdefault("COURIER_SERVER","http://127.0.0.1:9")
import daemon as d
for t in ["npx -y @google/gemini-cli -p hi","co`dex exec hi","& ('co'+'dex') exec","iex ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('Y29kZXg=')))",
          "& \"$env:APPDATA\\npm\\codex.cmd\"","Start-Process CODEX.EXE","cmd /c codex","& 'C:\\tools\\cx.exe'","npm exec -- @github/copilot-cli","uvx llm 'hi'","ollama run x",
          "git commit -m 'fix codex bridge'","Write-Host \"agy done\"","Get-ChildItem C:\\src\\claude\\","Get-Content .\\claude-notes.md","pytest -k gemini_router","Fix defects reported in task-codex-12"]:
    sys.__stdout__.write(f"{t!r:60} -> {d._provider_cli_in(t)}\n")
os.environ.clear()
os.environ.update({"PATH":"x","SystemRoot":"C:\\Windows","USERPROFILE":"C:\\Users\\b","APPDATA":"a","HTTPS_PROXY":"http://u:p@h:1","MYSQL_PWD":"p","DATABASE_URL":"postgres://u:p@h/db",
 "GIT_ASKPASS":"x","AZURE_CLIENT_CERTIFICATE_PATH":"c","OPENAI_ORG_ID":"o","GH_ENTERPRISE_TOKEN":"t","SSH_AUTH_SOCK":"s","GIT_AUTHOR_NAME":"Bob","NETRC":"n","COURIER_API_KEY":"k","COURIER_SERVER":"http://s","CODEX_HOME":"c","ANTHROPIC_BASE_URL":"b","ApiKey":"k","PSModulePath":"p","SENTRY_DSN":"https://abc@o.ingest"})
sys.__stdout__.write(str(sorted(d._child_env()))+"\n")
