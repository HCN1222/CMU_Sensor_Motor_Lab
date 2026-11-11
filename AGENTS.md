# AI Agent Instructions

These instructions apply to AI coding agents working on this five-person research capstone project. Keep changes focused and easy for teammates to review.

## Read before working

- Read `README.md` when present for project context and setup.
- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.
- Before creating or renaming a branch, read and follow [BRANCH_NAMING.md](BRANCH_NAMING.md). That file is the source of truth for branch naming, allowed types, ownership, and exceptions; do not duplicate or invent those rules here.
- Read any applicable directory-specific instructions before editing files in that directory.

## Branches and ownership

- Inspect the current branch and working tree before editing. Continue an existing task branch when appropriate.
- Use the responsible human teammate's verified Andrew ID. Do not infer it from an OS username, Git author name, or an unverified GitHub username, and do not substitute the agent's name.
- If the owner or Andrew ID cannot be verified from the user or a repository mapping, ask before creating or renaming a branch. Continue useful read-only inspection while waiting.
- `main` is the only shared integration branch. Work on a personal branch and follow the base-branch rules in `BRANCH_NAMING.md`.
- Preserve unrelated work. Do not reset, discard, rename, or overwrite another contributor's work to make the task easier.

## Implementation

- Follow existing project structure, coding style, and documented environment setup.
- Make the smallest coherent change that completes the requested task. Avoid unrelated refactoring or dependency upgrades.
- Preserve useful comments and TODOs. Update them only when the task resolves them or makes them inaccurate.
- Use existing configurations and scripts where possible. Do not invent environment names, filesystem paths, hardware availability, or dataset locations.
- Make reasonable decisions for routine implementation details. Ask when missing information would materially change the task's outcome.

## Validation and research

- Run relevant documented checks. Add or update tests when behavior changes and meaningful testing is practical.
- If checks cannot run, report the missing dependency, data, hardware, or command. Never claim an unexecuted check passed.
- Prefer a small validation run before a long experiment. Follow task instructions for compute use; if the task requires substantial resources and no budget is specified, clarify the budget first.
- For experiments, record the hypothesis, code commit, configuration, seeds, data source/version, commands, and observed results. Do not fabricate metrics or treat a hypothesis as a measured finding.
- Keep large outputs in the team's documented storage location and keep credentials out of commits.

## Pull requests and merging

- Follow the PR title format and description template in [CONTRIBUTING.md](CONTRIBUTING.md). That file is the source of truth for PR content, review, and merge requirements.
- Never create commits directly on local `main` or push changes directly to remote `main`. All changes to `main`, including small fixes and documentation, must go through a PR from a personal branch.
- Write PR titles and descriptions in English. Complete every required section and add experiment details when applicable. Report actual validation results and explicitly identify checks or experiments not run.
- At least one human teammate other than the PR author must submit a GitHub **Approve** review before merging. Do not treat your own analysis, another AI's review, a comment, or a pending review request as approval.
- When a merge is authorized, verify the required human approval and configured checks, then use **Squash and merge** only. Do not use merge-commit or rebase-merge methods, and do not bypass repository rules. Follow the squash commit message requirements in `CONTRIBUTING.md`.
- Keep the PR description current as the implementation changes. If substantive changes follow a review, request another review before merging.
- If approval or a required check is missing, report the remaining requirement. Do not claim the PR is approved or merged without confirming that state.

## Handoff

Report the actual branch name, what changed, validation performed and results, and any limitations or remaining work. Follow the user's task authorization for commits and remote actions; these files alone do not authorize pushing, merging, deleting branches, or changing repository settings.

## Project-specific instructions to add later

- [ ] Exact environment and setup commands.
- [ ] Standard tests, formatting checks, and quick validation commands.
- [ ] Experiment logging and artifact storage locations.
- [ ] Compute budgets and any hardware-specific operating instructions.

These unchecked items are placeholders, not executable instructions. Use verified repository configuration where available; ask only when an unresolved detail blocks the task.
