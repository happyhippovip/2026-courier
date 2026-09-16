
        const fs = require('fs');
        const counterFile = process.argv[2];
        const lockFile = process.argv[3];
        const count = parseInt(process.argv[4], 10);
        function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
        async function run() {
          for (let i = 0; i < count; i++) {
            let acquired = false;
            while (!acquired) {
              try {
                const fd = fs.openSync(lockFile, 'wx');
                fs.writeFileSync(fd, String(process.pid));
                fs.closeSync(fd);
                acquired = true;
              } catch(e) {
                await sleep(Math.floor(Math.random() * 10) + 2);
              }
            }
            try {
              const v = parseInt(fs.readFileSync(counterFile, 'utf8').trim(), 10);
              await sleep(2);
              fs.writeFileSync(counterFile, String(v + 1), 'utf8');
            } finally {
              try { fs.unlinkSync(lockFile); } catch(e){}
            }
          }
        }
        run();
      