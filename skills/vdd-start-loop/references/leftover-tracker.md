# A leftover `.scratch/<slug>/`

An earlier Workflow used this slug, and its Spec, its Tickets and its review
files are all still in `.scratch/<slug>/`. Put three answers to the user:
continue that Workflow, start fresh on this slug, or use a different slug.
Say what each answer does to those files when you put the question, so the user
chooses on the consequence rather than on the label.

- **Continue the earlier Workflow.** This is the answer when that Workflow was
  interrupted, and only then. Every file stays where it is, the Doorbell file
  `.scratch/<slug>/doorbells` with the rest, so the interrupted Workflow's
  waits pick up where they were. A signed-off `.scratch/<slug>/CODEREVIEW.md`
  from a Workflow that already finished sends a restarted Orchestrator
  straight to the PR-Author, and a `.scratch/<slug>/PLAN-REVIEW.md` from one
  sends the Planner pushback on a Spec it has not written.
- **Start fresh on this slug.** Move the directory to `.scratch/<slug>-<n>/`,
  taking the lowest `n` from 2 upwards that is not already a directory, and
  print the name you moved it to. The move happens before anything else
  writes under `.scratch/<slug>/`.
- **Use a different slug.** Every file stays where it is, under the slug that
  named it. Go back to step 3 and ask for the slug again.

Delete nothing on any of the three answers. The earlier Workflow's directory is
that Workflow's record, so a wrong answer here stays recoverable. Keep every
path you touch under `.scratch/` inside this loop's slug or the name you moved
the old one to.
