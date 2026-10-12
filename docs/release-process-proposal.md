# Proposal: one release process for the agent and MCP repos

Status: proposal, open for comments. The same file sits in airia-agents-config, arii-agents and arii-mcp.

## The problem

You cannot read from any of these repos what is running in Production today.

- **airia-agents-config.** This is where agents are released from. Every merge to `main` gets a version tag (for example `v0.76.15`). A merge that changes Arii or Nicoya agents deploys them to Development. Staging and Production are deployed by hand, and the deploy workflows default to deploying `main`, not a tag. GitHub's own deploy records name `main` for every deploy, so they cannot say which version went where. `CHANGELOG.md` groups changes by the week they merged, and it has to warn that a merge is not a deploy.
- **arii-agents.** This is a test repo. It will replace airia-agents-config once its testing is finished. Until then it copies the airia-agents-config changelog on purpose, to stay in step. Every merge gets a dated tag (for example `v2026.10.07.1`), and that tag deploys to Development.
- **arii-mcp.** `arii.yaml` already ships as a weekly release, and its version sits in the file (`3.1.0`). It is uploaded by hand. One catalog serves dev, staging and prod, so an upload is live everywhere at once. There is no git tag for a release, so you cannot check out the spec exactly as it was uploaded.

What the three have in common: the changelog records what merged, not what shipped where.

## The proposal

### 1. A release is one tag, cut every Thursday

Keep the tag on every merge. It is useful for Development. Every Thursday, pick the newest tag as the release, and publish it as a GitHub Release with the changelog entry as its notes.

For arii-mcp, tag the commit that was uploaded, using the spec version: `v3.1.0`.

### 2. Promote the same tag, in order

Deploy the release tag to Development, then Staging, then Production, then the regional Production environments. Never deploy `main` to Staging or Production. Every environment then runs bytes you can name, and two deploys of the same tag send the same thing.

arii-mcp has only one environment, so promotion there is just "upload the tagged spec".

### 3. The changelog is written per release, not per week

Each entry is headed by the release tag and its date, and links to its GitHub Release. Under it: agents (or tools) added, changed and removed, with the version each moved to, and then tooling and CI changes. This is the same layout the changelogs use today.

The GitHub Release notes carry one more line that records where the release went:

```
Deployed: Nicoya Development Oct 8 · Nicoya Staging Oct 9 · Nicoya Production Oct 10
```

The line lives in the GitHub Release, not in `CHANGELOG.md`, so that recording a deploy never needs a commit to `main`.

- **airia-agents-config:** the deploy workflows write the line by themselves. Until that ships, it is filled in by hand.
- **arii-mcp:** the spec is uploaded by hand, so the line is filled in by hand when it is uploaded.

### 4. Write the entry in the PR that makes the change

Each PR adds its line under an `## Unreleased` heading at the top of the changelog. Cutting a release renames `Unreleased` to the tag. arii-mcp already has this rule. It means nobody has to rebuild the week from git history.

### 5. Gate Production, roll back by tag

The QA gate and the agent evaluations must pass on the release tag before it goes to Production. To roll back, deploy the previous release tag.

## What changes in each repo

| Repo | Change |
| --- | --- |
| airia-agents-config | Add `## Unreleased` to `CHANGELOG.md`. Re-head the current week's entry with its release tag. Publish a GitHub Release every Thursday. Deploy Staging and Production from that tag. The deploy workflows write the `Deployed` line. |
| arii-agents | Nothing for now. When it replaces airia-agents-config, it takes over the changelog and this process unchanged. |
| arii-mcp | Tag each uploaded version (`v3.1.0`, ...) and publish it as a GitHub Release. Fill in the `Deployed` line by hand at upload. |
