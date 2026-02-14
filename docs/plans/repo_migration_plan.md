# Repo Migration Plan: Connecting to Fork (msneto)

This plan outlines the steps to reconfigure the local git repository to point to a personal fork while preserving all local branches and progress.

## Problem Statement
The local repository is currently connected to the original repository (`obeone/crawler-to-md`) as `origin`. Since the user lacks push access to the original repository, they need to point `origin` to their fork (`msneto/crawler-to-md`) to push changes and create Pull Requests, while keeping the original repository as `upstream` for synchronization.

## Detailed Steps

### 1. Rename Current Remote
*   **Action:** Rename the current `origin` to `upstream`.
*   **Command:** `git remote rename origin upstream`
*   **Files Affected:** `.git/config`
*   **Point of Attention:** This ensures that `obeone` remains accessible for fetching updates but is no longer the default push target.
*   **Risk:** Local branches will temporarily lose their tracking relationship.
*   **Mitigation:** This is resolved in Step 3 by re-establishing tracking with the new `origin`.

### 2. Add Fork as New Origin
*   **Action:** Add the personal fork as the new `origin`.
*   **Command:** `git remote add origin https://github.com/msneto/crawler-to-md.git`
*   **Point of Attention:** Verify the URL is correct to ensure push access.
*   **Risk:** Incorrect remote URL or lack of SSH/HTTPS credentials.
*   **Mitigation:** Verify connectivity immediately with `git remote -v`.

### 3. Sync with Fork and Push
*   **Action:** Push local branches to the fork and set up tracking.
*   **Sub-steps (for each branch: main, opencode, perf):**
    1.  `git checkout <branch>`
    2.  `git fetch origin`
    3.  `git merge origin/<branch> --allow-unrelated-histories` (Only if the fork has divergent history or was initialized with different files like a README).
    4.  `git push -u origin <branch>`
*   **Risk:** Merge conflicts if the fork contains changes not present locally.
*   **Mitigation:** Resolve conflicts manually. Use `--force-with-lease` if the local branch is the definitive "source of truth" and you wish to overwrite the fork's current state safely.

### 4. Verification
*   **Action:** Ensure the remotes and branches are correctly configured.
*   **Command:** `git remote -v && git branch -vv`
*   **Expected Outcome:** 
    - `origin` points to `msneto/crawler-to-md`.
    - `upstream` points to `obeone/crawler-to-md`.
    - Local branches track `origin/<branch>`.

## Tests
1. **Connectivity Test:** `git fetch upstream` and `git fetch origin` should both succeed.
2. **Push Test:** Create a dummy commit on a new branch and push: `git push origin <test-branch>`.
3. **Tracking Test:** `git status` should show "Your branch is up to date with 'origin/<branch>'".
