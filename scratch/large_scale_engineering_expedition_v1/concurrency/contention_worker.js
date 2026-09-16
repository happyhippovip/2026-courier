
    const fs = require('fs');
    const path = require('path');

    const counterFile = process.argv[2];
    const lockFile = process.argv[3];
    const workerId = process.argv[4];
    const iterations = parseInt(process.argv[5], 10);

    function sleep(ms) {
      return new Promise(r => setTimeout(r, ms));
    }

    async function acquireLock() {
      const maxRetries = 1000;
      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          const fd = fs.openSync(lockFile, 'wx');
          fs.writeFileSync(fd, workerId + ':' + Date.now());
          fs.closeSync(fd);
          return true;
        } catch (e) {
          if (e.code === 'EEXIST') {
            const jitter = Math.floor(Math.random() * 15) + 5;
            await sleep(jitter);
          } else {
            throw e;
          }
        }
      }
      throw new Error('Lock acquisition timeout in ' + workerId);
    }

    function releaseLock() {
      try {
        if (fs.existsSync(lockFile)) fs.unlinkSync(lockFile);
      } catch (e) {
        // Ignored
      }
    }

    async function main() {
      for (let i = 0; i < iterations; i++) {
        await acquireLock();
        try {
          const val = parseInt(fs.readFileSync(counterFile, 'utf8').trim(), 10);
          await sleep(5); // Hold lock across simulated workload
          fs.writeFileSync(counterFile, String(val + 1), 'utf8');
        } finally {
          releaseLock();
        }
        await sleep(Math.floor(Math.random() * 5));
      }
      console.log('Worker ' + workerId + ' completed ' + iterations + ' increments.');
    }

    main().catch(err => {
      console.error(err);
      process.exit(1);
    });
  