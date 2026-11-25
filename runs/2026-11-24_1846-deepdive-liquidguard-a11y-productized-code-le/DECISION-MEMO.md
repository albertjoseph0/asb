# Dalio Deep-Dive Decision Memo — LiquidGuard A11y — Productized Code-Level WCAG 2.2 AA Remediation & Monthly Regression-PR Guard for Shopify & WooCommerce Stores

- **Outcome:** `KILLED`
- **Independent Panel:** Scorer `-1.0` (0.30) · Attacker `-1.0` (0.40) · Consequence/EV `-1.0` (0.30) → Weighted `-1.0` (Split: `False`)
- **Expected ARR:** `$10,000` (`P=4.0%`)
- **Kill Trigger:** KILL IMMEDIATELY (do not write any scanner/PR automation code) if ANY of the following occur: (1) >40% of serious/critical WCAG 2.2 AA violations across 10 audited $500k-$5M target stores live inside unpatchable 3rd-party app scripts/iframes rather than theme Liquid/PHP; OR (2) fewer than 3 of 25 qualified $1M-$5M merchants place a real $1,450 deposit (or binding paid pilot agreement) after seeing AccessComply ($29-$199/mo) and Patrol ($200/mo) side-by-side and accepting explicit non-indemnity; OR (3) fewer than 50% of deposit-paying buyers agree to retain the $299/mo monitoring plan beyond Month 3 once the initial theme PR is merged.
