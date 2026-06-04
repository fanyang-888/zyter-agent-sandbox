# Issue Tracker: GitHub

Issues live in the private GitHub repository under the Zyter org.
The repo URL will be provided by Matt Burt once the GitHub org access is provisioned.

## CLI

Skills use the `gh` CLI. Authenticate once with:

```bash
gh auth login
```

## Creating issues

```bash
gh issue create --title "..." --body "..." --label "needs-triage"
```

## Listing issues

```bash
gh issue list --label "ready-for-agent"
```

## Notes

- Repo is private, under Zyter org — requires invite from Matt Burt / IT
- Until GitHub access is provisioned, track work in the shared Google Doc:
  https://docs.google.com/document/d/10Mnjhg5hkyFUCC-ZujzoyiX9jMTEC1WOxLHCcvAit8k
