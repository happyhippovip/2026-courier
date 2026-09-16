
    const { spawn } = require('child_process');
    const fs = require('fs');
    const logFile = process.argv[2];
    const child = spawn(process.execPath, ["C:\\Users\\lol\\2026-workspace\\courier\\scratch\\large_scale_engineering_expedition_v1\\subprocesses\\grandchild_target.js", logFile], {
      detached: true,
      stdio: 'ignore'
    });
    fs.writeFileSync(logFile, 'WRAPPER_SPAWNED_GRANDCHILD:' + child.pid + '\n', { flag: 'a' });
    child.unref();
    setTimeout(() => {
      fs.writeFileSync(logFile, 'WRAPPER_EXITING:' + process.pid + '\n', { flag: 'a' });
      process.exit(0);
    }, 400);
  