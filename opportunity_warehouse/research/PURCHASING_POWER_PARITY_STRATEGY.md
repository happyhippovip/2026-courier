# GLOBAL PURCHASING POWER PARITY (PPP) PRICING STRATEGY
**DOCUMENT:** `opportunity_warehouse/research/PURCHASING_POWER_PARITY_STRATEGY.md`  
**GOAL:** Maximize global sales unit volume and revenue without cannibalizing Tier-1 domestic margins.  
**STATUS:** PRODUCTION SPECIFICATION  

---

## 1. Regional Pricing Matrix

| Region Tier | Target Markets | Local Baseline Index | Recommended Price | Gumroad Discount Code | Net Realized EUR |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Tier 1 (Base)** | US, EU, UK, Canada, Australia, Japan | 100% | **€5.00** ($5.00) | Full Price (No Code) | ~€4.20 |
| **Tier 2 (Emerging High)** | Poland, Baltics, Southern Europe, Chile | 70% | **€3.50** ($3.50) | `GLOBAL30` (30% off) | ~€2.85 |
| **Tier 3 (Large Developer)** | India, Brazil, Mexico, Turkey, Indonesia | 40% | **€2.00** ($2.00 / ₹199) | `DEVPOWER60` (60% off) | ~€1.55 |
| **Tier 4 (Low Purchasing)** | Nigeria, Pakistan, Egypt, Vietnam | 25% | **€1.25** ($1.25) | `LOCAL75` (75% off) | ~€0.95 |

---

## 2. Fraud & Geo-Spoofing Protections
1. **Gumroad Native MoR Enforcement:** Gumroad automatically uses buyer IP geo-location and issuing credit card country code to prevent VPN arbitrage.
2. **First-Purchase Threshold:** The initial milestone requires **1 real sale $\ge$ €5.00** (Tier 1 domestic or un-discounted purchase) to certify the strict €5 baseline.
3. **Upsell Preserved:** Discount codes apply only to the entry tool (`agent-context-trimmer`); backend bundles and team licenses remain at full price.
