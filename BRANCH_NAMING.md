# Branch Naming Convention

This policy applies to the five teammates and their AI coding agents working on this research-focused capstone project. The repository has one shared integration branch, `main`. All development and research work takes place on personal working branches identified by the responsible teammate's Andrew ID.

**Required format:** `<andrew-id>/<type>/<description>`, or `<andrew-id>/<type>/<issue-id>-<description>` when a primary GitHub Issue exists.

In this document, **MUST** indicates a requirement, **SHOULD** indicates a recommendation, and **MAY** indicates an option. These are team conventions, not GitHub's built-in naming requirements.

## 1. Branch structure

```text
# Without a primary GitHub Issue
<andrew-id>/<type>/<description>

# With a primary GitHub Issue
<andrew-id>/<type>/<issue-id>-<description>
```

Examples below use `alice1` as an illustrative Andrew ID. Replace it with the verified ID of the responsible teammate; never copy the example ID literally.

```text
alice1/feat/add-local-planner
alice1/fix/57-handle-camera-timeout
alice1/exp/compare-ppo-sac
```

| Component | Requirement |
| --- | --- |
| `andrew-id` | The verified Andrew ID of the primary human owner, in lowercase. Use the ID only, without an email domain. |
| `type` | Exactly one type from Section 3. |
| `issue-id` | The primary GitHub Issue number, when one exists: a positive integer without `#` or leading zeros. |
| `description` | A meaningful lowercase description with words separated by single hyphens. |

Personal working branches MUST have exactly three slash-separated components. Additional module scope and experiment variants belong in the description, not in extra path segments.

## 2. Ownership and Andrew IDs

- The prefix MUST identify the human responsible for the branch, including work performed by an AI agent on that person's behalf.
- The prefix MUST NOT be a display name, an unverified GitHub username, an agent name, or a placeholder such as `your-id`.
- An AI agent MUST obtain the ID from an explicit user instruction or an authoritative repository mapping of teammates to Andrew IDs. Git author names, OS usernames, and GitHub usernames alone are insufficient evidence.
- If the owner or ID is unknown or conflicting, the agent MUST ask for the missing identity before creating or renaming a branch. It MAY continue relevant read-only inspection in the meantime.
- A collaborative branch still has one primary human owner. Other contributors are identified in the pull request; the prefix does not restrict who may contribute.
- Do not rename an existing collaborative personal branch merely because a different teammate or agent contributes to it. Coordinate an ownership transfer with its collaborators if a rename is needed.

For validation, this policy accepts an owner component matching `[a-z][a-z0-9]*`. This is a repository syntax rule, not proof that an Andrew ID exists. If a verified ID does not fit this syntax, have a maintainer update the policy rather than inventing an alias.

## 3. Allowed branch types

Use only these five types. They cover implementation, debugging, code maintenance, documentation, and research exploration for this project.

| Type | Purpose | Example |
| --- | --- | --- |
| `feat` | Add or extend project capabilities, tools, or development infrastructure. | `alice1/feat/add-local-planner` |
| `fix` | Correct an error in code, configuration, or development tooling. | `alice1/fix/correct-reward-sign` |
| `refactor` | Reorganize or optimize existing implementation while preserving intended behavior. | `alice1/refactor/vectorize-observations` |
| `docs` | Add or update documentation, research notes, or experiment reports. | `alice1/docs/summarize-baseline-results` |
| `exp` | Explore feasibility, prototype a research idea, compare methods, or run ablations. | `alice1/exp/ablate-temporal-attention` |

Choose the type by the branch's primary purpose:

- Use `feat` when implementing a capability intended for project integration; use `exp` when investigating whether an approach works or how it compares with alternatives.
- Use `fix` for incorrect behavior, including numerical errors, broken environments, or failing development workflows.
- Use `refactor` for cleanup and behavior-preserving optimizations. If a change intentionally alters the algorithm or model behavior, use `feat` or `exp` instead.
- Tests accompanying another task use that task's type. For a testing-only task, use `feat` to add coverage or testing infrastructure, `fix` to correct a faulty test, and `refactor` to reorganize tests without changing their intent.
- Development tooling, dependencies, and automated checks follow the same purpose-based rule: `feat` for adding capability, `fix` for repairing it, and `refactor` for routine maintenance that preserves intended behavior.
- Exploratory work uses `exp`; it does not require a separate feasibility-study type. A rollback uses the type that describes its purpose, usually `fix` when restoring correct behavior.

Do not introduce additional types or aliases. A branch may include related implementation, tests, configuration, and documentation without needing a separate branch for each file category.

## 4. Description and character rules

Personal working branch names MUST:

1. Use only lowercase ASCII letters, digits, hyphens, and the two structural slashes.
2. Start the description with a letter. Each hyphen-separated word must contain at least one letter or digit.
3. Avoid consecutive hyphens, leading or trailing hyphens, spaces, underscores, and extra slashes.
4. Stay within 80 characters for the complete name, including the Andrew ID, type, Issue number, and separators.
5. Describe one coherent purpose that can be reviewed and merged independently.

Descriptions SHOULD use an action and an object, such as `add-depth-camera`, `handle-empty-point-cloud`, or `compare-reward-functions`. A meaningful scope MAY precede the action, such as `navigation-add-recovery-behavior` or `training-implement-gae`.

Avoid vague descriptions such as `update`, `changes`, `stuff`, `temp`, or `final-v2`. Do not add dates, model names, or tool names merely to identify who or what created the branch. A technology name is appropriate when it describes the task itself.

| Avoid | Use instead |
| --- | --- |
| `alice1/feat/New_Planner` | `alice1/feat/add-local-planner` |
| `alice1/fix/bug` | `alice1/fix/handle-camera-timeout` |
| `alice1/exp/final-v2` | `alice1/exp/compare-reward-functions` |
| `claude/feat/add-local-planner` | `<verified-andrew-id>/feat/add-local-planner` |
| `alice1/feat/navigation/add-planner` | `alice1/feat/navigation-add-planner` |

## 5. Issues, scope, and experiments

- Include the primary GitHub Issue number when one exists. Otherwise omit it; do not create an Issue solely to satisfy naming.
- Use an Issue number, not a pull request number. List additional related Issues in the pull request description.
- External ticket identifiers are outside this policy. Add an explicit team-wide extension before adopting another ticket format.
- Put module names or research objectives in the description when useful.
- Use branches for meaningful code or method differences. Store seeds, learning rates, batch sizes, and individual run identifiers in configuration files and experiment records instead of creating a branch for every run.
- An `exp` branch does not have to merge into `main`. Record the hypothesis, relevant configuration, results, and conclusion in the experiment record or pull request. Integrate useful code and findings when appropriate; do not merge an unsuccessful prototype merely to close the branch.

```text
alice1/feat/42-add-checkpoint-resume
alice1/fix/perception-handle-empty-point-cloud
alice1/feat/training-add-policy-baseline
alice1/exp/compare-sparse-dense-rewards
```

If two independent tasks would have the same name, add a meaningful distinction, such as `add-local-planner-recovery`. Do not append arbitrary `new`, `final`, or `v2` suffixes. If the existing branch already represents the assigned task, continue that branch when authorized.

## 6. The shared branch: `main`

`main` is the only shared integration branch and the only branch name exempt from the Andrew ID format. It holds the team's integrated project code. All other branches MUST follow the personal working branch format, even when multiple teammates collaborate on them.

- Do not create `develop`, release branches, support branches, or additional shared integration branches.
- Start new independent tasks from the current remote `main` after fetching, and normally target `main` in the pull request.
- Work that explicitly depends on another in-progress task MAY branch from that task's personal branch. Document the dependency in the pull request and keep the Andrew ID naming format. This does not create another shared integration branch.
- Keep `main` usable for team integration and research. Follow the team's review and check requirements; its shared status does not grant permission to bypass them.

This project does not use a production release or multi-version maintenance branch workflow. AI-generated branches follow the same personal naming rules; there is no tool-name or automation-prefix exception under this policy.

## 7. Required workflow for AI agents

Before creating a branch, an agent MUST:

1. Read this policy and applicable repository instructions, including `AGENTS.md` and `CONTRIBUTING.md` when present.
2. Inspect the current branch and working tree. Preserve unrelated and uncommitted work; never reset, discard, or move it just to satisfy naming.
3. Determine whether an existing branch already belongs to the assigned task. Continue it when appropriate instead of creating unnecessary branches.
4. Resolve the primary human owner's Andrew ID using Section 2.
5. Choose the type, optional Issue number, and description from the actual task.
6. Validate the proposed name and check relevant local and remote branch names for collisions. Never overwrite a branch that belongs to unrelated work.
7. For new independent work, fetch and branch from the current remote `main`. Use a different personal branch only for an explicit task dependency under Section 6. Do not assume the currently checked-out branch is the correct base. If fetching is unavailable, report that the base could not be refreshed rather than claiming it is current.

If continuing a legacy branch whose name does not comply, report the mismatch and coordinate its migration; do not silently rename a collaborator's branch. If an agent platform mandates a conflicting prefix, report the conflict instead of silently creating a noncompliant branch. Resolve the platform configuration or obtain an explicit team policy change before proceeding with branch creation. Do not silently replace the Andrew ID with `codex`, `claude`, or another tool identifier.

The agent MUST report the actual branch name when handing off work. This policy governs naming and does not independently authorize pushing, merging, deleting branches, or changing repository settings.

## 8. Validation

The following regular expression checks the structure of a personal working branch:

```regex
^[a-z][a-z0-9]*/(feat|fix|refactor|docs|exp)/([1-9][0-9]*-)?[a-z][a-z0-9]*(-[a-z0-9]+)*$
```

Use a full-string match. Separately enforce the 80-character limit, verify the owner's identity, and confirm that the name accurately describes the task. A regular expression cannot verify identity, Issue relevance, or task ownership.

Accept the shared branch only when its name is exactly `main`:

```regex
^main$
```

The complete naming rule is: accept `main`, or accept a personal branch matching the first expression and the separate checks above. Reject all other names.

Git's own syntax check is an additional check, not a replacement for this policy:

```bash
git check-ref-format --branch 'alice1/feat/42-add-checkpoint-resume'
```

Automated enforcement SHOULD check the pull request's source branch name, treat only `main` as the shared-branch exception, and report actionable errors without attempting automatic renames.

## 9. Repository adoption

Place this file at the repository root as `BRANCH_NAMING.md`. Add the following instruction to both `CONTRIBUTING.md` and the repository's agent instruction file, typically `AGENTS.md`:

```markdown
Before creating or renaming a branch, read and follow [BRANCH_NAMING.md](BRANCH_NAMING.md). Personal branches must use the responsible human teammate's verified Andrew ID: `<andrew-id>/<type>/<description>` or `<andrew-id>/<type>/<issue-id>-<description>`. The only allowed types are `feat`, `fix`, `refactor`, `docs`, and `exp`; `main` is the only shared branch. AI agents must not invent an Andrew ID, substitute their own tool name, or create additional shared branches. If the ID cannot be verified, ask before creating the branch.
```

Adding this file alone does not configure GitHub enforcement or guarantee that every agent loads it. Maintainers should link it from the instruction files their tools actually read. New branches MUST comply once adopted; existing branches may remain until their current work finishes unless the team coordinates a rename. Changes to the five allowed types or the single-shared-branch policy require an explicit team decision and an update to this document.

## References

- [Git: git-check-ref-format](https://git-scm.com/docs/git-check-ref-format)
- [GitHub: Dealing with special characters in branch and tag names](https://docs.github.com/en/get-started/using-git/dealing-with-special-characters-in-branch-and-tag-names)

The references describe platform syntax and character handling. The ownership, type, length, and workflow requirements above are this team's policy.
