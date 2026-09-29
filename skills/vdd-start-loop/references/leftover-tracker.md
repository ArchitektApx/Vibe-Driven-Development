# What each answer does to an existing `.scratch/<slug>/`

Say what each answer does to those files when you put the question, so the user
chooses on the consequence rather than on the label.

- **Continue the earlier Workflow.** Every file stays where it is. The reason
  this is the interrupted-Workflow answer and no other: a signed-off
  `.scratch/<slug>/CODEREVIEW.md` from a Workflow that already finished sends a
  restarted Orchestrator straight to the PR-Author, and a
  `.scratch/<slug>/PLAN-REVIEW.md` from one sends the Planner pushback on a
  Spec it has not written.
- **Start fresh on this slug.** Move the directory to `.scratch/<slug>-<n>/`,
  taking the lowest `n` from 2 upwards that is not already a directory, and
  print the name you moved it to.
- **Use a different slug.** Every file stays where it is, under the slug that
  named it. Go back to step 4 and ask for the slug again.
