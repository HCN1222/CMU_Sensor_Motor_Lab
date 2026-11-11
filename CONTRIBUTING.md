# Contributing

This is a five-person research capstone project. Keep contributions focused, understandable, and reproducible so teammates can build on each other's work.

## Getting started

- Read `README.md` for the project overview and any documented setup instructions.
- Follow [BRANCH_NAMING.md](BRANCH_NAMING.md) before creating or renaming a branch. It is the source of truth for branch names and ownership.
- If you use an AI coding agent, make sure it reads [AGENTS.md](AGENTS.md) and the branch policy. You remain responsible for reviewing its changes and results.

## Development workflow

1. Agree on a focused task with the relevant teammates. Use an Issue when useful; not every task needs one.
2. Check your working tree before switching branches. Preserve unrelated work.
3. Fetch the latest remote state and start independent work from remote `main`, using the branch policy. Continue an existing task branch when appropriate.
4. Make focused changes on your personal branch and commit them with clear messages describing their purpose. Never commit directly on `main` or push directly to `main`.
5. Run relevant checks and update documentation affected by the change.
6. Open a pull request, normally targeting `main`, obtain approval from at least one teammate other than the PR author, and use **Squash and merge**. If your task depends on another personal branch, explain that dependency in the PR.

Use personal branches and PRs for development changes. `main` is the only shared integration branch; the full naming rules remain in `BRANCH_NAMING.md`.

## Pull requests

### Required review and merge rules

- All changes to `main` MUST arrive through a pull request. Do not create commits directly on local `main` or push changes directly to remote `main`. This applies to code, documentation, configuration, and fixes of any size.
- Every PR MUST receive a GitHub **Approve** review from at least one human teammate other than the PR author before it is merged. A review request, a comment, an author's own review, or an AI review does not satisfy this requirement.
- **Squash and merge** is the only permitted PR merge method. Do not use **Create a merge commit** or **Rebase and merge**. Each merged PR contributes one squash commit to its target branch.
- Before merging, satisfy the repository's configured rules and required checks. Do not use bypass permissions to evade this policy. After substantive changes following a review, ask the reviewer to review those changes before merging.
- PR titles and descriptions MUST be written in English. Keep descriptions proportional to the change; documentation-only and small fixes still use the required sections.

Reviewers should check correctness, clarity, reproducibility, and effects on other project components. Keep `main` usable for the team's ongoing work. Repository rules enforce the configured technical restrictions; these documents also govern requirements such as description quality and research reporting.

### PR title

Use `<type>: <short description>`, with a type defined in [BRANCH_NAMING.md](BRANCH_NAMING.md). Describe the PR's overall purpose. Do not include the Andrew ID; ownership is already recorded in the branch and PR.

```text
feat: add obstacle-aware local planner
fix: correct reward normalization
exp: compare sparse and dense rewards
```

### PR description

Use the following template. The first four sections are required. Include **Experiment Details** when the PR introduces or changes a research experiment or reports experimental results; otherwise remove that section. Link a related Issue when one exists, without creating an Issue just to fill the template.

```markdown
## Purpose
Explain the problem or research question and why this change is needed.
Link related Issues, if any.

## Changes
- Summarize the main changes and important design decisions.

## Validation
- List checks or experiments actually run, relevant commands, and observed results.
- If validation was not run or was only partial, explain why and what remains unverified.

## Limitations & Follow-up
- List known limitations, effects on other modules, dependencies, or remaining work.
- Write "None" if there are none.

## Experiment Details
- Hypothesis and method/baseline:
- Code commit, configuration, and random seeds:
- Data source/version and relevant environment or hardware:
- Reproduction commands:
- Results and experiment record/artifact links:
```

Replace the template prompts with actual information before requesting review. If an experiment has not been run, say so and distinguish planned evaluation from observed results. Use `N/A` with a brief reason for an inapplicable experiment field. Do not invent results to complete the template.

### Squash commit message

Use the final PR title as the squash commit title. Preserve the key rationale, changes, validation results, and material limitations from the final PR description in the commit body. A concise summary with links to detailed experiment records is sufficient. Check the proposed message before merging; do not assume generated defaults contain the intended information.

## Research and experiments

- Record the hypothesis, code commit, configuration, random seeds, data version or source, and commands needed to reproduce meaningful results.
- Distinguish measured results from expectations. Negative results are useful when documented.
- Experiments do not have to merge into `main`; integrate useful code or findings when appropriate.
- Keep large datasets, checkpoints, and generated outputs in the team's agreed storage location. Commit lightweight configurations and references instead. Do not commit credentials.

## Details to add as the project develops

The following are not configured by this document:

- [ ] Environment setup and dependency installation instructions in `README.md`.
- [ ] Standard test, formatting, and quick validation commands.
- [ ] Experiment record and dataset/checkpoint storage locations.
- [ ] Teammate-to-Andrew-ID mapping, if the team wants agents to resolve IDs automatically.

Until a command or location is documented, use verified repository instructions or coordinate with a teammate rather than guessing.
