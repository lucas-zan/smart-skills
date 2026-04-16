# Requirement: Example Feature

## Background

The team needs a shared delivery workflow so local AI changes become visible to everyone early and can be merged back with less conflict.

## Problem

Local-only agent changes are not visible to teammates, and late integration increases merge risk.

## Goal

Allow an operator to:

- keep developing on the current branch by default
- push a visible remote share branch first
- run verification before landing
- block landing when requirement, design, or test evidence is missing

## Scope

In scope:

- current branch as default base branch
- evidence validation before commit
- share-and-land after explicit human confirmation
- protected branch fallback to pull request

Out of scope:

- auto-writing requirement and design documents
- automatic reviewer assignment
- release approval workflow

## Acceptance Criteria

1. If `--base` is omitted, the current branch is used.
2. If requirement, design, or test evidence is missing, commit is blocked.
3. The share branch is pushed before landing to the base branch.
4. If the base branch changes during verification, the workflow rebases and verifies again.
5. If the base branch is protected by policy, the workflow reports that a pull request is required.

## Risks

- Teams may rely on direct landing where protected-branch review should be mandatory.
- Evidence file locations may vary across repositories and need repo-local policy adjustment.
