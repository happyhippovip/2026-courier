# Rugcheck Protection Knowledge Seed

**Updated:** 2026-09-11  
**Purpose:** compact, high-signal context for future Rugcheck/protection agents. This is reference knowledge, not an authorization to trade, spend, sign wallets, publish, contact third parties, or take external action.

## 1. Evidence discipline — permanent

Use this order of trust where possible:

1. **Primary evidence:** regulator filings, official government records, original posts, original on-chain transactions/contracts.
2. **Independent high-quality reporting:** Reuters/AP and similarly strong sources.
3. **Secondary analysis:** useful for leads, never enough by itself for a serious accusation.
4. **Social posts/screenshots:** prove that a statement/post existed if provenance is verified; they do **not** prove the statement itself is true.
5. **Rumor/anonymous claims:** lead only; mark unverified.

Permanent interpretation rules:

- **Correlation != causation.**
- **Shared contact != direct involvement.** Example: A knows B and B knows C does not prove A worked with C.
- **Political/business access != corruption.** A quid-pro-quo claim needs direct evidence.
- **Price move + headline != proven cause.** News narratives are hypotheses unless supported by market/physical evidence.
- Preserve timestamps, source URL, exact quote/data point, and confidence.
- Separate every output into `FACT`, `INFERENCE`, `ALLEGATION`, `UNKNOWN`.
- If evidence conflicts, fail closed and keep `UNKNOWN`.

## 2. Elon Musk / Donald Trump — compact verified timeline

Use these as network-analysis anchors, not as proof of wrongdoing.

- **2016-12-14 — formal access:** Trump transition announced Elon Musk as a member of the President's **Strategic and Policy Forum**, intended to meet with the President and provide economic-policy input.
  - Primary/archival source: https://www.presidency.ucsb.edu/documents/press-release-president-elect-donald-j-trump-announces-travis-kalanick-uber-elon-musk

- **2017-01-27 — second advisory link:** archived Trump White House listed **Elon Musk, Tesla** among the initial business leaders assisting the **Manufacturing Jobs Initiative**.
  - Source: https://trumpwhitehouse.archives.gov/briefings-statements/president-trump-announces-manufacturing-jobs-initiative/

- **2017-06-01 — public break:** Musk left presidential advisory councils after Trump's Paris Agreement withdrawal. This matters because the relationship was not a continuous alliance.

- **2024-07-13 — explicit endorsement:** Musk publicly endorsed Trump after the Pennsylvania assassination attempt.
  - Reuters: https://www.reuters.com/world/us/elon-musk-says-he-fully-endorses-tough-trump-posts-photo-2024-07-13/

- **2024 election financing — very large, documented:** FEC filings reported by Reuters showed Musk spent **more than $259M** supporting Trump's 2024 election effort; about **$239M** went to America PAC.
  - Reuters: https://www.reuters.com/world/us/musk-spent-over-quarter-billion-dollars-help-elect-trump-2024-12-06/

- **2025-05-30 — government role:** White House documented Musk as a **departing DOGE adviser** alongside Trump.
  - Primary source: https://www.whitehouse.gov/gallery/president-trump-participates-in-a-press-conference-with-departing-doge-adviser-elon-musk/

- **2025-06 — major public feud + government-contract exposure:** Reuters reported the White House directed Defense Department/NASA to gather details on billions in SpaceX contracts after the Trump-Musk rupture; roughly **$22B** in SpaceX government contracts were described as exposed/at risk in contemporaneous reporting. This is evidence of institutional/economic interdependence, **not** proof of illegal retaliation or corruption.
  - Reuters syndication: https://www.investing.com/news/stock-market-news/white-house-reviews-spacex-contracts-as-trumpmusk-feud-simmers-sources-say-4095848

- **2026-09 — renewed operational political alignment:** Reuters reported Musk's America PAC and Trump-aligned PACs again spending in Republican midterm races. Treat this as current political/financial alignment, not evidence of personal friendship or a hidden agreement.
  - Reuters: https://www.reuters.com/legal/government/trump-musk-super-pacs-unleash-millions-boost-republicans-battleground-races-2026-09-11/

### Protection-system lesson from this case

When analyzing a powerful network, track the sequence separately:

`PUBLIC STATEMENTS -> MONEY/FUNDING -> PLATFORM REACH -> FORMAL ACCESS -> GOVERNMENT ROLE -> CONTRACT/REGULATORY EXPOSURE`

Then test each edge independently. Never collapse the whole chain into one accusation.

## 3. Musk / Milei / crypto overreach guard

Prior research in the project found strong public Musk-Milei ties, but that does **not** by itself establish Musk involvement in the later $LIBRA scandal.

Permanent anti-false-positive rule:

`MUSK <-> MILEI` plus `MILEI <-> CRYPTO ACTOR` does **not** equal `MUSK <-> CRYPTO ACTOR`.

Require a direct meeting, message, payment, contract, wallet flow, shared entity, or other independently verifiable edge before connecting the endpoints.

## 4. Oil anomaly baseline — historical reference only

These numbers are timestamped baselines. **Never treat them as live prices later. Re-fetch current market data.**

- **2026-08-28 physical-flow signal:** Reuters/Kpler data reported **7 commodity vessels** transited the Strait of Hormuz, down from **17** the previous day and below the **10-day average of 15**.
  - Reuters-syndicated source: https://www.internazionale.it/ultime-notizie-reuters/2026/08/28/shipping-traffic-via-strait-of-hormuz-slips-below-10-day-average-data-shows

- **2026-09-01 market move:** Brent settled at **$94.65 (+4.6%)** and WTI at **$90.22 (+5.2%)** during renewed U.S.-Iran fighting and supply-risk concerns.
  - Reuters: https://www.reuters.com/business/energy/oil-prices-rise-latest-fighting-resurrects-middle-east-supply-disruption-risks-2026-09-01/

- **2026-09-11 later snapshot:** Reuters reported Brent around **$105.17** and WTI around **$100.04**, with oil still on track for a weekly gain above 9% despite a daily pullback.
  - Reuters: https://www.reuters.com/business/energy/oil-prices-set-end-week-over-100-first-time-nearly-4-months-2026-09-11/

- **User-reported alarm performance:** oil alarm had **2 correct hits out of 2** at the time of the prior handover. Preserve as user-reported operational history only; **2/2 is not statistical proof** of predictive power.

### Oil-analysis rule for Rugcheck/protection agents

Do not explain a move from the headline alone. Check, where available:

`PRICE -> VOLUME -> OPEN INTEREST -> TERM STRUCTURE -> LIQUIDATION/SHORT-COVERING SIGNALS -> PHYSICAL FLOWS -> INVENTORIES -> REFINERY/PIPELINE/SHIPPING DISRUPTIONS -> EVENT TIMELINE`

CFTC positioning is delayed, so it may be impossible to attribute a same-day move to a specific actor. If attribution is not evidenced, say `UNKNOWN`.

## 5. Minimal future Rugcheck checklist

For any coin, market event, market-maker claim, influencer network, or suspected rug:

1. **Identity:** verified entities, aliases, wallets, companies, official accounts.
2. **Timeline:** what existed before promotion/launch/pump and what changed after.
3. **Control:** deployer/admin keys, mint/freeze authority, LP control, upgradeability, concentration, vesting/unlocks.
4. **Money flow:** funding wallets, transfers, exchange deposits/withdrawals, shared counterparties.
5. **Market mechanics:** liquidity, volume quality, OI/funding, liquidation cascades, spreads, price impact, suspicious synchronized behavior.
6. **Promotion/network:** original posts, paid promotion evidence, disclosed/undisclosed relationships, shared entities.
7. **Source strength:** primary first; screenshot provenance required.
8. **Alternative explanations:** test benign explanations before alleging manipulation.
9. **Confidence:** output `HIGH / MEDIUM / LOW` and list what would falsify the hypothesis.
10. **Safety:** informational analysis only. No autonomous trade, spend, wallet signing, customer outreach, publication, or accusations presented as fact without evidence.

## 6. Output format for agents

Keep Rugcheck outputs compact:

```text
CLAIM:
STATUS: FACT | INFERENCE | ALLEGATION | UNKNOWN
CONFIDENCE: HIGH | MEDIUM | LOW
EVIDENCE:
- source + timestamp + exact data point
COUNTEREVIDENCE / ALTERNATIVES:
WHAT WOULD CONFIRM OR FALSIFY:
RISK TO USER:
NEXT SAFE READ-ONLY CHECK:
```

This file is intentionally small. Add only durable lessons or verified anchor facts; do not turn it into a raw news dump.