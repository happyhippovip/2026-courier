# Courier Subscription-First Auto Router — 2026-09-27

Status: HIGH-PRIORITY PRODUCT REQUIREMENT
Purpose: let Courier automatically keep useful work moving across already-authorized subscription/provider capacity with minimal human relay.

## User goal

The user should not have to manually decide which already-paid provider/session should receive the next task.

Courier should automatically use the subscriptions/capacity the user already has, while remaining truthful about availability, quota, cost, and stop reasons.

## Core rule

SUBSCRIPTION_FIRST

Use already-authorized subscription capacity before PAYG/API spend when that is the user's configured preference.

PAYG is an explicit fallback, not an invisible default.

## Provider state

Track per provider/account/session:

- provider
- auth_mode: SUBSCRIPTION / PAYG_API / UNKNOWN
- available: YES / NO / UNKNOWN
- quota_state: AVAILABLE / LOW / EXHAUSTED / UNKNOWN
- reset_at when known
- active_slots
- admitted_slots
- last_success_at
- last_error_class
- cost_mode
- user_priority
- cooldown_until

## Routing order

Default policy:

1. already-open healthy subscription capacity
2. other already-authorized subscription capacity
3. free/cheaper read-only capacity
4. PAYG only when explicitly enabled and within budget
5. HUMAN_GATE when no authorized route remains

Never change subscriptions, buy plans, create/revoke keys, rotate accounts, or spend money without explicit user authorization.

## Automatic fallback

When a worker returns a provider/quota failure such as:

- subscription quota exhausted
- rate limit
- session unavailable
- provider unavailable

Courier should:

1. checkpoint current work;
2. preserve task/attempt identity;
3. mark provider lane temporarily unavailable;
4. choose another authorized provider lane;
5. continue the same dependency-safe work without human relay;
6. avoid duplicate execution;
7. record the handoff in the Ledger.

## No blind account rotation

Courier may route among accounts/sessions that the user has already authenticated and explicitly admitted to the wall.

It must not:
- scrape credentials;
- reveal or copy secret keys;
- silently log into new accounts;
- bypass provider limits;
- evade rate limits;
- automate CAPTCHA/2FA;
- change billing/subscription state.

## Subscription recovery

When a subscription quota resets, Courier may return that provider to AVAILABLE after a lightweight health check.

Do not assume a reset occurred only because a clock passed.

## Budget guard

For PAYG:

- user-configured soft budget
- optional hard stop when local spend estimate reaches the user limit
- dashboard/API usage reconciliation when available
- no invisible escalation from subscription to PAYG

If cost state is UNKNOWN, fail toward cheaper/read-only work rather than spending.

## Customer UX

Normal customer surface should be simple:

AUTO
- Use my subscriptions first
- Use PAYG fallback: ON/OFF
- PAYG budget: user-set
- Reserve interactive capacity: user-set

Status example:

Google Subscription: AVAILABLE
Muse Subscription: EXHAUSTED until reset
Muse PAYG: AVAILABLE
Current route: Google Subscription
Fallback: Muse PAYG
Human action needed: NO

## Ledger binding

Every provider switch must preserve:

GOAL
-> TASK
-> ATTEMPT
-> DISPATCH GENERATION
-> PROVIDER ROUTE
-> EXECUTION
-> RESULT
-> VERIFY
-> RECONCILE

A provider fallback must not create a second active execution for the same attempt.

## Near-term implementation target

After the current final-candidate proof path is green:

1. provider-capacity registry
2. subscription/PAYG auth-mode classification
3. quota/error classifier
4. routing policy
5. failover with duplicate-safety
6. reset/cooldown handling
7. simple AUTO user control

## Success condition

The user can start Courier once and leave.

If one subscription lane exhausts, Courier keeps going on another already-authorized lane or a permitted PAYG fallback without asking the user to manually shuttle tasks between windows.
