"""GUARD-1: shared tripwire against starting a provider CLI from local_shell or a PowerShell instruction.

A provider CLI spends a quota whose cost is not verified (founder decision 23.10), so it must go
through provider_exec and its cost gate. This is a tripwire, not a sandbox: renamed binaries, shell
variables or string concatenation are accepted limits; the other layers are the metered cost class,
an empty home folder and an environment without credentials.
"""
import sys

import pytest

from courier_core import provider_cli_guard as guard

PY = sys.executable

PROVIDER_ARGV = [
    ["codex", "exec", "hi"],
    ["/usr/local/bin/claude", "-p", "hi"],
    ["C:\\Tools\\gemini.cmd", "-p", "x"],
    [".\\codex.exe", "exec"],
    ["C:\\x\\CODEX.CMD"],
    ["agy.exe", "run"],
    ["/usr/bin/env", "claude", "-p", "hi"],
    ["env", "FOO=1", "-i", "codex", "exec"],
    ["env", "-S", "codex exec"],
    ["env", "--split-string=claude -p x"],
    ["timeout", "30s", "codex"],
    ["timeout", "-k", "5", "30", "codex"],
    ["sudo", "-u", "bob", "codex"],
    ["xargs", "-a", "f", "codex"],
    ["nice", "-n", "5", "gemini"],
    ["npx", "@openai/codex", "exec"],
    ["npx", "-y", "@anthropic-ai/claude-code", "-p", "x"],
    ["npx", "-y", "@google/gemini-cli"],
    ["npx", "--yes", "@github/copilot-cli"],
    ["npx", "codex@latest", "exec"],
    ["npx", "-p", "@google/gemini-cli", "gemini"],
    ["uv", "run", "codex"],
    ["uvx", "aider"],
    ["npm", "exec", "--", "codex"],
    ["pnpm", "dlx", "@openai/codex"],
    ["yarn", "dlx", "@google/gemini-cli"],
    ["bun", "x", "claude"],
    ["sh", "-c", "agy -p hi"],
    ["sh", "-ec", "agy -p hi"],
    ["bash", "-xc", "codex exec"],
    ["bash", "-lc", "cd /tmp && claude -p hi"],
    ["bash", "-c", "FOO=1 timeout 5 codex exec | tee o"],
    ["cmd", "/c", "codex exec x"],
    ["cmd.exe", "/S", "/C", "gemini -p x"],
    ["cmd", "/ccodex exec"],
    ["powershell", "-NoProfile", "-Command", "gemini -p x"],
    ["powershell", "codex exec"],
    ["pwsh", "-c", "& codex exec"],
    ["powershell", "-EncodedCommand", "YwBvAGQAZQB4AA=="],
    ["pwsh", "-enc", "YwBvAGQAZQB4AA=="],
    ["powershell", "-Command", "Start-Process gemini -ArgumentList '-p','x'"],
    ["powershell", "-Command", "iex 'codex exec x'"],
    [PY, "-c", "import subprocess; subprocess.run(['gemini', '-p', 'x'])"],
    [PY, "-Ic", "import os; os.system('codex exec x')"],
    ["python3.12", "-c", "import subprocess; subprocess.run('claude -p x', shell=True)"],
    ["py", "-3", "-c", "import subprocess; subprocess.run(['agy'])"],
    ["node", "-e", "require('child_process').execSync('codex exec x')"],
    ["node", "-p", "require('child_process').execSync('gemini')"],
    ["perl", "-E", "system('claude -p x')"],
    ["cursor-agent", "-p", "x"],
    ["opencode", "run"],
]


@pytest.mark.parametrize("argv", PROVIDER_ARGV)
def test_a_provider_cli_is_found(argv):
    assert guard.provider_in_argv(argv) is not None


ORDINARY_ARGV = [
    [PY, "-c", "open('out.txt', 'w').write('shell-made')"],
    [PY, "/repo/scripts/run_antigravity_bridge.py", "--job-file", "j.json"],
    ["grep", "-r", "claude", "docs"],
    ["git", "log", "--author", "codex-bot"],
    ["git", "commit", "-m", "fix codex bridge"],
    ["bash", "-c", "git commit -m 'fix codex bridge'"],
    ["bash", "-c", "ls src/copilot/ && echo agy done"],
    ["bash", "-c", "/opt/claude-tools/run.sh"],
    ["sh", "-c", "cat codex.txt"],
    [PY, "-c", "print('fix gemini adapter'); x = 'claudette'"],
    ["timeout", "5", "grep", "codex", "file"],
    ["sudo", "-u", "bob", "ls", "claude"],
    ["/opt/claude-tools/run.sh"],
    ["npx", "prettier", "--check", "codex.md"],
    ["powershell", "-Command", "Write-Host 'agy done'; Get-ChildItem C:\\src\\claude\\"],
    ["cmd", "/c", "echo codex"],
]


@pytest.mark.parametrize("argv", ORDINARY_ARGV)
def test_ordinary_commands_that_only_mention_a_provider_pass(argv):
    assert guard.provider_in_argv(argv) is None


@pytest.mark.parametrize("script", [
    "codex exec 'fix it'", "& 'C:\\Tools\\claude.exe' -p hi", "agy -p hi | Out-File o.txt",
    "npx @openai/codex exec x", "Start-Process gemini -ArgumentList '-p','x'",
    "Write-Host x; codex exec", "if ($true) { claude -p x }", "powershell -enc YwBvAGQAZQB4AA==",
    "cmd /c codex exec", ". C:\\bin\\gemini.ps1",
])
def test_a_provider_cli_in_a_powershell_instruction_is_found(script):
    assert guard.provider_in_script(script) is not None


@pytest.mark.parametrize("script", [
    "Write-Host 'claudette and geminid'", "git commit -m 'fix codex bridge'", "Write-Host \"agy done\"",
    "Get-ChildItem C:\\src\\claude\\", "Copy-Item codex.txt out.txt", "echo ok",
])
def test_ordinary_powershell_instructions_pass(script):
    assert guard.provider_in_script(script) is None


@pytest.mark.parametrize("name", ["OPENAI_API_KEY", "GITHUB_TOKEN", "github_token", "Db_Password", "X_SECRET",
                                  "AUTH_COOKIE", "SSH_AUTH_SOCK", "MYSQL_PWD", "AWS_SECRET_ACCESS_KEY", "APIKEY",
                                  "SOME_CREDENTIALS", "SENTRY_DSN", "GH_PAT", "COURIER_API_KEY", "MY_ACCESSTOKEN"])
def test_credential_names(name):
    assert guard.is_credential_name(name)


@pytest.mark.parametrize("name", ["GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "KEYBOARD_LAYOUT", "PWD", "OLDPWD", "PATH",
                                  "HOME", "AUTHOR", "MONKEY_PATCH", "TOKENIZERS_PARALLELISM"])
def test_not_credential_names(name):
    assert not guard.is_credential_name(name)


@pytest.mark.parametrize("value,secret", [("http://u:p@proxy:8080", True), ("https://user:@h", True),
                                          ("postgres://a:b@db/x", True), ("http://proxy:8080", False),
                                          ("C:\\Windows", False), ("user@example.com", False)])
def test_values_with_userinfo(value, secret):
    assert guard.has_userinfo(value) is secret


def test_provider_config_names_are_login_pointers():
    for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "GEMINI_CLI_HOME", "GIT_ASKPASS", "GIT_SSH_COMMAND", "NETRC",
                 "DBUS_SESSION_BUS_ADDRESS", "GIT_CONFIG_GLOBAL", "ANTHROPIC_BASE_URL"):
        assert guard.is_login_pointer(name), name
    for name in ("PATH", "TEMP", "LANG", "GIT_AUTHOR_NAME"):
        assert not guard.is_login_pointer(name), name


# Review v8c
@pytest.mark.parametrize("script", [
    'python -c "import os; os.system(\'claude -p hi\')"',
    'python -c "import subprocess; subprocess.run([\'codex\', \'exec\'])"',
    'node -e "require(\'child_process\').execSync(\'codex exec\')"',
    "$out = claude -p hi",
    "$out=codex exec",
    'start "" codex',
    "start /b codex exec",
    "wsl codex exec",
    "wsl -d Ubuntu -- claude -p x",
    "gh copilot suggest x",
    'echo "$(codex exec)"',
])
def test_review_v8c_bypasses_are_found(script):
    assert guard.provider_in_script(script) is not None


def test_sh_backticks_are_command_substitution():
    assert guard.provider_in_script("echo `claude -p x`", "sh") is not None
    assert guard.provider_in_argv(["sh", "-c", "echo `claude -p x`"]) is not None


@pytest.mark.parametrize("script", [
    'git commit -m "fix codex adapter; claude docs"',
    'echo "a; claude"',
    'grep -r "codex\\|claude" src',
    'git commit -m "(goose) fix"',
    "echo $(date) codex",
    "Write-Host 'a; claude'",
    'cmd /c "git commit -m a"',
])
def test_review_v8c_quoted_separators_are_not_commands(script):
    assert guard.provider_in_script(script) is None


@pytest.mark.parametrize("argv", [
    ["bash", "-c", "git commit -m 'x; claude'"],
    ["powershell", "-Command", "Write-Host 'a; claude'"],
])
def test_review_v8c_quoted_separators_in_argv(argv):
    assert guard.provider_in_argv(argv) is None


def test_overlong_input_is_refused_quickly():
    import time
    started = time.monotonic()
    assert guard.provider_in_script("A" * 2_000_000) is not None          # fail closed, not a stall
    assert guard.provider_in_argv(["sh", "-c", "x" * 2_000_000]) is not None
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("value", ["https://ghp_x@github.com/o/r", "http://:p@h", "git+https://tok@host/x"])
def test_token_only_userinfo(value):
    assert guard.has_userinfo(value)


@pytest.mark.parametrize("name", ["GPG_PASSPHRASE", "SSH_PRIVATEKEY", "API_BEARER", "MY_JWT", "APP_SESSIONID"])
def test_more_credential_names(name):
    assert guard.is_credential_name(name)


@pytest.mark.parametrize("text", ["(" * 5000 + "x", ")" * 5000, 'a"b', "'''", "$(" * 3000, "`" * 1001, "\x00", "",
                                  "echo $(echo $(echo $(echo $(echo $(echo $(echo $(echo hi)))))))"])
def test_odd_input_never_raises(text):
    guard.provider_in_script(text)
    guard.provider_in_argv(["sh", "-c", text])
    guard.provider_in_argv([text])


# Review v8d: one scanner per shell dialect
@pytest.mark.parametrize("script,dialect", [
    ('Write-Host "x`""; codex', "ps"), ("Write-Host `\"; codex", "ps"),
    ('echo "x\\"" ; codex', "sh"), ('echo \\"; codex', "sh"),
    ('$t = @"\nsay "hi\n"@\ncodex exec', "ps"), ("$t = @'\nit's\n'@\ncodex exec", "ps"),
    ('$t = @"\n$(claude -p x)\n"@', "ps"),
    ("for i in 1; do codex; done", "sh"), ("if true; then codex; fi", "sh"), ("while true; do claude; done", "sh"),
    ("for %f in (a) do codex", "cmd"), ("if exist x codex exec", "cmd"), ("if not exist x gemini", "cmd"),
    ("if /i a==b claude -p x", "cmd"), ('x=$(echo ")"); codex', "sh"), ("echo ^\" & codex", "cmd"),
    ("$(codex", "sh"), ("echo `codex", "sh"), ('$t = @"\nno end', "ps"),
])
def test_dialect_rules_find_the_command(script, dialect):
    assert guard.provider_in_script(script, dialect) is not None


@pytest.mark.parametrize("script,dialect", [
    ('Write-Host "a`"; codex"', "ps"), ('echo "a\\"; codex"', "sh"), ("echo a ^& codex", "cmd"),
    ('Write-Host "line`nnext"', "ps"), ("$t = @'\n$(codex)\n'@", "ps"), ("if exist codex.txt type codex.txt", "cmd"),
    ("if grep -q codex f; then echo ok; fi", "sh"),
])
def test_dialect_rules_do_not_invent_a_command(script, dialect):
    assert guard.provider_in_script(script, dialect) is None


def test_balanced_deep_substitution_fails_closed():
    text = "$(" * 2000 + "x" + ")" * 2000
    assert guard.provider_in_script(text, "sh") is not None
    assert guard.provider_in_script("$(" * 20 + "x" + ")" * 20, "sh") == "too deeply nested command"
