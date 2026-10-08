#!/bin/bash
# Courier host setup for macOS.
#
# One line in Terminal (normal user, no admin):
#   curl -fsSL https://raw.githubusercontent.com/happyhippovip/2026-courier/lane/L6-host-setup/scripts/setup/courier-setup.sh | bash
# Flags go after "bash -s --":
#   ... | bash -s -- --check        doctor only, writes nothing
#   ... | bash -s -- --with-godot   also install Godot 4 into ~/Applications
#   ... | bash -s -- --uninstall    delegate to scripts/mac_worker/uninstall.sh
#
# Safe to run again. It never elevates, never stops a process, never deletes,
# stashes, resets or cleans anything, and never reads credentials. A checkout
# with local changes or another branch is left alone; a fresh sibling clone is
# used instead. Unknown state fails closed with a message.
#
# Exit codes: 0 HOST READY, 2 HOST PARTIAL, 3 HOST BLOCKED, 64 usage error.
#
# Everything lives in functions and the last line calls them, so bash has read
# the whole file before anything runs when the script arrives through a pipe.
# Nothing depends on $0 or on the script's directory.

set -u

CS_VERSION="1"
CS_REPO_URL="${COURIER_REPO_URL:-https://github.com/happyhippovip/2026-courier.git}"
CS_BRANCH="${COURIER_BRANCH:-integration/v1}"
CS_LABEL="com.courier.mac_worker"
CS_MAX_HEAVY_BUILDERS=1
CS_MIN_SWAP_FREE_MB=1024
CS_MIN_FREE_RAM_MB=2048
CS_MIN_DISK_FREE_MB=10240

cs_usage() {
  cat <<'USAGE'
Courier host setup (macOS)
  --check       doctor only; changes nothing
  --with-godot  also install Godot 4 (Homebrew cask into ~/Applications)
  --uninstall   remove the Courier launchd job via scripts/mac_worker/uninstall.sh
  --help        this text
USAGE
}

cs_is_int() {
  case "${1:-}" in
    ''|*[!0-9]*) return 1 ;;
  esac
  return 0
}

cs_note() { CS_NOTES="${CS_NOTES}- $*
"; }
cs_action() { CS_ACTIONS="${CS_ACTIONS}- $*
"; }
cs_next() { CS_NEXT="${CS_NEXT}- $*
"; }
cs_partial() { if [ "$CS_STATUS" = "READY" ]; then CS_STATUS="PARTIAL"; fi; }
cs_blocked() { CS_STATUS="BLOCKED"; }
cs_say() { printf '%s\n' "$*" >&2; }

# Literal substring test on a file, without the grep family.
cs_file_contains() {
  [ -f "$1" ] || return 1
  awk -v m="$2" 'index($0, m) { found = 1; exit } END { exit found ? 0 : 1 }' "$1" 2>/dev/null
}

# Home-relative display path. Never prints the real home directory.
# shellcheck disable=SC2088  # a literal tilde is the point
cs_tilde() {
  case "$1" in
    "$HOME") printf '~' ;;
    "$HOME"/*) printf '~/%s' "${1#"$HOME"/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

cs_sha12() {
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum -a 256 | cut -c1-12
  elif command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | cut -c1-12
  else
    printf 'unknown'
  fi
}

# Replace every literal occurrence of identifying strings and anything shaped
# like a credential. Applied to the whole report before it is shown, written
# or copied.
cs_redact() {
  awk -v h="$HOME" -v u="${USER:-}" -v n1="$CS_HOST_FULL" -v n2="$CS_HOST_SHORT" -v n3="$CS_HOST_NAME" '
    function rep(s, f, r,   out, i) {
      if (length(f) < 2) return s
      out = ""
      while ((i = index(s, f)) > 0) { out = out substr(s, 1, i - 1) r; s = substr(s, i + length(f)) }
      return out s
    }
    BEGIN {
      c = "[A-Za-z0-9_-]"; long = c c c c c c c c c c c c c c c c
      re_sk = "sk-" long "+"
    }
    {
      line = $0
      line = rep(line, h, "~")
      line = rep(line, n1, "<host>"); line = rep(line, n2, "<host>"); line = rep(line, n3, "<host>")
      gsub(/\/Users\/[^\/ ]+/, "/Users/<user>", line)
      gsub(/\/home\/[^\/ ]+/, "/home/<user>", line)
      gsub(/gh[pousr]_[A-Za-z0-9]+/, "<token>", line)
      gsub(/github_pat_[A-Za-z0-9_]+/, "<token>", line)
      gsub(re_sk, "<token>", line)
      gsub(/[Bb]earer [A-Za-z0-9._~+\/=-]+/, "Bearer <token>", line)
      gsub(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z][A-Za-z]+/, "<email>", line)
      if (length(u) >= 2) line = rep(line, u, "<user>")
      print line
    }'
}

# Keep tool output to one short printable line.
cs_oneline() {
  head -n 1 | tr -cd '[:print:]' | cut -c1-60
}

cs_find_brew() {
  CS_BREW=""
  if command -v brew >/dev/null 2>&1; then
    CS_BREW="$(command -v brew)"
  elif [ -x /opt/homebrew/bin/brew ]; then
    CS_BREW="/opt/homebrew/bin/brew"
  elif [ -x /usr/local/bin/brew ]; then
    CS_BREW="/usr/local/bin/brew"
  fi
}

cs_brew_install() {
  # No auto-update and no cleanup: cleanup would delete old versions.
  HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_ENV_HINTS=1 \
    "$CS_BREW" install "$@" </dev/null >/dev/null 2>&1
}

cs_detect_git() {
  CS_GIT="missing"; CS_GIT_VER=""
  local g
  g="$(command -v git 2>/dev/null || true)"
  [ -n "$g" ] || return 0
  if [ "$g" = "/usr/bin/git" ] && command -v xcode-select >/dev/null 2>&1; then
    # /usr/bin/git is a stub that opens an install dialog without the tools.
    xcode-select -p >/dev/null 2>&1 || return 0
  fi
  CS_GIT_VER="$(git --version 2>/dev/null | awk '{print $3}' | cs_oneline)"
  [ -n "$CS_GIT_VER" ] && CS_GIT="yes"
  return 0
}

cs_detect_python() {
  CS_PY=""; CS_PY_VER="missing"
  local c v p
  for c in python3.12 python3; do
    p="$(command -v "$c" 2>/dev/null || true)"
    [ -n "$p" ] || continue
    v="$("$p" --version 2>&1 | cs_oneline)"
    case "$v" in
      "Python 3.12"*) CS_PY="$p"; CS_PY_VER="${v#Python }"; return 0 ;;
    esac
  done
  if [ -n "$CS_BREW" ]; then
    p="$(dirname "$CS_BREW")/python3.12"
    if [ -x "$p" ]; then
      CS_PY="$p"; CS_PY_VER="$("$p" --version 2>&1 | cs_oneline)"; CS_PY_VER="${CS_PY_VER#Python }"
    fi
  fi
  return 0
}

cs_detect_tools() {
  cs_detect_git
  cs_detect_python
  CS_GH="no"; CS_GH_AUTH="no"
  if command -v gh >/dev/null 2>&1; then
    CS_GH="yes"
    # Exit status only; the output may name the account and is discarded.
    if gh auth status >/dev/null 2>&1; then CS_GH_AUTH="yes"; fi
  fi
  CS_MUSE="missing"
  if command -v muse >/dev/null 2>&1; then
    CS_MUSE="$(muse --version 2>/dev/null | cs_oneline)"
    [ -n "$CS_MUSE" ] || CS_MUSE="present (version unknown)"
  fi
  CS_AGY="no"
  command -v agy >/dev/null 2>&1 && CS_AGY="yes"
  CS_GODOT="no"
  if command -v godot >/dev/null 2>&1 || [ -d "$HOME/Applications/Godot.app" ] || [ -d "/Applications/Godot.app" ]; then
    CS_GODOT="yes"
  fi
}

cs_detect_host() {
  CS_OS_VER="$(sw_vers -productVersion 2>/dev/null | cs_oneline)"; [ -n "$CS_OS_VER" ] || CS_OS_VER="unknown"
  CS_ARCH="$(uname -m 2>/dev/null | cs_oneline)"; [ -n "$CS_ARCH" ] || CS_ARCH="unknown"
  CS_CPU="$(sysctl -n machdep.cpu.brand_string 2>/dev/null | cs_oneline)"; [ -n "$CS_CPU" ] || CS_CPU="unknown"
  CS_NCPU="$(sysctl -n hw.ncpu 2>/dev/null | cs_oneline)"; cs_is_int "$CS_NCPU" || CS_NCPU="unknown"

  CS_RAM_MB="unknown"; CS_FREE_RAM_MB="unknown"
  local mem pct swap total free disk
  mem="$(sysctl -n hw.memsize 2>/dev/null | cs_oneline)"
  if cs_is_int "$mem"; then CS_RAM_MB=$((mem / 1048576)); fi
  pct="$(memory_pressure 2>/dev/null | sed -n 's/.*System-wide memory free percentage: *\([0-9][0-9]*\)%.*/\1/p' | head -n 1)"
  if cs_is_int "$pct" && cs_is_int "$CS_RAM_MB"; then CS_FREE_RAM_MB=$((CS_RAM_MB * pct / 100)); fi

  CS_SWAP_TOTAL_MB="unknown"; CS_SWAP_FREE_MB="unknown"
  swap="$(sysctl -n vm.swapusage 2>/dev/null | head -n 1)"
  total="$(printf '%s' "$swap" | sed -n 's/.*total = *\([0-9][0-9]*\)[.0-9]*M.*/\1/p')"
  free="$(printf '%s' "$swap" | sed -n 's/.*free = *\([0-9][0-9]*\)[.0-9]*M.*/\1/p')"
  cs_is_int "$total" && CS_SWAP_TOTAL_MB="$total"
  cs_is_int "$free" && CS_SWAP_FREE_MB="$free"

  CS_DISK_FREE_MB="unknown"
  disk="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print int($4 / 1024)}')"
  cs_is_int "$disk" && CS_DISK_FREE_MB="$disk"
}

cs_count_processes() {
  # Count only. Our own shell is excluded; nothing is signalled.
  CS_PROCS="$(ps -axo pid=,command= 2>/dev/null | awk -v me="$$" '
    $1 == me { next }
    /courier-setup/ { next }
    /mac_worker\/daemon\.py|muse_supervisor|macos_muse_night|courier_(worker|runtime|hub)|run_autonomous_loop|deploy\/run-supervisor/ { n++ }
    END { print n + 0 }')"
  cs_is_int "$CS_PROCS" || CS_PROCS="unknown"
}

cs_is_protected_path() {
  case "$1" in
    "$HOME/Desktop"|"$HOME/Desktop/"*|"$HOME/Documents"|"$HOME/Documents/"*|"$HOME/Downloads"|"$HOME/Downloads/"*) return 0 ;;
  esac
  return 1
}

cs_count_dirty() {
  # Dirty worktrees of checkouts under ~/Courier, count only. Worktrees inside
  # Desktop, Documents or Downloads are skipped to avoid privacy prompts.
  CS_DIRTY=0; CS_DIRTY_SKIPPED=0
  [ "$CS_GIT" = "yes" ] || { CS_DIRTY="unknown"; return 0; }
  [ -d "$CS_BASE" ] || return 0
  local d wt
  for d in "$CS_BASE"/*; do
    [ -d "$d" ] || continue
    [ -e "$d/.git" ] || continue
    while IFS= read -r wt; do
      [ -n "$wt" ] || continue
      if cs_is_protected_path "$wt"; then CS_DIRTY_SKIPPED=$((CS_DIRTY_SKIPPED + 1)); continue; fi
      [ -d "$wt" ] || continue
      if [ -n "$(git -C "$wt" status --porcelain 2>/dev/null | head -n 1)" ]; then
        CS_DIRTY=$((CS_DIRTY + 1))
      fi
    done <<EOF_WT
$(git -C "$d" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
EOF_WT
  done
}

# One of: ABSENT OK DIRTY FOREIGN_BRANCH FOREIGN_REMOTE NOT_GIT SYMLINK UNREADABLE
cs_repo_inspect() {
  local d="$1" url br st
  if [ -L "$d" ]; then echo SYMLINK; return 0; fi
  if [ ! -e "$d" ]; then echo ABSENT; return 0; fi
  if [ ! -d "$d/.git" ]; then echo NOT_GIT; return 0; fi
  url="$(git -C "$d" config --get remote.origin.url 2>/dev/null || true)"
  case "$url" in
    "$CS_REPO_URL"|*github.com/happyhippovip/2026-courier|*github.com/happyhippovip/2026-courier.git|*github.com:happyhippovip/2026-courier.git) ;;
    *) echo FOREIGN_REMOTE; return 0 ;;
  esac
  br="$(git -C "$d" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ "$br" != "$CS_BRANCH" ]; then echo FOREIGN_BRANCH; return 0; fi
  if ! st="$(git -C "$d" status --porcelain 2>/dev/null)"; then echo UNREADABLE; return 0; fi
  if [ -n "$st" ]; then echo DIRTY; return 0; fi
  echo OK
}

cs_clone() {
  local d="$1"
  if GIT_TERMINAL_PROMPT=0 git clone --quiet --branch "$CS_BRANCH" --single-branch "$CS_REPO_URL" "$d" </dev/null >/dev/null 2>&1; then
    cs_action "cloned $CS_BRANCH into $(cs_tilde "$d")"
    CS_REPO_DIR="$d"; CS_REPO_STATE="CLONED"
    return 0
  fi
  cs_note "clone into $(cs_tilde "$d") failed (network or access)"
  return 1
}

# Fast-forward only, and only on a clean checkout of the right branch.
# Returns 1 when local commits would block a fast-forward.
cs_update() {
  local d="$1"
  if ! GIT_TERMINAL_PROMPT=0 git -C "$d" fetch --quiet origin "$CS_BRANCH" </dev/null >/dev/null 2>&1; then
    cs_note "$(cs_tilde "$d"): fetch failed; using the checkout as it is"
    CS_REPO_DIR="$d"; CS_REPO_STATE="STALE"
    return 0
  fi
  if [ "$(git -C "$d" rev-parse HEAD 2>/dev/null)" = "$(git -C "$d" rev-parse FETCH_HEAD 2>/dev/null)" ]; then
    CS_REPO_DIR="$d"; CS_REPO_STATE="UP_TO_DATE"
    return 0
  fi
  if ! git -C "$d" merge-base --is-ancestor HEAD FETCH_HEAD 2>/dev/null; then
    cs_note "$(cs_tilde "$d"): has local commits; left untouched"
    return 1
  fi
  if git -C "$d" merge --ff-only --quiet FETCH_HEAD </dev/null >/dev/null 2>&1; then
    cs_action "fast-forwarded $(cs_tilde "$d")"
    CS_REPO_DIR="$d"; CS_REPO_STATE="UPDATED"
    return 0
  fi
  cs_note "$(cs_tilde "$d"): fast-forward failed; left untouched"
  return 1
}

cs_repo_step() {
  CS_REPO_DIR=""; CS_REPO_STATE="NONE"
  local cand state
  for cand in "$CS_BASE/2026-courier" "$CS_BASE/2026-courier-host"; do
    state="$(cs_repo_inspect "$cand")"
    case "$state" in
      OK)
        if [ "$CS_MODE" = "check" ]; then
          CS_REPO_DIR="$cand"; CS_REPO_STATE="OK (update not attempted in --check)"
          return 0
        fi
        cs_update "$cand" && return 0
        ;;
      ABSENT)
        if [ "$CS_MODE" = "check" ]; then
          CS_REPO_STATE="WOULD_CLONE into $(cs_tilde "$cand")"
          return 0
        fi
        cs_clone "$cand" && return 0
        cs_blocked
        return 1
        ;;
      *)
        cs_note "$(cs_tilde "$cand"): $state; left untouched"
        ;;
    esac
  done
  cand="$CS_BASE/2026-courier-host-$(date -u '+%Y%m%dT%H%M%SZ')"
  if [ "$CS_MODE" = "check" ]; then
    CS_REPO_STATE="WOULD_CLONE into a fresh sibling"
    return 0
  fi
  cs_clone "$cand" && return 0
  cs_blocked
  return 1
}

cs_eval_admission() {
  CS_ADMISSION="OPEN"; CS_ADMISSION_WHY=""
  if ! cs_is_int "$CS_FREE_RAM_MB" || ! cs_is_int "$CS_SWAP_TOTAL_MB" || ! cs_is_int "$CS_SWAP_FREE_MB"; then
    CS_ADMISSION="PARKED"; CS_ADMISSION_WHY="metrics unreadable (fails closed)"
    return 0
  fi
  if [ "$CS_FREE_RAM_MB" -lt "$CS_MIN_FREE_RAM_MB" ]; then
    CS_ADMISSION="PARKED"; CS_ADMISSION_WHY="free RAM ${CS_FREE_RAM_MB} MB < ${CS_MIN_FREE_RAM_MB} MB"
  fi
  # macOS grows swap on demand; total 0 means no swap in use, which is fine.
  if [ "$CS_SWAP_TOTAL_MB" -gt 0 ] && [ "$CS_SWAP_FREE_MB" -lt "$CS_MIN_SWAP_FREE_MB" ]; then
    CS_ADMISSION="PARKED"; CS_ADMISSION_WHY="${CS_ADMISSION_WHY:+$CS_ADMISSION_WHY; }swap free ${CS_SWAP_FREE_MB} MB < ${CS_MIN_SWAP_FREE_MB} MB"
  fi
  if cs_is_int "$CS_DISK_FREE_MB" && [ "$CS_DISK_FREE_MB" -lt "$CS_MIN_DISK_FREE_MB" ]; then
    CS_ADMISSION="PARKED"; CS_ADMISSION_WHY="${CS_ADMISSION_WHY:+$CS_ADMISSION_WHY; }disk free ${CS_DISK_FREE_MB} MB < ${CS_MIN_DISK_FREE_MB} MB"
  fi
}

# Writes only files this script owns. A file without our marker is left alone.
cs_write_owned() {
  local dest="$1" content="$2" marker="$3" tmp
  if [ -e "$dest" ] && ! cs_file_contains "$dest" "$marker"; then
    cs_note "$(cs_tilde "$dest") exists and was not written by courier-setup; left untouched"
    cs_partial
    return 1
  fi
  tmp="$dest.tmp.$$"
  if printf '%s\n' "$content" > "$tmp" && mv -f "$tmp" "$dest"; then
    return 0
  fi
  cs_note "could not write $(cs_tilde "$dest")"
  cs_partial
  return 1
}

cs_host_config() {
  local repo_disp="none"
  [ -n "$CS_REPO_DIR" ] && repo_disp="$(cs_tilde "$CS_REPO_DIR")"
  CS_HOST_CONFIG_JSON="{
  \"schema\": \"courier.host_config.v1\",
  \"written_by\": \"courier-setup\",
  \"setup_version\": \"$CS_VERSION\",
  \"updated_at\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"host_id\": \"$CS_HOST_HASH\",
  \"os\": \"macos\",
  \"ram_total_mb\": \"$CS_RAM_MB\",
  \"repo_path\": \"$repo_disp\",
  \"repo_branch\": \"$CS_BRANCH\",
  \"start_heavy_workers_on_setup\": false,
  \"resource_admission\": {
    \"max_heavy_builders\": $CS_MAX_HEAVY_BUILDERS,
    \"park_new_work_when\": {
      \"free_ram_mb_below\": $CS_MIN_FREE_RAM_MB,
      \"swap_free_mb_below\": $CS_MIN_SWAP_FREE_MB,
      \"disk_free_mb_below\": $CS_MIN_DISK_FREE_MB,
      \"metrics_unreadable\": true
    },
    \"running_work\": \"never stopped by admission; only new work is parked\"
  }
}"
  if [ "$CS_MODE" = "check" ]; then
    if [ -e "$CS_BASE/host-config.json" ]; then CS_HOST_CONFIG="present"; else CS_HOST_CONFIG="WOULD_WRITE"; fi
    return 0
  fi
  if cs_write_owned "$CS_BASE/host-config.json" "$CS_HOST_CONFIG_JSON" 'courier.host_config.v1'; then
    CS_HOST_CONFIG="written (max heavy builders $CS_MAX_HEAVY_BUILDERS)"
    cs_action "wrote ~/Courier/host-config.json"
  else
    CS_HOST_CONFIG="not written"
  fi
}

cs_job_loaded() { launchctl list "$CS_LABEL" >/dev/null 2>&1; }

cs_job_pid() {
  launchctl list "$CS_LABEL" 2>/dev/null | sed -n 's/.*"PID" = \([0-9][0-9]*\);.*/\1/p' | head -n 1
}

cs_service_step() {
  local plist="$HOME/Library/LaunchAgents/$CS_LABEL.plist" installer
  CS_SERVICE="UNKNOWN"
  if cs_job_loaded; then
    CS_SERVICE="REGISTERED (already loaded; left as is)"
    return 0
  fi
  if [ -e "$plist" ]; then
    CS_SERVICE="PLIST_PRESENT_NOT_LOADED (left untouched)"
    cs_note "a $CS_LABEL job file exists but is not loaded; it may belong to another install, so it is not replaced"
    cs_partial
    return 0
  fi
  if [ -z "$CS_REPO_DIR" ]; then
    if [ "$CS_MODE" = "check" ]; then CS_SERVICE="NOT_REGISTERED"; else CS_SERVICE="SKIPPED (no checkout)"; fi
    cs_partial
    return 0
  fi
  installer="$CS_REPO_DIR/scripts/mac_worker/install.sh"
  if [ ! -f "$installer" ]; then
    CS_SERVICE="SKIPPED (installer missing in checkout)"
    cs_partial
    return 0
  fi
  if ! cs_file_contains "$installer" 'COURIER_NO_START'; then
    # Older installers load the job with RunAtLoad/KeepAlive and start it.
    CS_SERVICE="SKIPPED (installer in this checkout would start the worker; needs the no-start installer on $CS_BRANCH)"
    cs_partial
    return 0
  fi
  if [ -z "$CS_PY" ]; then
    CS_SERVICE="SKIPPED (python 3.12 missing)"
    cs_partial
    return 0
  fi
  if [ "$CS_MODE" = "check" ]; then
    CS_SERVICE="NOT_REGISTERED (setup would register it without starting)"
    cs_partial
    return 0
  fi
  if COURIER_NO_START=1 PYTHON_BIN="$CS_PY" /bin/bash "$installer" </dev/null >/dev/null 2>&1; then
    CS_SERVICE="REGISTERED_IDLE (launchd job loaded, not started)"
    cs_action "registered $CS_LABEL via scripts/mac_worker/install.sh (no start)"
  else
    CS_SERVICE="FAILED (installer exit non-zero)"
    cs_partial
  fi
}

cs_prereqs() {
  cs_find_brew
  if [ "$CS_MODE" = "check" ]; then
    [ -n "$CS_BREW" ] || cs_note "Homebrew missing"
    return 0
  fi
  if [ -z "$CS_BREW" ]; then
    cs_note "Homebrew missing; its installer needs an admin password, so setup does not install it"
  fi
  if [ "$CS_GIT" != "yes" ] && [ -n "$CS_BREW" ]; then
    cs_brew_install git && cs_action "installed git (Homebrew)"
    hash -r; cs_detect_git
  fi
  if [ -z "$CS_PY" ] && [ -n "$CS_BREW" ]; then
    cs_brew_install python@3.12 && cs_action "installed python@3.12 (Homebrew)"
    hash -r; cs_detect_python
  fi
  if [ "$CS_GH" = "no" ] && [ -n "$CS_BREW" ]; then
    if cs_brew_install gh; then cs_action "installed gh (Homebrew)"; CS_GH="yes"; fi
  fi
  if [ "$CS_WITH_GODOT" = "1" ] && [ "$CS_GODOT" = "no" ]; then
    if [ -z "$CS_BREW" ]; then
      cs_note "--with-godot needs Homebrew"
      cs_partial
    else
      mkdir -p "$HOME/Applications"
      if cs_brew_install --cask --appdir="$HOME/Applications" godot; then
        cs_action "installed Godot 4 into ~/Applications"; CS_GODOT="yes"
      else
        cs_note "Godot install failed"
        cs_partial
      fi
    fi
  fi
}

cs_uninstall() {
  local plist="$HOME/Library/LaunchAgents/$CS_LABEL.plist" pid cand uninstaller=""
  for cand in "$CS_BASE/2026-courier" "$CS_BASE/2026-courier-host" "$CS_BASE"/2026-courier-host-*; do
    if [ -f "$cand/scripts/mac_worker/uninstall.sh" ]; then uninstaller="$cand/scripts/mac_worker/uninstall.sh"; break; fi
  done
  if ! cs_job_loaded && [ ! -e "$plist" ]; then
    CS_SERVICE="NOT_INSTALLED (nothing to remove)"
    return 0
  fi
  pid="$(cs_job_pid)"
  if [ -n "$pid" ]; then
    CS_SERVICE="RUNNING (not removed; setup never stops a worker)"
    cs_next "stop the Courier worker through its owner first, then run --uninstall again"
    cs_blocked
    return 0
  fi
  if [ -e "$plist" ] && ! cs_file_contains "$plist" "$CS_BASE/"; then
    CS_SERVICE="FOREIGN_JOB (points outside ~/Courier; not removed)"
    cs_blocked
    return 0
  fi
  if [ -z "$uninstaller" ]; then
    CS_SERVICE="NO_UNINSTALLER (no checkout under ~/Courier)"
    cs_blocked
    return 0
  fi
  if /bin/bash "$uninstaller" </dev/null >/dev/null 2>&1; then
    CS_SERVICE="UNINSTALLED (job removed; checkouts, config and logs kept)"
    cs_action "ran scripts/mac_worker/uninstall.sh"
  else
    CS_SERVICE="UNINSTALL_FAILED"
    cs_blocked
  fi
}

cs_report() {
  local mode_label="setup"
  [ "$CS_MODE" = "check" ] && mode_label="check (no changes)"
  [ "$CS_MODE" = "uninstall" ] && mode_label="uninstall"
  local sha="none"
  if [ -n "$CS_REPO_DIR" ] && [ "$CS_GIT" = "yes" ]; then
    sha="$(git -C "$CS_REPO_DIR" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
  fi
  local repo_disp="none"
  [ -n "$CS_REPO_DIR" ] && repo_disp="$(cs_tilde "$CS_REPO_DIR")"
  local pause="no"
  [ -e "$HOME/.courier/dev-night/RESOURCE_PAUSE" ] && pause="yes"
  CS_REPORT="COURIER HOST SETUP REPORT v$CS_VERSION
HOST $CS_STATUS
mode: $mode_label
time_utc: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
host_id: $CS_HOST_HASH
os: macOS $CS_OS_VER ($CS_ARCH)
cpu: $CS_CPU, $CS_NCPU cores
ram_mb: total $CS_RAM_MB, free $CS_FREE_RAM_MB
swap_mb: total $CS_SWAP_TOTAL_MB, free $CS_SWAP_FREE_MB
disk_free_mb: $CS_DISK_FREE_MB
git: $CS_GIT ${CS_GIT_VER}
python3.12: $CS_PY_VER
gh: $CS_GH, auth: $CS_GH_AUTH
muse: $CS_MUSE
agy: $CS_AGY
godot: $CS_GODOT
courier_processes: $CS_PROCS
dirty_worktrees: $CS_DIRTY (skipped in protected folders: $CS_DIRTY_SKIPPED)
night_runner_pause_file: $pause
repo: $repo_disp @ $sha [$CS_REPO_STATE]
host_config: $CS_HOST_CONFIG
service: $CS_SERVICE
admission: $CS_ADMISSION${CS_ADMISSION_WHY:+ ($CS_ADMISSION_WHY)}, max heavy builders $CS_MAX_HEAVY_BUILDERS
heavy_workers_started: 0
actions:
${CS_ACTIONS:-- none
}notes:
${CS_NOTES:-- none
}next:
${CS_NEXT:-- none
}"
  CS_REPORT="$(printf '%s\n' "$CS_REPORT" | cs_redact)"
}

courier_setup_main() {
  # Nothing below may read the piped script or wait for input.
  exec </dev/null

  CS_MODE="setup"; CS_WITH_GODOT=0
  local arg
  for arg in "$@"; do
    case "$arg" in
      --check) [ "$CS_MODE" = "setup" ] || { cs_say "Choose one of --check or --uninstall."; return 64; }; CS_MODE="check" ;;
      --uninstall) [ "$CS_MODE" = "setup" ] || { cs_say "Choose one of --check or --uninstall."; return 64; }; CS_MODE="uninstall" ;;
      --with-godot) CS_WITH_GODOT=1 ;;
      -h|--help) cs_usage; return 0 ;;
      *) cs_say "Unknown option: $arg"; cs_usage >&2; return 64 ;;
    esac
  done

  CS_STATUS="READY"; CS_NOTES=""; CS_ACTIONS=""; CS_NEXT=""

  local os_name="${COURIER_SETUP_UNAME:-$(uname -s 2>/dev/null)}"
  if [ "$os_name" != "Darwin" ]; then
    cs_say "HOST BLOCKED: this script is for macOS; detected '${os_name:-unknown}'. Nothing was changed."
    cs_say "Windows: use scripts/setup/courier-setup.ps1."
    return 3
  fi
  if [ "$(id -u 2>/dev/null)" = "0" ]; then
    cs_say "HOST BLOCKED: run as your normal user, not root. Nothing was changed."
    return 3
  fi
  if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
    cs_say "HOST BLOCKED: HOME is not set to a directory. Nothing was changed."
    return 3
  fi

  CS_BASE="$HOME/Courier"
  if [ -L "$CS_BASE" ] || { [ -e "$CS_BASE" ] && [ ! -d "$CS_BASE" ]; }; then
    cs_say "HOST BLOCKED: ~/Courier is a link or not a folder. Nothing was changed."
    return 3
  fi

  CS_HOST_FULL="$(hostname 2>/dev/null || true)"
  CS_HOST_SHORT="${CS_HOST_FULL%%.*}"
  CS_HOST_NAME="$(scutil --get ComputerName 2>/dev/null || true)"
  CS_HOST_HASH="h-$(cs_sha12 "courier-host-v1:$CS_HOST_SHORT")"

  cs_say "Courier host setup ($CS_MODE) ..."
  cs_detect_host
  cs_find_brew
  cs_detect_tools
  cs_count_processes

  if [ "$CS_MODE" = "uninstall" ]; then
    cs_uninstall
    CS_REPO_DIR=""; CS_REPO_STATE="not inspected"; CS_HOST_CONFIG="kept"; CS_DIRTY="not counted"; CS_DIRTY_SKIPPED=0
    CS_ADMISSION="n/a"; CS_ADMISSION_WHY=""
  else
    if [ "$CS_MODE" = "setup" ]; then
      if ! mkdir -p "$CS_BASE"; then
        cs_say "HOST BLOCKED: cannot create ~/Courier. Nothing else was changed."
        return 3
      fi
    fi
    cs_prereqs
    if [ "$CS_GIT" != "yes" ]; then
      CS_REPO_DIR=""; CS_REPO_STATE="SKIPPED (git missing)"
      cs_next "install the Xcode Command Line Tools (xcode-select --install), then run this line again"
      cs_blocked
    else
      cs_repo_step || true
    fi
    cs_count_dirty
    if [ -z "$CS_PY" ]; then
      cs_next "python 3.12 missing: brew install python@3.12"
      cs_partial
    fi
    cs_eval_admission
    if [ "$CS_STATUS" = "BLOCKED" ] && [ -z "$CS_REPO_DIR" ]; then
      CS_HOST_CONFIG="not written (blocked)"; CS_SERVICE="SKIPPED (blocked)"
    else
      cs_host_config
      cs_service_step
    fi
    [ "$CS_GH_AUTH" = "yes" ] || cs_next "GitHub CLI not signed in: run 'gh auth login' yourself (setup never handles credentials)"
    [ "$CS_MUSE" != "missing" ] || cs_next "muse CLI not found in PATH"
    [ "$CS_ADMISSION" = "OPEN" ] || cs_next "new heavy work stays parked until memory/swap recover"
  fi

  cs_report
  if [ "$CS_MODE" != "check" ] && [ -d "$CS_BASE" ]; then
    if cs_write_owned "$CS_BASE/setup-report.txt" "$CS_REPORT" "COURIER HOST SETUP REPORT"; then
      cs_say "Report: ~/Courier/setup-report.txt"
    fi
    # cs_write_owned may have downgraded the status; keep the printed word in sync.
    CS_REPORT="$(printf '%s\n' "$CS_REPORT" | sed "2s/.*/HOST $CS_STATUS/")"
  fi
  printf '%s\n' "$CS_REPORT"
  if [ "$CS_MODE" != "check" ] && command -v pbcopy >/dev/null 2>&1; then
    if printf '%s\n' "$CS_REPORT" | pbcopy 2>/dev/null; then
      cs_say "Report copied to the clipboard. Paste it into the chat."
    fi
  fi
  printf '\n==== HOST %s ====\n' "$CS_STATUS"
  case "$CS_STATUS" in
    READY) return 0 ;;
    PARTIAL) return 2 ;;
    *) return 3 ;;
  esac
}

courier_setup_main "$@"
exit $?
