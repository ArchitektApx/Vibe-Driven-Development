# The two checks behind `PR: yes`

- **Can push.** A remote is configured and `git ls-remote <remote> HEAD` exits
  0.
- **Can open a PR.** `gh` is on `PATH`, the host read from
  `git remote get-url <remote>` is a GitHub host, and
  `gh auth status --hostname <host>` exits 0.

Both checks use the same remote: the one the base branch tracks when it tracks
one, else the single configured remote, else `origin`.

Stderr is ignored because it lies here. `git ls-remote` has been observed
printing `fatal: failed to store` on a call that exited 0, and a check that
read that line would report a working remote as broken.
