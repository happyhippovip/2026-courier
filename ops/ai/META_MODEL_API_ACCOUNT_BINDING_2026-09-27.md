# Meta Model API Account Binding — 2026-09-27

Status: NON-SECRET ACCOUNT/OPERATIONS NOTE

## Chosen login method

For the separate Meta Model API / PAYG account, use **GitHub sign-in**.

This is only the authentication method for the Meta developer account.

It does **not** mean:
- Meta receives repository write authority from Courier;
- the Courier repo stores GitHub credentials;
- the repo stores the Meta API key;
- the repo stores OAuth/session tokens.

## Target use

Purpose:
- Meta Model API PAYG
- model: muse-spark-1.3-contributor
- separate from the existing Muse Code subscription quota
- intended for Courier API usage after a successful local CLI auth test

## Secret handling

NEVER commit:
- Meta API keys
- GitHub OAuth tokens
- browser session cookies
- passwords
- recovery codes
- billing details

The repo may record only:
- login method = GitHub
- account role/purpose
- non-secret project/account labels
- verification status such as PAYG_PROVEN=YES/NO

## Current verified state

PAYG Contributor playground test has been observed successfully at the account level:
- model: muse-spark-1.3-contributor
- request counted in Usage
- 8 input tokens
- 20 output tokens

Local terminal environment at last check:
- MODEL_API_KEY not set
- META_API_KEY not set

Therefore:
- account-level PAYG path works;
- local CLI PAYG auth is NOT yet proven.

## Next exact step

Create/sign into the separate Meta Model API account using GitHub auth.
Then create a PAYG API key in that non-subscription project/account.
Store the secret locally only.
Test exactly one Muse CLI session before rolling out to the wall.
