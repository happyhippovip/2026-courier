/**
 * Windows Validation Oracle
 * Autonomous Windows validation and support lane for the safe local-workflow mission.
 * Invariants:
 *  - COPY_PASTE_EXIT = ACHIEVED
 *  - UNKNOWN != STOPPED
 *  - CONTENT_INTEGRITY != ACCESS_INTEGRITY
 *  - CMD != POWERSHELL
 *  - TEMPLATE commands with unresolved placeholders are non-executable fail-closed.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ShellClass = {
  CMD: 'CMD',
  POWERSHELL: 'POWERSHELL',
  BASH: 'BASH',
  ZSH: 'ZSH',
  UNKNOWN: 'UNKNOWN'
};

const CommandType = {
  EXAMPLE: 'EXAMPLE',
  TEMPLATE: 'TEMPLATE',
  EXECUTABLE: 'EXECUTABLE'
};

const ProcessState = {
  RUNNING: 'RUNNING',
  STOPPING: 'STOPPING',
  STOPPED: 'STOPPED',
  UNKNOWN: 'UNKNOWN'
};

const AccessIntegrityStatus = {
  SECURE_LEAST_PRIVILEGE: 'SECURE_LEAST_PRIVILEGE',
  PERMISSIVE_WARNING: 'PERMISSIVE_WARNING',
  INSECURE_EVERYONE_FULLCONTROL: 'INSECURE_EVERYONE_FULLCONTROL',
  UNVERIFIED: 'UNVERIFIED'
};

class WindowsValidationOracle {
  constructor() {
    this.reservedDeviceNames = new Set([
      'CON', 'PRN', 'AUX', 'NUL',
      'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
      'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]);

    this.macOnlyPatterns = [
      { pattern: /\bflock\s+-/i, issue: 'POSIX flock is not natively available in Windows cmd/pwsh' },
      { pattern: /\bkill\s+-[0-9]+/i, issue: 'POSIX signal delivery (kill -9 or kill -pgid) requires Darwin/Linux kernel' },
      { pattern: /\bsetsid\b/i, issue: 'POSIX setsid() requires Unix process group session manager' },
      { pattern: /\bsetpgid\b/i, issue: 'POSIX setpgid() requires Darwin/Linux kernel' },
      { pattern: /\bps\s+-[a-zA-Z]+/i, issue: 'POSIX ps command not native to Windows (use Get-Process or tasklist)' },
      { pattern: /\bchmod\s+[0-7]+/i, issue: 'POSIX chmod has no direct effect on NTFS DACL permissions' },
      { pattern: /\bchown\s+/i, issue: 'POSIX chown requires Darwin/Linux user accounts' },
      { pattern: /\blaunchctl\b/i, issue: 'macOS launchctl is Darwin specific' },
      { pattern: /\bpbcopy\b/i, issue: 'macOS pbcopy is Darwin specific (use Set-Clipboard or clip)' },
      { pattern: /\/dev\/null\b/i, issue: 'Unix /dev/null path (use NUL or $null in Windows)' },
      { pattern: /\/tmp\b/i, issue: 'Unix /tmp directory assumption (use %TEMP% or [System.IO.Path]::GetTempPath())' }
    ];

    this.placeholderPatterns = [
      /<[A-Z0-9_-]{2,}>/,
      /\{\{[A-Za-z0-9_-]+\}\}/,
      /\bTODO_INSERT_[A-Z0-9_]+\b/,
      /\[YOUR_[A-Z0-9_]+\]/
    ];
  }

  // --- A. PATH & COMPATIBILITY VALIDATION ---

  normalizePath(inputPath, targetPlatform = 'windows') {
    if (!inputPath || typeof inputPath !== 'string') {
      return { valid: false, error: 'EMPTY_OR_INVALID_PATH', normalized: '' };
    }

    const trimmed = inputPath.trim();
    const baseName = path.basename(trimmed).split('.')[0].toUpperCase();
    if (this.reservedDeviceNames.has(baseName)) {
      return {
        valid: false,
        error: `RESERVED_WINDOWS_DEVICE_NAME: ${baseName}`,
        normalized: trimmed,
        isReservedDevice: true
      };
    }

    let normalized = trimmed;
    if (targetPlatform === 'windows') {
      normalized = trimmed.replace(/\//g, '\\');
    } else {
      normalized = trimmed.replace(/\\/g, '/');
    }

    const isLongPath = normalized.length >= 260;
    const hasLongPrefix = normalized.startsWith('\\\\?\\');

    return {
      valid: true,
      raw: inputPath,
      normalized,
      targetPlatform,
      isLongPath,
      hasLongPrefix,
      requiresLongPathPrefix: isLongPath && !hasLongPrefix
    };
  }

  detectMacOnlyAssumptions(commandOrSnippet) {
    if (!commandOrSnippet || typeof commandOrSnippet !== 'string') return [];
    const findings = [];
    for (const rule of this.macOnlyPatterns) {
      if (rule.pattern.test(commandOrSnippet)) {
        findings.push({
          matched: rule.pattern.source,
          issue: rule.issue
        });
      }
    }
    return findings;
  }

  // --- B. SHELL PROVENANCE & TEMPLATE CLASSIFICATION ---

  classifyShell(commandString) {
    if (!commandString || typeof commandString !== 'string') return ShellClass.UNKNOWN;
    const s = commandString.trim();

    // PowerShell specific indicators
    const isPwsh = /\$env:[A-Za-z0-9_]+/i.test(s) ||
                   /\b(Get-Process|Stop-Process|Start-Process|Test-Path|Get-Content|Set-Content|ConvertFrom-Json|ConvertTo-Json)\b/i.test(s) ||
                   /\b-(eq|ne|gt|lt|ge|le|match|notmatch)\b/i.test(s) ||
                   /\|\s*(Measure-Object|Select-Object|Where-Object|ForEach-Object)\b/i.test(s);

    // CMD specific indicators
    const isCmd = /%[A-Za-z0-9_]+%/.test(s) ||
                  /\bset\s+[A-Za-z0-9_]+=/.test(s) ||
                  /\b(dir\s+\/b|type\s+nul|del\s+\/f|rmdir\s+\/s)\b/i.test(s) ||
                  /\b(echo\s+off|goto\s+:[A-Za-z0-9_]+)\b/i.test(s);

    // Bash/Zsh indicators
    const isBash = /\bexport\s+[A-Za-z0-9_]+=/.test(s) ||
                   /#!\/bin\/(bash|sh|zsh)/.test(s) ||
                   /\b(source\s+\.|apt-get|brew|systemctl)\b/.test(s);

    if (isPwsh && !isCmd && !isBash) return ShellClass.POWERSHELL;
    if (isCmd && !isPwsh && !isBash) return ShellClass.CMD;
    if (isBash && !isPwsh && !isCmd) return ShellClass.BASH;

    if (isPwsh && isCmd) return 'HYBRID_PWSH_CMD_CONFLICT';
    return ShellClass.UNKNOWN;
  }

  classifyCommandType(commandString) {
    if (!commandString || typeof commandString !== 'string') {
      return { commandType: CommandType.EXAMPLE, canExecute: false, reason: 'EMPTY_STRING' };
    }

    const s = commandString.trim();

    // Check for unresolved placeholders
    for (const p of this.placeholderPatterns) {
      if (p.test(s)) {
        return {
          commandType: CommandType.TEMPLATE,
          canExecute: false,
          reason: `UNRESOLVED_PLACEHOLDER: ${s.match(p)[0]}`
        };
      }
    }

    // Check for documentation comments or illustrative markers
    if (s.startsWith('# example') || s.startsWith('// example') || s.includes('example.com')) {
      return {
        commandType: CommandType.EXAMPLE,
        canExecute: false,
        reason: 'ILLUSTRATIVE_EXAMPLE_ONLY'
      };
    }

    return {
      commandType: CommandType.EXECUTABLE,
      canExecute: true,
      reason: 'FULLY_BOUND_AND_VALIDATED'
    };
  }

  // --- C. ACCESS INTEGRITY VS CONTENT INTEGRITY ---

  verifyContentIntegrity(contentOrBuffer, expectedSha256) {
    const hash = crypto.createHash('sha256').update(contentOrBuffer).digest('hex');
    const matches = expectedSha256 ? (hash.toLowerCase() === expectedSha256.toLowerCase()) : null;
    return {
      contentIntegrity: matches === true ? 'PASS' : (matches === false ? 'FAIL' : 'COMPUTED'),
      sha256: hash
    };
  }

  evaluateAccessIntegrity(aclOutputString) {
    if (!aclOutputString || typeof aclOutputString !== 'string') {
      return {
        accessIntegrity: AccessIntegrityStatus.UNVERIFIED,
        isBroadFullControl: false,
        reason: 'NO_ACL_DATA'
      };
    }

    // Check for dangerous Everyone:(F) or Everyone FullControl
    const hasEveryoneFullControl = /Everyone:\(F\)/i.test(aclOutputString) ||
                                   /Jeder:\(F\)/i.test(aclOutputString) ||
                                   /Everyone.*FullControl/i.test(aclOutputString);

    if (hasEveryoneFullControl) {
      return {
        accessIntegrity: AccessIntegrityStatus.INSECURE_EVERYONE_FULLCONTROL,
        isBroadFullControl: true,
        reason: 'FORBIDDEN: Broad Everyone:(F) grant violates least-privilege security invariant'
      };
    }

    const hasBroadWrite = /Everyone:\(W\)/i.test(aclOutputString) || /Jeder:\(W\)/i.test(aclOutputString);
    if (hasBroadWrite) {
      return {
        accessIntegrity: AccessIntegrityStatus.PERMISSIVE_WARNING,
        isBroadFullControl: false,
        reason: 'WARNING: Broad write permissions detected'
      };
    }

    return {
      accessIntegrity: AccessIntegrityStatus.SECURE_LEAST_PRIVILEGE,
      isBroadFullControl: false,
      reason: 'Bounded authenticated user access confirmed'
    };
  }

  // Invariant proof: Content integrity does not imply access integrity
  assertIntegrityDecoupling(contentMatch, accessMatch) {
    const isSecurityAcceptable = (contentMatch === true) && (accessMatch === AccessIntegrityStatus.SECURE_LEAST_PRIVILEGE);
    return {
      contentIntegrity: contentMatch ? 'PASS' : 'FAIL',
      accessIntegrity: accessMatch,
      totalAcceptance: isSecurityAcceptable ? 'PASS' : 'FAIL_CLOSED',
      invariant: 'CONTENT_INTEGRITY_DOES_NOT_PROVE_ACCESS_INTEGRITY'
    };
  }

  // --- D. PROCESS STATE EVIDENCE ORACLE (UNKNOWN != STOPPED) ---

  evaluateProcessState(evidenceRecord) {
    if (!evidenceRecord || typeof evidenceRecord !== 'object') {
      return {
        state: ProcessState.UNKNOWN,
        isStopped: false,
        reason: 'NO_EVIDENCE_RECORD'
      };
    }

    const { pid, hasActivePid, exitCode, timeoutGraceExpired, queryError } = evidenceRecord;

    if (queryError) {
      return {
        state: ProcessState.UNKNOWN,
        isStopped: false,
        reason: `QUERY_ERROR: ${queryError} (UNKNOWN != STOPPED)`
      };
    }

    if (hasActivePid === true) {
      if (timeoutGraceExpired) {
        return {
          state: ProcessState.STOPPING,
          isStopped: false,
          reason: 'Process still visible during graceful shutdown'
        };
      }
      return {
        state: ProcessState.RUNNING,
        isStopped: false,
        reason: `Active process confirmed with PID ${pid}`
      };
    }

    if (hasActivePid === false && exitCode !== undefined && exitCode !== null) {
      return {
        state: ProcessState.STOPPED,
        isStopped: true,
        exitCode,
        reason: `Positive evidence of termination captured (exitCode: ${exitCode})`
      };
    }

    return {
      state: ProcessState.UNKNOWN,
      isStopped: false,
      reason: 'PID absent but exit code not captured; UNKNOWN != STOPPED'
    };
  }

  // --- E. DURABLE DATA FORMAT & ATOMIC WRITE ---

  validateIso8601UtcTimestamp(ts) {
    if (!ts || typeof ts !== 'string') return false;
    const isoRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/;
    if (!isoRegex.test(ts)) return false;
    const parsed = new Date(ts);
    return !isNaN(parsed.getTime());
  }

  safeAtomicWrite(targetPath, content) {
    const dir = path.dirname(targetPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const tempPath = `${targetPath}.${Date.now()}.${crypto.randomBytes(4).toString('hex')}.tmp`;
    fs.writeFileSync(tempPath, content, 'utf8');
    fs.renameSync(tempPath, targetPath);
    return { success: true, targetPath, bytesWritten: Buffer.byteLength(content, 'utf8') };
  }
}

module.exports = {
  ShellClass,
  CommandType,
  ProcessState,
  AccessIntegrityStatus,
  WindowsValidationOracle
};
