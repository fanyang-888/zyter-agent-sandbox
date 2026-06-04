# Triage Labels

Standard five-label vocabulary. Apply these exactly as written.

| Label | Meaning | When to apply |
|-------|---------|---------------|
| `needs-triage` | Needs human evaluation | Default for all new incoming issues |
| `needs-info` | Waiting on reporter to clarify | Incomplete bug report or unclear requirement |
| `ready-for-agent` | Fully specified, AFK-ready | Spec is complete; an agent can pick this up without human context |
| `ready-for-human` | Needs human implementation | Too ambiguous or high-stakes for autonomous agent action |
| `wontfix` | Will not be actioned | Out of scope, duplicate, or intentional non-fix |

## Creating labels in GitHub

Run once after repo is provisioned:

```bash
gh label create "needs-triage"    --color "e4e669" --description "Needs human evaluation"
gh label create "needs-info"      --color "d93f0b" --description "Waiting on reporter"
gh label create "ready-for-agent" --color "0075ca" --description "Fully specified, AFK-ready"
gh label create "ready-for-human" --color "008672" --description "Needs human implementation"
gh label create "wontfix"         --color "ffffff" --description "Will not be actioned"
```
