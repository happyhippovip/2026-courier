"""Tripwire: would this command start a provider CLI, and which environment may a child see?

A provider CLI (codex, claude, gemini, agy, ...) spends a subscription quota whose per-run cost is
not verified (founder decision 23.10), so it runs only through ``provider_exec`` and its cost gate.
``local_shell`` and the Windows worker's PowerShell instructions use this module to refuse such a
command before anything starts.

It looks for a provider program where a program runs: the command itself, the command behind a
wrapper (env, sudo, timeout, npx, uv run, ...), the commands of an inline script (sh -c, cmd /c,
powershell -Command, iex) and string literals that start a program in inline code (python -c,
node -e). A provider word anywhere else (a commit message, a path, an argument) is not a hit.

This is a tripwire, not a sandbox. Renamed or linked binaries, shell variables, string
concatenation and script files are not seen; the other layers are the metered cost class, an
empty home folder and a child environment without credentials or login pointers.
"""

from __future__ import annotations

import re
from typing import Sequence

PROVIDER_CLIS = frozenset({
    "codex", "claude", "gemini", "agy", "antigravity", "grok", "cursor-agent", "openai", "aider",
    "chatgpt", "copilot", "opencode", "qwen", "amp", "goose",
})
_SUFFIXES = ("-cli", "-code", "-ai")
_EXTENSIONS = (".exe", ".cmd", ".bat", ".ps1", ".com")

# wrapper -> options that take a value (the value is not the program)
_WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D", "--user", "--group"},
    "doas": {"-u", "-C"},
    "timeout": {"-k", "-s", "--kill-after", "--signal"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p"},
    "nohup": set(), "setsid": set(), "stdbuf": set(), "time": set(), "exec": set(), "command": set(),
    "chronic": set(), "unbuffer": set(), "caffeinate": set(), "call": set(),
    "start": {"/d"},
    "wsl": {"-d", "--distribution", "-u", "--user", "--cd"},
    "xargs": {"-a", "-I", "-i", "-n", "-P", "-d", "-E", "-L", "-s", "--arg-file", "--max-args", "--max-procs"},
    "start-process": {"-argumentlist", "-workingdirectory", "-verb", "-windowstyle", "-redirectstandardoutput",
                      "-redirectstandarderror", "-redirectstandardinput", "-credential"},
    "saps": {"-argumentlist", "-workingdirectory", "-verb", "-windowstyle"},
}
_PACKAGE_RUNNERS = {"npx", "bunx", "pnpx", "uvx"}
_TWO_WORD_RUNNERS = {("uv", "run"), ("uv", "tool"), ("pipx", "run"), ("npm", "exec"), ("npm", "x"),
                     ("pnpm", "dlx"), ("pnpm", "exec"), ("yarn", "dlx"), ("yarn", "exec"), ("bun", "x")}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "busybox"}
_INTERPRETER_INLINE = {"node": {"-e", "-p", "--eval", "--print"}, "deno": {"eval"}, "bun": {"-e", "--eval"},
                       "perl": {"-e", "-E"}, "ruby": {"-e"}, "php": {"-r"}}
_PS_VALUE_OPTIONS = {"-executionpolicy", "-ep", "-ex", "-workingdirectory", "-wd", "-configurationname",
                     "-outputformat", "-of", "-inputformat", "-if", "-windowstyle", "-w", "-version", "-v"}
_MAX_INPUT = 64 * 1024        # longer commands are refused instead of scanned (no worker stall)
_NAMES = "|".join(sorted((re.escape(n) for n in PROVIDER_CLIS), key=len, reverse=True))
_CODE_LITERAL = re.compile(r"""["']\s*(?:[^"'\s]*[/\\])?(""" + _NAMES + r""")(?:\.(?:exe|cmd|bat|ps1))?(?=[\s"'])""",
                           re.IGNORECASE)
_MAX_DEPTH = 6


def _program(token: str) -> str:
    """Normalised program or package name: basename, lower case, no extension, no @version."""
    name = token.strip().strip("'\"").replace("\\", "/")
    scoped = name.startswith("@") and "/" in name
    name = name.rsplit("/", 1)[-1].lower()
    if "@" in name[1:] or (scoped and "@" in name):
        name = name.split("@", 1)[0] or name
    for ext in _EXTENSIONS:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _is_provider(name: str) -> bool:
    if name in PROVIDER_CLIS:
        return True
    return any(name.endswith(s) and name[: -len(s)] in PROVIDER_CLIS for s in _SUFFIXES)


def _after_options(argv: Sequence[str], i: int, with_value: set) -> int:
    """Index of the first non-option token from i (skipping VAR=value and option values)."""
    while i < len(argv):
        token = argv[i]
        lowered = token.lower()
        if token == "--":
            return i + 1
        if token.startswith("-") and len(token) > 1:
            i += 2 if (token in with_value or lowered in with_value) and "=" not in token else 1
            continue
        if "=" in token and not token.startswith(("/", ".", "$")):
            i += 1
            continue
        return i
    return i


def _short_cluster_with(token: str, letter: str) -> bool:
    return token.startswith("-") and not token.startswith("--") and token[1:].isalpha() and letter in token[1:]


def provider_in_argv(argv: Sequence[str], _depth: int = 0) -> str | None:
    """The provider CLI an argv would start (or a reason it cannot be checked), else None."""
    if _depth > _MAX_DEPTH:
        return "too deeply nested command"
    argv = [str(a) for a in argv]
    if sum(len(a) for a in argv) > _MAX_INPUT:
        return "command too long to check"
    i = _after_options(argv, 0, set())               # leading VAR=value assignments
    while i < len(argv):
        token = argv[i]
        prog = _program(token)
        if prog in (".", "&", "") or token.startswith("/") and argv[0].lower() in ("start", "start.exe") and i > 0:
            i += 1                                    # call operators, start's "" title and /b /min ...
            continue
        if token.startswith("$") and (token.endswith("=") or (i + 1 < len(argv) and argv[i + 1] == "=")):
            i += 1 if token.endswith("=") else 2      # PowerShell assignment: $out = <command>
            continue
        if token.startswith("$") and "=" in token:
            argv[i] = token.split("=", 1)[1]
            continue
        if _is_provider(prog):
            return prog
        nxt = argv[i + 1].lower() if i + 1 < len(argv) else ""
        if prog == "gh" and nxt == "copilot":
            return "copilot"
        if prog in _CONTROL_WORDS:
            i += 1                                    # if/then/do/else/while ... start a command
            continue
        if prog == "for":                             # sh: for x in ...; do cmd  /  cmd: for ... do cmd
            rest = [a.lower() for a in argv[i + 1:]]
            if "do" not in rest:
                return None
            i = i + 2 + rest.index("do")
            continue
        if prog == "if" and i + 1 < len(argv):
            i = _after_if_condition(argv, i + 1)
            continue
        if prog in _WRAPPERS:
            if prog == "env":
                for j, arg in enumerate(argv[i + 1:], start=i + 1):
                    if arg in ("-S", "--split-string") and j + 1 < len(argv):
                        return provider_in_script(argv[j + 1], "sh", _depth + 1)
                    if arg.startswith("--split-string="):
                        return provider_in_script(arg.split("=", 1)[1], "sh", _depth + 1)
                    if arg.startswith("-S") and len(arg) > 2:
                        return provider_in_script(arg[2:], "sh", _depth + 1)
            if prog in ("start-process", "saps"):
                for j, arg in enumerate(argv[i + 1:-1], start=i + 1):
                    if arg.lower() == "-filepath":
                        return provider_in_argv(argv[j + 1:j + 2], _depth + 1)
            i = _after_options(argv, i + 1, _WRAPPERS[prog])
            if prog == "timeout" and i < len(argv) and re.fullmatch(r"[0-9.]+[smhd]?", argv[i]):
                i += 1                                # the duration
            continue
        if prog in _PACKAGE_RUNNERS or (prog, nxt) in _TWO_WORD_RUNNERS:
            start = i + 1 if prog in _PACKAGE_RUNNERS else i + 2
            for j, arg in enumerate(argv[start:-1], start=start):
                if arg in ("-p", "--package") and _is_provider(_program(argv[j + 1])):
                    return _program(argv[j + 1])
                if arg in ("-c", "--call"):
                    return provider_in_script(argv[j + 1], "sh", _depth + 1)
            for arg in argv[start:]:
                if arg.startswith("--package=") and _is_provider(_program(arg.split("=", 1)[1])):
                    return _program(arg.split("=", 1)[1])
            i = _after_options(argv, start, {"-p", "--package", "--from", "--with", "-w"})
            continue
        if prog in _SHELLS:
            for j, arg in enumerate(argv[i + 1:-1], start=i + 1):
                if _short_cluster_with(arg, "c"):
                    return provider_in_script(argv[j + 1], "sh", _depth + 1)
            return None                               # a script file: not inspected
        if prog == "cmd":
            for j, arg in enumerate(argv[i + 1:], start=i + 1):
                if arg.lower().startswith(("/c", "/k")):
                    return provider_in_script(" ".join([arg[2:], *argv[j + 1:]]), "cmd", _depth + 1)
            return None
        if prog in ("powershell", "pwsh"):
            return _powershell(argv[i + 1:], _depth)
        if prog.startswith("python") or prog == "py":
            for j, arg in enumerate(argv[i + 1:-1], start=i + 1):
                if _short_cluster_with(arg, "c"):
                    return _in_code(argv[j + 1])
            return None
        if prog in _INTERPRETER_INLINE:
            for j, arg in enumerate(argv[i + 1:-1], start=i + 1):
                if arg in _INTERPRETER_INLINE[prog]:
                    return _in_code(argv[j + 1])
            return None
        if prog in ("iex", "invoke-expression"):
            return provider_in_script(" ".join(a.strip("'\"") for a in argv[i + 1:]), "ps", _depth + 1)
        return None
    return None


_CONTROL_WORDS = frozenset({"then", "do", "else", "elif", "while", "until", "!", "not"})
_CMD_COMPARE = frozenset({"equ", "neq", "lss", "leq", "gtr", "geq", "=="})


def _after_if_condition(argv: Sequence[str], i: int) -> int:
    """Index of the command after a cmd ``if`` condition; sh ``if cmd`` keeps the command."""
    while i < len(argv) and argv[i].lower() in ("/i", "not"):
        i += 1
    if i < len(argv) and argv[i].lower() in ("exist", "defined", "errorlevel", "cmdextversion"):
        return i + 2
    if i < len(argv) and "==" in argv[i]:
        return i + 1
    if i + 2 < len(argv) and argv[i + 1].lower() in _CMD_COMPARE:
        return i + 3
    return i


def _powershell(args: Sequence[str], depth: int) -> str | None:
    i = 0
    while i < len(args):
        lowered = args[i].lower()
        if lowered in ("-e", "-ec") or lowered.startswith("-enc"):
            return "powershell encoded command"      # cannot be read, so it is not run
        if lowered in ("-c", "-command", "-commandwithargs", "-cwa"):
            return provider_in_script(" ".join(args[i + 1:]), "ps", depth + 1)
        if lowered in ("-f", "-file"):
            return None                               # a script file: not inspected
        if lowered.startswith("-"):
            i += 2 if lowered in _PS_VALUE_OPTIONS else 1
            continue
        if lowered.endswith(".ps1"):
            return None
        return provider_in_script(" ".join(args[i:]), "ps", depth + 1)
    return None


def _in_code(code: str) -> str | None:
    match = _CODE_LITERAL.search(code)
    return match.group(1).lower() if match else None


class _TooDeep(Exception):
    pass


class _Unclear(Exception):
    """An unclosed substitution or here-string: what runs cannot be read."""


_ESCAPE = {"sh": "\\", "ps": "`", "cmd": "^"}
_HERE_END = {'"': re.compile(r'\r?\n[ \t]*"@'), "'": re.compile(r"\r?\n[ \t]*'@")}


def _closing_paren(text: str, start: int, dialect: str) -> int:
    """Index just past the ``)`` closing a ``$(`` whose content starts at ``start`` (quote-aware)."""
    level, quote, k, n, esc = 1, None, start, len(text), _ESCAPE[dialect]
    while k < n:
        ch = text[k]
        if ch == esc and quote != "'" and k + 1 < n:
            k += 2
            continue
        if quote is None and ch in "'\"":
            quote = ch
        elif quote is not None and ch == quote:
            quote = None
        elif quote is None and ch == "(":
            level += 1
        elif quote is None and ch == ")":
            level -= 1
            if level == 0:
                return k + 1
        k += 1
    raise _Unclear()


def _segments(text: str, dialect: str, depth: int = 0) -> list[list[str]]:
    """Simple commands of a script as token lists, read with the rules of its shell.

    ``dialect`` is ``sh`` (escape ``\\``, substitution ``$(...)`` and backticks), ``ps``
    (PowerShell: escape backtick, ``$(...)``, doubled quotes, here-strings) or ``cmd``
    (escape ``^``, no single quotes, no substitution). Separators split commands only
    outside quotes; a substitution runs even inside double quotes, so it becomes a command.
    """
    if depth > _MAX_DEPTH:
        raise _TooDeep()
    commands, tokens, word = [], [], []
    quote = None
    i, n, esc = 0, len(text), _ESCAPE[dialect]

    def end_word():
        if word:
            tokens.append("".join(word))
            word.clear()

    def end_command():
        end_word()
        if tokens:
            commands.append(list(tokens))
            tokens.clear()

    while i < n:
        ch = text[i]
        if ch == esc and quote != "'" and not (dialect == "cmd" and quote == '"'):
            if i + 1 < n:
                word.append(text[i + 1])
            i += 2
            continue
        if quote is None and (ch == '"' or (ch == "'" and dialect != "cmd")):
            if dialect == "ps" and text.startswith("@", i - 1) and i > 0 and re.match(r"[ \t]*\r?\n", text[i + 1:]):
                end = _HERE_END[ch].search(text, i + 1)
                if end is None:
                    raise _Unclear()
                body = text[i + 1:end.start()]
                if ch == '"':                          # an expandable here-string runs its $(...)
                    k = 0
                    while True:
                        k = body.find("$(", k)
                        if k < 0:
                            break
                        stop = _closing_paren(body, k + 2, dialect)
                        commands.extend(_segments(body[k + 2:stop - 1], dialect, depth + 1))
                        k = stop
                word.clear()
                word.append("@here")
                i = end.end()
                continue
            quote = ch
            i += 1
            continue
        if quote is not None and ch == quote:
            if dialect == "ps" and text.startswith(ch * 2, i):
                word.append(ch)                        # "" or '' inside a PowerShell string
                i += 2
                continue
            quote = None
            i += 1
            continue
        if dialect != "cmd" and quote != "'" and text.startswith("$(", i):
            stop = _closing_paren(text, i + 2, dialect)
            commands.extend(_segments(text[i + 2:stop - 1], dialect, depth + 1))
            word.append("$()")
            i = stop
            continue
        if dialect == "sh" and quote != "'" and ch == "`":
            k = i + 1
            while k < n and text[k] != "`":
                k += 2 if text[k] == "\\" else 1
            if k >= n:
                raise _Unclear()
            commands.extend(_segments(text[i + 1:k], dialect, depth + 1))
            word.append("$()")
            i = k + 1
            continue
        if quote is None:
            if text.startswith(("&&", "||"), i):
                end_command()
                i += 2
                continue
            if ch in ";\n\r|&(){}":
                end_command()
                i += 1
                continue
            if ch.isspace():
                end_word()
                i += 1
                continue
        word.append(ch)
        i += 1
    end_command()
    return commands


def provider_in_script(text: str, dialect: str = "ps", _depth: int = 0) -> str | None:
    """The provider CLI a script would start, else None. ``dialect``: ``ps``, ``sh`` or ``cmd``."""
    if _depth > _MAX_DEPTH:
        return "too deeply nested command"
    text = str(text or "")
    if len(text) > _MAX_INPUT:
        return "command too long to check"
    try:
        commands = _segments(text, dialect)
    except _TooDeep:
        return "too deeply nested command"
    except _Unclear:
        return "unclosed substitution or here-string"
    except RecursionError:
        return "too deeply nested command"
    for tokens in commands:
        hit = provider_in_argv(tokens, _depth + 1)
        if hit is not None:
            return hit
    return None


# ---- environment -----------------------------------------------------------------------------
_CREDENTIAL_SEGMENTS = frozenset({
    "KEY", "KEYS", "APIKEY", "TOKEN", "TOKENS", "SECRET", "SECRETS", "PASSWORD", "PASSWD", "PASS", "PWD",
    "COOKIE", "COOKIES", "CREDENTIAL", "CREDENTIALS", "AUTH", "DSN", "PAT", "PRIVATE", "PASSPHRASE",
    "PRIVATEKEY", "BEARER", "JWT", "SESSIONID",
})
_GLUED = ("APIKEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PASSPHRASE", "PRIVATEKEY", "SESSIONID")
_LOGIN_PREFIXES = ("CODEX_", "CLAUDE_", "ANTHROPIC_", "OPENAI_", "GEMINI_", "GOOGLE_", "XAI_", "GROK_", "CURSOR_",
                   "AGY_", "ANTIGRAVITY_", "COPILOT_", "AIDER_", "OPENCODE_", "QWEN_", "AWS_", "AZURE_", "GCP_",
                   "CLOUDSDK_", "GH_", "GITHUB_", "COURIER_")
_LOGIN_NAMES = frozenset({
    "GIT_ASKPASS", "SSH_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "NETRC", "DBUS_SESSION_BUS_ADDRESS",
    "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_PARAMETERS", "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR", "GNUPGHOME", "SSH_AUTH_SOCK", "KUBECONFIG", "DOCKER_CONFIG", "NODE_PATH", "NPM_CONFIG_USERCONFIG",
    "PIP_CONFIG_FILE",
})
_USERINFO = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s@]*@", re.IGNORECASE)


def is_credential_name(name: str) -> bool:
    """A variable whose name says it holds a secret (judged by name segments, not substrings)."""
    upper = str(name).upper()
    if upper in ("PWD", "OLDPWD"):
        return False
    for segment in re.split(r"[_.\-]+", upper):
        if segment in _CREDENTIAL_SEGMENTS:
            return True
        if any(segment.endswith(g) and len(segment) > len(g) for g in _GLUED):
            return True
    return False


def is_login_pointer(name: str) -> bool:
    """A variable that points a child at a login, credential helper or provider configuration."""
    upper = str(name).upper()
    return upper in _LOGIN_NAMES or upper.startswith(_LOGIN_PREFIXES)


def has_userinfo(value: str) -> bool:
    """A URL value with userinfo (``user:password@`` or ``token@``) in it (proxy, database, git)."""
    return bool(_USERINFO.search(str(value)))


def may_inherit(name: str, value: str) -> bool:
    """Whether a worker variable may be passed to an untrusted child at all."""
    return not (is_credential_name(name) or is_login_pointer(name) or has_userinfo(value))
