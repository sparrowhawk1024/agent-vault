# AgentVault Workspace Rule

You are working on AgentVault, a standalone hackathon project for WEB3-05: policy-bound autonomous procurement and machine-to-machine payments.

Always re-read the relevant section of `docs/MASTER_PROMPT.md` and the current `docs/PROGRESS.md` before resuming work.

Preserve the existing implementation and all completed phase gates. Inspect files before changing them. Do not overwrite working components or start over merely because a new task is received.

Keep the agent, optimizer, verifier and smart contract as separate responsibilities.

Never enforce financial authority in an LLM prompt. Never trust the agent, free-text vendor descriptions or optimizer output. Enforce the required rules in deterministic verification code and in the contract where they are on-chain verifiable.

Use the installed QpiAI SDK interfaces documented in `docs/SDK_NOTES.md`. Do not invent functions, parameters, result fields or execution outcomes.

Never fabricate a sponsor call, transaction, benchmark, timing, screenshot or evidence artifact.

Keep API secrets and private keys out of source control, browser code, logs and evidence. Use test-only local-chain keys and tokens.

Write or update tests as each module is added. Fix errors before advancing through a gate.

Every meaningful step updates `docs/PROGRESS.md` with completed work, work in progress, blockers, decisions, elapsed time and the next three actions.

Maintain documentation for assumptions, architecture, installed SDK interfaces, demo execution and known limitations.

At the end of each phase, run the stated gates, record actual results and commit the phase only if the tests and required checks pass. Never report unexecuted tests as passed.

When context resets, read this rule, sections 0–4 of the master prompt, the active phase, and `docs/PROGRESS.md` before taking further action.

Ask the user only for genuine blockers such as missing credentials, account access or required administrative permissions. Continue with work that is not blocked.

The deliverable is a working, tested procurement-security application. Code quantity and visual polish do not substitute for correct execution or verifiable security behavior.
