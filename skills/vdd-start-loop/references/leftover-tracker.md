# A leftover `.scratch/<slug>/`

An earlier Workflow used this slug, and its Spec, its Tickets and its review
files are still in `.scratch/<slug>/`. Put the answers `loop new` prints to the
user, each with what it does to those files, so the user chooses on the
consequence rather than on the label:

- **Continue the earlier Workflow.** Only when that Workflow was interrupted.
  Every file stays where it is, the Doorbell file with the rest, so its waits
  pick up where they were.
- **Start fresh on this slug.** The directory moves to `.scratch/<slug>-<n>/`,
  closed, and nothing in it is deleted.
- **Use a different slug.** Every file stays where it is, under the slug that
  named it.
