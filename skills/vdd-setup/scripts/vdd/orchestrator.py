"""The orchestrator command group: the Orchestrator acting on the tool's
output, reading no Working file.

orchestrator start places the Workflow from the state file and the Doorbell
file, on a first start or after a restart, and records the session.
orchestrator return runs after every hosted Role's return that is not a
QUESTION or a BLOCKED, and after a Planner Doorbell: it reads the round's
outcome from the state its check --write recorded and prints the one next
step. Neither rings, spawns or resumes anything: the Orchestrator takes every
outward step itself, so the user can pause the Loop before any of them.
"""

from __future__ import annotations

import os
import re
from typing import Any, NoReturn

from . import args, doorbells, gitcmd, harness as harnesses, loopfile, loopstate, places, signoff
from .out import TELL, Failure, Output

SUBCOMMANDS = ("start", "return", "respawn", "tokens")
USER_REASON = "for the user's findings"
POLICY = re.compile(r"^(every round|never|over ([1-9][0-9]*)(k?))$")
HOSTED = ("Plan-Reviewer", "Coder", "Code-Reviewer")
HELP = [
    "orchestrator start --slug <slug> [--harness <h>]",
    "  Run on every start of the Orchestrator's Session, a restart included. Records a new session, names the",
    "  Harness and its Harness file, says where each Loop stands, and prints the one next step: a spawn, the",
    "  ring to the Planner, the wait for the Planner's Doorbell, the fold at a code Sign-off, or the PR",
    "  step. Every spawn after a restart is fresh. After the user's findings it spawns the Coder fresh for",
    "  the next round, with no ring.",
    "",
    "orchestrator return --role <Planner|Plan-Reviewer|Coder|Code-Reviewer> --slug <slug> --harness <h>",
    "  Run after every hosted Role's return whose last line does not start with QUESTION: or BLOCKED:, and",
    "  with --role Planner once doorbell take printed the Planner's Doorbell. It takes no return line and no",
    "  token count: the round's outcome is the one its check --write recorded. It prints the next step, a",
    "  spawn with its Read and Write lists, a resume with its message, the ring, the wait or the fold; a",
    "  second return for a round already acted on, and a round with no check --write, each say what to do.",
    "",
    "orchestrator respawn --role <Plan-Reviewer|Coder|Code-Reviewer> (--policy \"<p>\" | --once) --slug <slug> --write",
    "  On the user's word: --policy sets the Role's Respawn policy, \"every round\", never or \"over <n>k\"",
    "  (Claude Code only, from the Coder's subagent_tokens); --once makes the Role's next spawn fresh, and",
    "  after a BLOCKED prints that fresh spawn for the unfinished round at once. The reviewers start at never;",
    "  the Coder's policy is asked at Model approval.",
    "",
    "orchestrator tokens --role <Role> --tokens <n> --slug <slug>",
    "  Claude Code only, when a Next: line asks for it: record the Role's subagent_tokens from its latest",
    "  completion notice and print the step that waited for the count.",
    "",
    "start, return and tokens ring, spawn and resume nothing, and take no --write: you take each step they",
    "print. --slug names the loop; pass it on every call. Run every command from the repository root.",
]

COMMON = {"slug": args.VALUE, "harness": args.VALUE}
SPECS = {
    "start": dict(COMMON),
    "return": dict(COMMON, role=args.VALUE),
    "respawn": dict(COMMON, role=args.VALUE, policy=args.VALUE, once=args.FLAG, write=args.FLAG),
    "tokens": dict(COMMON, role=args.VALUE, tokens=args.VALUE),
}


def usage() -> str:
    return "%s orchestrator --help" % places.command()


def run(argv: list[str]) -> int:
    return args.run_group(argv, "orchestrator", SPECS, HELP,
                          "Run the orchestrator command your skill or the last Next: line names.", dispatch)


def dispatch(sub: str, values: dict[str, Any]) -> int:
    flow = Flow.find(values, "orchestrator %s" % sub)
    if sub == "start":
        return start(flow)
    if sub == "respawn":
        return respawn(flow, values)
    if sub == "tokens":
        return tokens(flow, values)
    args.require(values, ["role", "harness"], usage())
    role = values["role"]
    args.choice(role, HOSTED + ("Planner",), "--role takes Planner, Plan-Reviewer, Coder or Code-Reviewer.",
                "Run %s for the usage." % usage())
    return returned(flow, role)


# The spawn ledger's lines, as loopstate's builders write them.
SESSION = re.compile(r"^orchestrator session ([0-9]+)$")
SPAWNED = re.compile(r"^(spawn|resume) (\S+) ([0-9]+) session ([0-9]+)(?: reason (.*))?$")
ONCE = re.compile(r"^respawn-once (\S+)$")
RESPAWN = re.compile(r"^respawn (\S+) (.+)$")
RETURNED = re.compile(r"^return (\S+) ([0-9]+) (ok|miss)$")
TOKENS = re.compile(r"^tokens (\S+) ([0-9]+) ([0-9]+)$")


class Spawned:
    """One spawn or resume line."""

    def __init__(self, kind: str, role: str, round_number: int, session: int, reason: str | None) -> None:
        self.kind = kind
        self.role = role
        self.round = round_number
        self.session = session
        self.reason = reason


class Flow:
    """One loop as the Orchestrator sees it: its state file, its Doorbell
    file and the Harness the Loop file names."""

    @classmethod
    def find(cls, values: dict[str, Any], command: str) -> Flow:
        loop = loopfile.find(gitcmd.project_root(os.getcwd()), values["slug"])
        state = loopstate.open_loop(loop, command)
        flow = cls(loop, state)
        if values["harness"] is not None:
            given = args.harness_of(values, usage())
            if given.name != flow.harness.name:
                raise Failure(
                    "--harness %s does not match the Loop file's Harness: %s." % (given.name, flow.harness_label),
                    "Run the command again with --harness %s." % flow.harness.name,
                )
        return flow

    def __init__(self, loop: loopfile.Loop, state: loopstate.State) -> None:
        self.loop = loop
        self.state = state
        self.slug = loop.slug
        self.harness = harnesses.known(loopfile.harness_slug(loop.setting("Harness")[0]))
        # The Loop file's own value: Generic's Harness module has no label.
        self.harness_label = loop.setting("Harness")[0]
        self.place = doorbells.Place(loop.root, loop.slug, loop, state)
        self.last_session = 0
        self.spawns: list[Spawned] = []
        self.once: dict[str, bool] = {}
        self.policies: dict[str, str] = {}
        self.returns: list[tuple[str, int, bool]] = []
        self.counts: dict[tuple[str, int], int] = {}
        for line in state.lines:
            self.read(line)

    # --- the spawn ledger, parsed once at load ---

    def read(self, line: str) -> None:
        """Add one state line to the records it belongs to."""
        match = SESSION.match(line)
        if match:
            self.last_session = int(match.group(1))
            return
        match = SPAWNED.match(line)
        if match:
            record = Spawned(match.group(1), match.group(2), int(match.group(3)), int(match.group(4)),
                             match.group(5))
            self.spawns.append(record)
            if record.kind == "spawn":
                self.once[record.role] = False
            return
        match = ONCE.match(line)
        if match:
            self.once[match.group(1)] = True
            return
        match = RESPAWN.match(line)
        if match:
            self.policies[match.group(1)] = match.group(2).strip()
            return
        match = RETURNED.match(line)
        if match:
            self.returns.append((match.group(1), int(match.group(2)), match.group(3) == "ok"))
            return
        match = TOKENS.match(line)
        if match:
            self.counts[(match.group(1), int(match.group(2)))] = int(match.group(3))

    def append(self, line: str) -> None:
        """Append a built state line and add it to the records."""
        self.state.append(line)
        self.read(line)

    def session(self) -> int:
        return self.last_session

    def out(self, role: str, session: int | None = None) -> tuple[str, int] | None:
        """(kind, round) of the Role's last spawn or resume in the session,
        or None: whether a live subagent of that Role is out."""
        session = self.session() if session is None else session
        last: tuple[str, int] | None = None
        for record in self.spawns:
            if record.role == role and record.session == session:
                last = (record.kind, record.round)
        return last

    def policy(self, role: str) -> str | None:
        """The Role's Respawn policy: its last respawn line, else never for a
        reviewer and None (unset) for the Coder."""
        found = self.policies.get(role)
        if found is None and role != "Coder":
            return "never"
        return found

    def once_pending(self, role: str) -> bool:
        """Whether a respawn-once request for the Role waits for its next
        spawn."""
        return self.once.get(role, False)

    def spawned_before(self, role: str) -> bool:
        """Whether an earlier session spawned or resumed the Role."""
        session = self.session()
        return any(r.role == role and r.session < session for r in self.spawns)

    def spawn_reason(self, role: str, number: int) -> str | None:
        """The reason of the Role's last spawn for the round in this
        session, or None."""
        session = self.session()
        found: str | None = None
        for record in self.spawns:
            if record.kind == "spawn" and record.role == role and record.round == number and record.session == session:
                found = record.reason
        return found

    def tokens(self, role: str, number: int) -> int | None:
        return self.counts.get((role, number))

    def any_spawn(self) -> bool:
        """Whether this session has recorded a spawn or resume."""
        session = self.session()
        return bool(session) and any(r.session == session for r in self.spawns)

    def acted(self, role: str, number: int) -> bool:
        return (role, number, True) in self.returns

    def misses(self, role: str, number: int) -> int:
        return self.returns.count((role, number, False))

    def rung(self) -> int:
        return self.place.planner_round()

    def position(self) -> loopstate.Position:
        return self.place.position()

    def done(self, role: str, number: int) -> bool:
        if role == "Coder":
            return self.state.code_mark("end", number) is not None
        kind = "plan" if role == "Plan-Reviewer" else "code"
        return self.state.review(kind, number) is not None

    def path(self, name: str) -> str:
        return "%s/%s" % (self.loop.tracker, name)

    # --- the lines printed ---

    def command(self, text: str) -> str:
        return "%s %s" % (places.command(), text)

    def return_command(self, role: str) -> str:
        return self.command("orchestrator return --role %s --slug %s --harness %s" % (role, self.slug,
                                                                                      self.harness.name))

    def ring_command(self) -> str:
        return doorbells.ring_command("Orchestrator", self.harness, self.slug)

    def check_command(self, role: str) -> str:
        if role == "Coder":
            return "coder check --slug %s --write" % self.slug
        return "review check --role %s --slug %s --write" % (role, self.slug)


def lists(flow: Flow, role: str, number: int) -> tuple[list[str], list[str]]:
    """The Read and Write lists of a Role's round, every path under the
    tracker directory."""
    if role == "Plan-Reviewer":
        read = (["PLAN-REVIEW.md"] if number > 1 else []) + ["spec.md", "issues/"]
        write = ["PLAN-REVIEW.md"]
    elif role == "Coder":
        read = (["CODEREVIEW.md"] if number > 1 else []) + ["spec.md", "issues/"]
        write = ["FIXES.md", "issues/ (the ticked checkboxes)"]
    else:
        read = ["CODEREVIEW.md", "spec.md", "issues/"] if number > 1 else ["spec.md", "issues/", "FIXES.md"]
        write = ["CODEREVIEW.md"]
    return [flow.path(name) for name in read], [flow.path(name) for name in write]


def handoff(flow: Flow, role: str, number: int) -> str:
    """The resume message that starts a live Role's round: the other Role's
    Doorbell line for it."""
    if role == "Coder":
        review = flow.state.review("code", number - 1)
        if review is None:
            raise RuntimeError("No code review is recorded for round %d." % (number - 1))
        return loopstate.review_doorbell(review)
    if role == "Code-Reviewer":
        return loopstate.coder_doorbell(number)
    return loopstate.planner_doorbell(flow.loop.tracker, number)


def next_after(flow: Flow, role: str) -> str:
    return ("When it returns, act on its last line as your skill says; for anything but QUESTION or BLOCKED, run %s"
            % flow.return_command(role))


def spawn(flow: Flow, out: Output, role: str, number: int, reason: str | None = None,
          first: str | None = None) -> int:
    """Record a fresh spawn and print it. first, when given, is a step to
    take before it."""
    flow.append(loopstate.spawn_line(role, number, flow.session(), reason))
    read, write = lists(flow, role, number)
    out.line("Spawning %s, <model>, round %d%s." % (role, number, ", " + reason if reason else ""))
    out.line("Read: %s" % ", ".join(read))
    out.line("Write: %s" % ", ".join(write))
    before = "%s Then print" % first if first else "Print"
    return out.finish(
        "%s the Spawning line above in your reply, <model> filled in from Model approval, then spawn a fresh %s "
        "with the Spawn prompt, the slug %s, round %d and the Read and Write lists above. %s"
        % (before, role, flow.slug, number, next_after(flow, role))
    )


def resume(flow: Flow, out: Output, role: str, number: int, message: str, first: str | None = None) -> int:
    flow.append(loopstate.resume_line(role, number, flow.session()))
    out.line("Resuming %s, round %d." % (role, number))
    out.line("Resume message:")
    out.line(message)
    before = "%s Then resume" % first if first else "Resume"
    return out.finish(
        "%s the same %s with the resume message above as the whole message, nothing added but what your "
        "Harness file says every resume message carries. %s" % (before, role, next_after(flow, role))
    )


def size(count: int) -> str:
    return "%dk" % round(count / 1000.0) if count >= 1000 else str(count)


def limit_of(policy: str | None) -> int | None:
    match = POLICY.match(policy or "")
    if not match or not match.group(2):
        return None
    return int(match.group(2)) * (1000 if match.group(3) else 1)


def step(flow: Flow, out: Output, role: str, number: int, first: str | None = None,
         fresh: str | None = None) -> int:
    """Spawn or resume role for round number, by its Respawn policy: a Role
    with no live subagent in this session is spawned, for fresh when given;
    one with a live subagent is respawned on a once request, every round, or
    over its limit, and resumed otherwise."""
    live = flow.out(role)
    if live is None:
        reason = fresh or ("after a restart" if flow.spawned_before(role) else None)
        return spawn(flow, out, role, number, reason, first)
    if flow.once_pending(role):
        return spawn(flow, out, role, number, "respawn on request", first)
    policy = flow.policy(role) or "never"
    if live[1] != number and policy == "every round":
        return spawn(flow, out, role, number, "respawn every round", first)
    limit = limit_of(policy)
    if live[1] != number and limit is not None and flow.harness.name == "claude-code":
        count = flow.tokens(role, live[1])
        if count is None:
            if first:
                out.line("First: %s" % first)
            out.line("The %s's Respawn policy is %s, and no token count is recorded for its round %d."
                     % (role, policy, live[1]))
            return out.finish(
                "Run %s, with subagent_tokens from the %s's latest completion notice; it records the count and "
                "prints the step that waits for it." % (flow.command(
                    "orchestrator tokens --role %s --tokens <subagent_tokens> --slug %s" % (role, flow.slug)), role)
            )
        if count > limit:
            return spawn(flow, out, role, number, "respawn at %s" % size(count), first)
    return resume(flow, out, role, number, handoff(flow, role, number), first)


def planner_wait(flow: Flow) -> str:
    return doorbells.wait_or_hold(flow.place, "Orchestrator", flow.harness)


def ring_then_wait(flow: Flow, out: Output) -> int:
    return out.finish(
        "Relay the last plan review to the Planner: run %s in the foreground, then do what its Next: line says: it names the wait for the Planner's next "
        "Doorbell." % flow.ring_command()
    )


def after_sign_off(flow: Flow, out: Output) -> int:
    """The step after the code Sign-off: the fold while no fold outcome is
    recorded, on every PR: value, else the PR step."""
    out.line("Code Loop: signed off.")
    if flow.state.fold_owed():
        out.line("Fold: not run yet.")
        return out.finish(
            "Run %s, relay its Tell the user verbatim line, then do what its Next: line says." % flow.command(
                "loop fold --slug %s --harness %s --write" % (flow.slug, flow.harness.name))
        )
    # Not owed after a signed-off review means a fold line is recorded.
    outcome = flow.state.fold_record()
    out.line("Fold: %s." % (outcome.kind if outcome else "not run yet"))
    return out.finish(signoff.pr_step(flow.loop))


# --- where the Workflow stands ---

def describe(flow: Flow) -> str:
    plan = flow.state.last_review("plan")
    rung = flow.rung()
    if plan and plan.signed_off and flow.position().owed_by("Plan-Reviewer"):
        plan_text = "signed off in round %d; the Planner rang round %d after it, not reviewed yet" % (
            plan.round, rung)
    elif plan and plan.signed_off:
        plan_text = "signed off in round %d" % plan.round
    elif rung > (plan.round if plan else 0):
        plan_text = "the Planner rang round %d, not reviewed yet" % rung
    elif plan:
        plan_text = "round %d reviewed, %d blocker, %d major, %d minor open; the Planner owns the next move" % (
            (plan.round,) + tuple(plan.counts))
    else:
        plan_text = "the Planner has rung no round yet"
    code = flow.state.last_review("code")
    newest = flow.state.code_round()
    if code and code.signed_off:
        code_text = "signed off in round %d" % code.round
    elif newest and flow.state.code_mark("end", newest) is None:
        code_text = "Coder round %d started, not finished" % newest
    elif newest and (code is None or code.round < newest):
        code_text = "Coder round %d done, not reviewed" % newest
    elif code and code.user:
        code_text = "reopened by the user's findings after round %d, %d blocker, %d major, %d minor open" % (
            (code.round,) + tuple(code.counts))
    elif code:
        code_text = "round %d reviewed, %d blocker, %d major, %d minor open" % ((code.round,) + tuple(code.counts))
    else:
        code_text = "not started"
    return "Plan Loop: %s. Code Loop: %s." % (plan_text, code_text)


def policies_line(flow: Flow) -> str:
    return "Respawn policies: %s." % ", ".join(
        "%s %s" % (role, flow.policy(role) or "not set") for role in ("Coder", "Plan-Reviewer", "Code-Reviewer"))


def quoted(value: str) -> str:
    return '"%s"' % value if " " in value else value


def respawn_question(flow: Flow) -> str:
    recommended, limit = flow.harness.respawn_recommendation()
    answers = [("Every round", "every round"), ("Never", "never")]
    if limit:
        answers.append(("Over a limit of the Coder's token count, for example %s; the user may name another "
                        "number" % limit, limit))
    parts = []
    for label, value in answers:
        mark = " (recommended)" if value == recommended else ""
        parts.append("\"%s\"%s (--policy %s)." % (label, mark, quoted(value)))
    return ("Respawn question: When should the Orchestrator respawn the Coder, spawning it anew for a round in "
            "place of resuming the one before? Answers, in this order: " + " ".join(parts))


def start(flow: Flow) -> int:
    previous = flow.session()
    out = Output()
    out.line("Loop: %s, open. Harness: %s. Read %s, the Harness file this skill's Harnesses index links, now, once."
             % (flow.slug, flow.harness_label, flow.loop.harness_file()))
    out.line(describe(flow))
    out.line(policies_line(flow))
    if flow.policy("Coder") is None:
        out.line(respawn_question(flow))
        return out.finish(
            "Ask Model approval and the Respawn question above in one message, and wait for the user. Then run %s"
            % flow.command('orchestrator respawn --role Coder --policy "<answer>" --slug %s --write' % flow.slug)
        )
    flow.append(loopstate.session_line(previous + 1))
    # A wait an earlier session started wakes that session, not this one.
    doorbells.clear_marker(flow.place, "Orchestrator")
    # The placement below acts on every Doorbell rung so far.
    doorbells.mark_handled(flow.place, "Orchestrator", out)
    reason = "after a restart" if previous else None
    code = flow.state.last_review("code")
    if code and code.user and flow.state.code_mark("start", code.round + 1) is None:
        # The plan Loop is long over: no ring, and nothing restarted.
        return spawn(flow, out, "Coder", code.round + 1, USER_REASON)
    where = flow.position()
    if where.phase == "code":
        first = "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command()
        if where.signed_off:
            out.line("First: %s" % first)
            return after_sign_off(flow, out)
        return spawn(flow, out, where.owes, where.round, reason, first)
    if where.owed_by("Plan-Reviewer"):
        return spawn(flow, out, "Plan-Reviewer", where.round, reason)
    if flow.state.last_review("plan"):
        return ring_then_wait(flow, out)
    return out.finish(planner_wait(flow))


# --- return ---

def fixed_resume(flow: Flow, role: str, number: int) -> str:
    return ("Round %d is not finished: `%s` has not passed. Run it, fix what it reports until it passes, then end "
            "your turn with the line it prints." % (number, flow.check_command(role)))


def already(role: str, number: int) -> NoReturn:
    raise Failure(
        "%s round %d was already acted on." % (role, number),
        "Nothing to do for this return; go on with the step the tool printed before it.",
    )


def returned(flow: Flow, role: str) -> int:
    if role == "Planner":
        return planner_returned(flow)
    live = flow.out(role)
    if live is None:
        raise Failure(
            "No %s is out in this Orchestrator session, so there is no return to act on." % role,
            "Run %s" % flow.command("orchestrator start --slug %s --harness %s" % (flow.slug, flow.harness.name)),
        )
    number = live[1]
    if flow.acted(role, number):
        already(role, number)
    out = Output()
    if not flow.done(role, number):
        flow.append(loopstate.return_line(role, number, False))
        if flow.misses(role, number) == 1:
            out.line("%s round %d ended without `%s`: the round is not finished." % (
                role, number, flow.check_command(role)))
            return resume(flow, out, role, number, fixed_resume(flow, role, number))
        out.line("%s round %d ended without `%s` a second time." % (role, number, flow.check_command(role)))
        out.tell("The %s ended round %d twice without finishing it. Answer resume to resume it once more, respawn "
                 "to start a fresh %s for round %d, or stop." % (role, number, role, number))
        return out.finish(
            "Relay the line above and end your turn; the user decides. On resume, resume the same %s with the "
            "user's words as the message. On respawn, run %s. On stop, stop." % (
                role, flow.command("orchestrator respawn --role %s --once --slug %s --write" % (role, flow.slug)))
        )
    flow.append(loopstate.return_line(role, number, True))
    if role == "Coder":
        out.line("Code Loop: Coder round %d done." % number)
        fresh = USER_REASON if flow.spawn_reason("Coder", number) == USER_REASON else None
        return step(flow, out, "Code-Reviewer", number, fresh=fresh)
    if role == "Code-Reviewer":
        review = flow.state.review("code", number)
        if review is None:
            raise RuntimeError("done found no code review for round %d." % number)
        if review.signed_off:
            return after_sign_off(flow, out)
        out.line("Code Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
            (number,) + tuple(review.counts)))
        return step(flow, out, "Coder", number + 1)
    review = flow.state.review("plan", number)
    if review is None:
        raise RuntimeError("done found no plan review for round %d." % number)
    if review.signed_off:
        out.line("Plan Loop: signed off in round %d." % number)
        first = "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command()
        return step(flow, out, "Coder", 1, first)
    out.line("Plan Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
        (number,) + tuple(review.counts)))
    return ring_then_wait(flow, out)


def planner_returned(flow: Flow) -> int:
    """After doorbell take printed the Planner's Doorbell: the Plan-Reviewer's
    spawn for the rung round, or its resume when one is live."""
    plan = flow.state.last_review("plan")
    number = (plan.round if plan else 0) + 1
    if plan is not None and plan.signed_off and flow.position().ring_ignored:
        raise Failure(
            [
                "The Planner rang plan round %d after the plan Sign-off in round %d, and the code Loop has started: "
                "no Plan-Reviewer reviews it." % (flow.rung(), plan.round),
                TELL % ("The plan Loop is signed off and the code Loop is running, so the Planner's plan round %d "
                        "is not reviewed. The code Loop goes on with the Spec as it was signed off." % flow.rung()),
            ],
            "Relay the Tell the user verbatim line above unchanged, then go on with the step you were on before "
            "the Planner's Doorbell. Spawn no Plan-Reviewer.",
        )
    if flow.rung() < number:
        raise Failure(
            "The Planner has rung no round after the last plan review: there is nothing to act on.",
            "Nothing to do for this return; go on with the step the tool printed before it.",
        )
    live = flow.out("Plan-Reviewer")
    if flow.acted("Planner", number) or (live is not None and live[1] == number):
        already("Planner", number)
    flow.append(loopstate.return_line("Planner", number, True))
    out = Output()
    out.line("Plan Loop: the Planner rang round %d." % number)
    return step(flow, out, "Plan-Reviewer", number)


# --- respawn and tokens ---

def respawn(flow: Flow, values: dict[str, Any]) -> int:
    role = values["role"]
    args.choice(role, HOSTED, "--role takes Plan-Reviewer, Coder or Code-Reviewer.", "Run %s for the usage." % usage())
    if (values["policy"] is None) == (not values["once"]):
        raise Failure("Give --policy or --once, not both and not neither.", "Run %s for the usage." % usage())
    out = Output()
    if values["once"]:
        if not values["write"]:
            out.line("Would make the %s's next spawn fresh." % role)
            return out.finish("Run the same command with --write.")
        flow.append(loopstate.respawn_once_line(role))
        live = flow.out(role)
        if live is not None and not flow.acted(role, live[1]) and not flow.done(role, live[1]):
            out.line("The %s's round %d is unfinished: a fresh %s takes it over." % (role, live[1], role))
            return spawn(flow, out, role, live[1], "respawn on request")
        out.line("The %s's next spawn is fresh." % role)
        if live is not None and not flow.acted(role, live[1]):
            # A BLOCKED after the round's check --write passed: the round is
            # done and its return is still owed.
            out.line("The %s's round %d is finished and not acted on yet." % (role, live[1]))
            return out.finish("Run %s" % flow.return_command(role))
        return out.finish("Go on with the step the tool printed before it.")
    policy = " ".join(values["policy"].split()).lower()
    match = POLICY.match(policy)
    if match is None:
        raise Failure(
            "--policy %s is not a Respawn policy. It takes \"every round\", never, or \"over <n>k\" with <n> a whole "
            "number from 1." % values["policy"],
            "Ask the user again with those answers, then run the command with one of them.",
        )
    if match.group(2) and flow.harness.name != "claude-code":
        raise Failure(
            "over <n> works only on Claude Code: %s reports no subagent token count." % flow.harness_label,
            "Ask the user for \"every round\" or never instead.",
        )
    if not values["write"]:
        out.line("Would set: respawn %s %s." % (role, policy))
        return out.finish("Run the same command with --write.")
    flow.append(loopstate.respawn_line(role, policy))
    out.line(policies_line(flow))
    if flow.any_spawn():
        return out.finish("The policy applies from the Role's next round; go on with the step the tool printed "
                          "before it.")
    return out.finish("Run %s" % flow.command("orchestrator start --slug %s --harness %s" % (flow.slug,
                                                                                           flow.harness.name)))


def tokens(flow: Flow, values: dict[str, Any]) -> int:
    args.require(values, ["role", "tokens"], usage())
    role = values["role"]
    args.choice(role, HOSTED, "--role takes Plan-Reviewer, Coder or Code-Reviewer.", "Run %s for the usage." % usage())
    if flow.harness.name != "claude-code":
        raise Failure(
            "%s reports no subagent token count, so there is none to record." % flow.harness_label,
            "Go on with the step the tool printed before it.",
        )
    if not re.fullmatch(r"[0-9]+", values["tokens"]):
        raise Failure("--tokens takes a whole number: subagent_tokens from the completion notice.",
                      "Run the command again with the number.")
    live = flow.out(role)
    if live is None:
        raise Failure(
            "No %s is out in this Orchestrator session, so no count is asked for." % role,
            "Go on with the step the tool printed before it.",
        )
    count = int(values["tokens"])
    flow.append(loopstate.tokens_line(role, live[1], count))
    out = Output()
    out.line("Recorded: %s round %d, %s tokens." % (role, live[1], size(count)))
    waiting = waiting_step(flow, role)
    if waiting is None or waiting == live[1]:
        return out.finish("Go on with the step the tool printed before it.")
    return step(flow, out, role, waiting)


def waiting_step(flow: Flow, role: str) -> int | None:
    """The round of role the Workflow waits to spawn or resume, or None."""
    where = flow.position()
    return where.round if where.owed_by(role) else None
