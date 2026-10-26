Current status:
!`git status --short`
Recent commits:
!`git log --oneline -5`

Ship what is verified and nothing else.

1. Run the full pipeline — Make targets if present, otherwise tests, lint, type-check — and report exact results.
2. Probe what this change touches for real: endpoints, CLI, services.
3. Verify config and environment: what is set, what is missing, what silently defaults.
4. Stage only the intended files; no secrets; commit message in repo style with honest scope.
5. Prepare the PR description: changes, evidence, known gaps, what stays out.
6. `git push` and PR creation need explicit human approval: present the plan and stop.

Context from the requester: ${note}
