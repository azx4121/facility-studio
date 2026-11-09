# AI collaboration and handoff

Create separate worktrees from a known commit. Codex prepares requirements and acceptance tests; Claude implements within the assigned worktree; Gemini reviews the resulting commit or PR diff independently, including counterexamples; Codex verifies tests and prepares a draft PR. An unavailable or unauthenticated agent blocks that stage; never substitute a fabricated review. Only one agent changes the same engine files at a time.

The handoff must record: task_id; requirements; relevant files; engineering assumptions and units; reference inputs; expected and actual results; author and reviewer; test commands and outcomes; commit and PR; outstanding approvals. Do not send secrets, private customer files, or unreviewed local data to cloud services. Review the diff and file list before any push. A draft PR is not approval to merge or release.

Stop work at a failed gate, record the failure and preserve evidence. Resume from the recorded commit after addressing the cause; do not reset another agent's worktree.
