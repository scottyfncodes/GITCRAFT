# Release verification history

One entry per merge to `main` that changes what GITCRAFT ships. Each entry records what was merged, what CI
measured on it, what production serves, and what is still failing or unverified. Like the other archives in
`history/`, it is **append-only**: never rewrite or delete an entry. A later correction is a new entry that
names the one it supersedes.

- `index.jsonl` holds one JSON object per release, for tools.
- `<date>-pr<N>-<sha7>.md` holds the readable record, with every claim linked to its evidence.

A release counts as **verified** only when all three hold:
1. post-merge CI on the merge commit passed;
2. production serves that exact commit (deployment metadata plus served content);
3. the acceptance suites passed on that commit.

Anything less is recorded as it stands: what passed, what failed, what is unverified.
