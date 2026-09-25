# Email Sender Policy

## Hard invariant: affected account = sender

For account-specific support, billing, verification, entitlement, quota, suspension, access, or similar cases, the **affected account must be the outgoing email account**.

Rules:

1. **Never choose the next available connected email account.**
2. Before sending, identify the exact affected account and use that exact address as the sender.
3. If the affected sender is ambiguous, ask the human which exact address is authorized. Do not send until clarified.
4. If the affected account is not connected or cannot be used as a sender, fail closed: do not substitute another account. Prepare a draft/text or request the required human action instead.
5. If several accounts have separate problems, treat each account separately unless the human explicitly authorizes one sender to discuss the others.
6. After sending, verify the actual sent message and confirm the real `From`, recipients, subject, and attachments. Never claim a send without evidence.
7. A spoken typo or approximate account name must not override written evidence from screenshots, the support thread, or an explicitly confirmed address.

Default behavior:

**AFFECTED_ACCOUNT -> EXACT_SENDER -> VERIFY_SENT**

If exact sender cannot be guaranteed:

**HUMAN_GATE / NO SEND**
