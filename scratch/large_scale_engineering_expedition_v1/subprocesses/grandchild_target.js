
    const fs = require('fs');
    const logFile = process.argv[2];
    fs.writeFileSync(logFile, 'STARTED:' + process.pid + '\n', { flag: 'a' });
    setInterval(() => {
      fs.writeFileSync(logFile, 'BEAT:' + process.pid + '\n', { flag: 'a' });
    }, 200);
  