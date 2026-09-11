// Zero-dependency FX converter and charm pricing matrix
const RATES = {
  EUR: { rate: 1.0, symbol: '€', vat_inclusive: true },
  USD: { rate: 1.08, symbol: '$', vat_inclusive: false },
  GBP: { rate: 0.85, symbol: '£', vat_inclusive: true },
  JPY: { rate: 165.0, symbol: '¥', vat_inclusive: true },
  CAD: { rate: 1.48, symbol: 'C$', vat_inclusive: false },
  AUD: { rate: 1.64, symbol: 'A$', vat_inclusive: true },
  CHF: { rate: 0.96, symbol: 'CHF ', vat_inclusive: true }
};

function roundCharmPrice(rawAmount, currency) {
  if (currency === 'JPY') {
    // JPY uses integers, typical charm price ends in 90 or 80 (e.g. 890)
    return Math.round(rawAmount / 10) * 10 - 10;
  }
  // If exact whole number (e.g. 5.00), charm price is 4.99
  if (rawAmount > 0 && Math.abs(rawAmount - Math.round(rawAmount)) < 0.01) {
    return Math.round(rawAmount) - 0.01;
  }
  // Decimal currencies round to .49 or .99
  const floorVal = Math.floor(rawAmount);
  const remainder = rawAmount - floorVal;
  if (remainder <= 0.49) {
    return floorVal + 0.49;
  } else {
    return floorVal + 0.99;
  }
}

function convertPrice(baseEur, targetCurrency) {
  const meta = RATES[targetCurrency];
  if (!meta) {
    throw new Error(`Unsupported currency: ${targetCurrency}`);
  }
  const rawConverted = baseEur * meta.rate;
  const charmPrice = roundCharmPrice(rawConverted, targetCurrency);
  return {
    currency: targetCurrency,
    symbol: meta.symbol,
    base_eur: baseEur,
    fx_rate: meta.rate,
    raw_amount: Math.round(rawConverted * 100) / 100,
    charm_price: charmPrice,
    display_price: `${meta.symbol}${targetCurrency === 'JPY' ? charmPrice : charmPrice.toFixed(2)}`,
    vat_inclusive: meta.vat_inclusive
  };
}

function generateFullMatrix(baseEur = 5.00) {
  const matrix = {};
  for (const curr of Object.keys(RATES)) {
    matrix[curr] = convertPrice(baseEur, curr);
  }
  return {
    base_currency: 'EUR',
    base_price: baseEur,
    generated_at: new Date().toISOString(),
    matrix
  };
}

module.exports = {
  RATES,
  convertPrice,
  generateFullMatrix,
  roundCharmPrice
};
