module.exports = function hardenedHumanGateClassifier(text) {
    const l = text.toLowerCase();
    if (l.includes('do not') || l.includes('without deployment') || l.includes('analysis only') ||
        l.includes('prepare ') || l.includes('draft only') || l.includes('write ') ||
        l.includes('paper trade') || l.includes('simulate ') || l.includes('free option analysis') ||
        l.includes('recommendation report')) {
      if (!l.includes('auto-renew') && !l.includes('future charge') && !l.includes('send outreach')) return false;
    }
    const gated = ['deploy to', 'send outreach', 'execute live trade', 'execute trade', 'auto-renew', 'future charge', 'upgrade execution', 'spend €', 'spend $'];
    for (const g of gated) {
      if (l.includes(g)) return true;
    }
    if (l.includes('deploy') || l.includes('trade') || l.includes('publish') || l.includes('outreach')) return true;
    return false;
  };
