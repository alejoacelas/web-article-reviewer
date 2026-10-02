# Publication decisions

## Core decisions

- [Keep the public distribution generic](#generic-public-distribution): use placeholder
  examples, derive the capture site from the input URL, and require an explicit Google
  account for document writes.

## Details

### Generic public distribution

This repository publishes reusable code, prompts and documentation. Organization-specific
branding, accounts, repository links and review outputs belong in separately managed
checkouts. Review incoming changes before publication so synchronizing another checkout
cannot restore that material. Publish future changes on top of the clean public
history; merging an older checkout would restore the removed history.

## Decision log

- 2026-10-02: Keep the public distribution generic, including examples and runtime
  defaults. This lets readers configure the reviewer for their own site and account.
- 2026-10-02: Replace the public development history with one clean initial commit,
  preserving the current code and documentation.
