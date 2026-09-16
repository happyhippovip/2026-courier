
        const { spawn } = require('child_process');
        const child = spawn(process.execPath, ["C:\\Users\\lol\\2026-workspace\\courier\\scratch\\durable_autonomy_runtime_multi_hour_v1\\scratch\\TASK-1789014832240-8\\orphan_target.js"], { detached: true, stdio: 'ignore' });
        console.log('GRANDCHILD_PID:' + child.pid);
        child.unref();
        process.exit(0);
      