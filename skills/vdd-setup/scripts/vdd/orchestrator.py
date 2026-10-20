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

import os
import re

from . import args, doorbells, fold, gitcmd, harness as harnesses, loopfile, loopstate, places
from .out import Failure, Output

SUBCOMMANDS = ("start", "return", "respawn", "tokens")
POLICY = re.compile(r"^(every round|never|over ([1-9][0-9]*)(k?))$")
HOSTED = ("Plan-Reviewer", "Coder", "Code-Reviewer")
SKILLS = {"Plan-Reviewer": "vdd-plan-reviewer", "Coder": "vdd-coder", "Code-Reviewer": "vdd-code-reviewer"}

HELP = [
    "orchestrator start --slug <slug> [--harness <h>]",
    "  Run on every start of the Orchestrator's Session, a restart included. Records a new session, names the",
    "  Harness and its Harness file, says where each Loop stands, and prints the one next step: a spawn, the",
    "  ring to the Planner, the wait for the Planner's Doorbell, the fold at the code Sign-off, or the PR",
    "  step. Every spawn after a restart is fresh.",
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


def usage():
    return "%s orchestrator --help" % places.command()


def run(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        out = Output()
        for line in HELP:
            out.line(line)
        return out.finish("Run the orchestrator command your skill or the last Next: line names.")
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        args.unknown_command("orchestrator " + sub, usage())
    values = args.parse(rest, SPECS[sub], usage())
    if values["help"]:
        return run(["--help"])
    flow = Flow.find(values, "orchestrator %s" % sub)
    if sub == "start":
        return start(flow)
    if sub == "respawn":
        return respawn(flow, values)
    if sub == "tokens":
        return tokens(flow, values)
    args.require(values, ["role", "harness"], usage())
    role = values["role"]
    if role not in HOSTED + ("Planner",):
        raise Failure("--role takes Planner, Plan-Reviewer, Coder or Code-Reviewer.", "Run %s for the usage." % usage())
    return returned(flow, role)


class Flow:
    """One loop as the Orchestrator sees it: its state file, its Doorbell
    file and the Harness the Loop file names."""

    @classmethod
    def find(cls, values, command):
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

    def __init__(self, loop, state):
        self.loop = loop
        self.state = state
        self.slug = loop.slug
        self.harness = harnesses.get(loopfile.harness_slug(loop.setting("Harness")[0]))
        # The Loop file's own value: Generic's Harness module has no label.
        self.harness_label = loop.setting("Harness")[0]
        self.place = doorbells.Place(loop.root, loop.slug)
        self.place.loop = loop

    # --- the state, as the Orchestrator needs it ---

    def session(self):
        number = 0
        for line in self.state.lines:
            match = re.match(r"^orchestrator session ([0-9]+)$", line)
            if match:
                number = int(match.group(1))
        return number

    def out(self, role, session=None):
        """(kind, round) of the Role's last spawn or resume in the session,
        or None: whether a live subagent of that Role is out."""
        session = self.session() if session is None else session
        last = None
        for line in self.state.lines:
            match = re.match(r"^(spawn|resume) (\S+) ([0-9]+) session ([0-9]+)(\s|$)", line)
            if match and match.group(2) == role and int(match.group(4)) == session:
                last = (match.group(1), int(match.group(3)))
        return last

    def policy(self, role):
        """The Role's Respawn policy: its last respawn line, else never for a
        reviewer and None (unset) for the Coder."""
        found = None
        prefix = "respawn %s " % role
        for line in self.state.lines:
            if line.startswith(prefix):
                found = line[len(prefix):].strip()
        if found is None and role != "Coder":
            return "never"
        return found

    def once_pending(self, role):
        """Whether a respawn-once request for the Role waits for its next
        spawn."""
        pending = False
        for line in self.state.lines:
            if line == "respawn-once %s" % role:
                pending = True
            elif re.match(r"^spawn %s [0-9]+ " % re.escape(role), line):
                pending = False
        return pending

    def spawned_before(self, role):
        """Whether an earlier session spawned or resumed the Role."""
        session = self.session()
        for line in self.state.lines:
            match = re.match(r"^(spawn|resume) (\S+) [0-9]+ session ([0-9]+)", line)
            if match and match.group(2) == role and int(match.group(3)) < session:
                return True
        return False

    def tokens(self, role, number):
        found = None
        for line in self.state.lines:
            match = re.match(r"^tokens (\S+) ([0-9]+) ([0-9]+)$", line)
            if match and match.group(1) == role and int(match.group(2)) == number:
                found = int(match.group(3))
        return found

    def any_spawn(self):
        """Whether this session has recorded a spawn or resume."""
        session = self.session()
        return any(re.match(r"^(spawn|resume) \S+ [0-9]+ session %d(\s|$)" % session, line)
                   for line in self.state.lines) if session else False

    def acted(self, role, number):
        return ("return %s %d ok" % (role, number)) in self.state.lines

    def misses(self, role, number):
        return self.state.lines.count("return %s %d miss" % (role, number))

    def rung(self):
        rounds = [e.doorbell.round for e in self.place.entries("Orchestrator", doorbells.LOCK_RETRY_SECONDS)
                  if e.doorbell]
        return max(rounds) if rounds else 0

    def done(self, role, number):
        if role == "Coder":
            return self.state.code_mark("end", number) is not None
        kind = "plan" if role == "Plan-Reviewer" else "code"
        return self.state.review(kind, number) is not None

    def path(self, name):
        return "%s/%s" % (self.loop.tracker, name)

    # --- the lines printed ---

    def command(self, text):
        return "%s %s" % (places.command(), text)

    def return_command(self, role):
        return self.command("orchestrator return --role %s --slug %s --harness %s" % (role, self.slug,
                                                                                      self.harness.name))

    def ring_command(self):
        return doorbells.ring_command("Orchestrator", self.harness, self.slug)

    def check_command(self, role):
        if role == "Coder":
            return "coder check --slug %s --write" % self.slug
        return "review check --role %s --slug %s --write" % (role, self.slug)


def lists(flow, role, number):
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


def handoff(flow, role, number):
    """The resume message that starts a live Role's round: the other Role's
    Doorbell line for it."""
    if role == "Coder":
        return loopstate.review_doorbell(flow.state.review("code", number - 1))
    if role == "Code-Reviewer":
        return loopstate.coder_doorbell(number)
    return loopstate.planner_doorbell(flow.loop.tracker, number)


def next_after(flow, role):
    return ("When it returns, act on its last line as your skill says; for anything but QUESTION or BLOCKED, run %s"
            % flow.return_command(role))


def spawn(flow, out, role, number, reason=None, first=None):
    """Record a fresh spawn and print it. first, when given, is a step to
    take before it."""
    flow.state.append("spawn %s %d session %d%s" % (role, number, flow.session(),
                                                     " reason " + reason if reason else ""))
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


def resume(flow, out, role, number, message, first=None):
    flow.state.append("resume %s %d session %d" % (role, number, flow.session()))
    out.line("Resuming %s, round %d." % (role, number))
    out.line("Resume message:")
    out.line(message)
    before = "%s Then resume" % first if first else "Resume"
    return out.finish(
        "%s the same %s with the resume message above as the whole message, nothing added but what your "
        "Harness file says every resume message carries. %s" % (before, role, next_after(flow, role))
    )


def size(count):
    return "%dk" % round(count / 1000.0) if count >= 1000 else str(count)


def limit_of(policy):
    match = POLICY.match(policy or "")
    if not match or not match.group(2):
        return None
    return int(match.group(2)) * (1000 if match.group(3) else 1)


def step(flow, out, role, number, first=None):
    """Spawn or resume role for round number, by its Respawn policy: a Role
    with no live subagent in this session is spawned; one with a live
    subagent is respawned on a once request, every round, or over its limit,
    and resumed otherwise."""
    live = flow.out(role)
    if live is None:
        reason = "after a restart" if flow.spawned_before(role) else None
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


def planner_wait(flow):
    return doorbells.wait_or_hold(flow.place, "Orchestrator", flow.harness)


def ring_then_wait(flow, out):
    return out.finish(
        "Relay the last plan review to the Planner: run %s in the foreground, then do what its Next: line says: it names the wait for the Planner's next "
        "Doorbell." % flow.ring_command()
    )


def after_sign_off(flow, out):
    """The step after the code Sign-off: the fold while no fold outcome is
    recorded, on every PR: value, else the PR step."""
    out.line("Code Loop: signed off.")
    outcome = flow.state.fold_outcome()
    if outcome is None:
        out.line("Fold: not run yet.")
        return out.finish(
            "Run %s, relay its Tell the user verbatim line, then do what its Next: line says." % flow.command(
                "loop fold --slug %s --harness %s --write" % (flow.slug, flow.harness.name))
        )
    out.line("Fold: %s." % outcome[0])
    return out.finish(fold.pr_step(flow.loop))


# --- where the Workflow stands ---

def describe(flow):
    plan = flow.state.last_review("plan")
    rung = flow.rung()
    if plan and plan.signed_off:
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
    elif code:
        code_text = "round %d reviewed, %d blocker, %d major, %d minor open" % ((code.round,) + tuple(code.counts))
    else:
        code_text = "not started"
    return "Plan Loop: %s. Code Loop: %s." % (plan_text, code_text)


def code_place(flow):
    """(role, round) the code Loop owes next, or None at its Sign-off."""
    review = flow.state.last_review("code")
    if review and review.signed_off:
        return None
    newest = flow.state.code_round()
    if newest and flow.state.code_mark("end", newest) is None:
        return ("Coder", newest)
    if newest and (review is None or review.round < newest):
        return ("Code-Reviewer", newest)
    return ("Coder", review.round + 1 if review else 1)


def policies_line(flow):
    return "Respawn policies: %s." % ", ".join(
        "%s %s" % (role, flow.policy(role) or "not set") for role in ("Coder", "Plan-Reviewer", "Code-Reviewer"))


def quoted(value):
    return '"%s"' % value if " " in value else value


def respawn_question(flow):
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


def start(flow):
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
    flow.state.append("orchestrator session %d" % (previous + 1))
    # A wait an earlier session started wakes that session, not this one.
    doorbells.clear_marker(flow.place, "Orchestrator")
    # The placement below acts on every Doorbell rung so far.
    doorbells.mark_handled(flow.place, "Orchestrator", out)
    reason = "after a restart" if previous else None
    plan = flow.state.last_review("plan")
    reviewed = plan.round if plan else 0
    if plan and plan.signed_off and flow.rung() <= plan.round:
        where = code_place(flow)
        first = "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command()
        if where is None:
            out.line("First: %s" % first)
            return after_sign_off(flow, out)
        role, number = where
        return spawn(flow, out, role, number, reason, first)
    if flow.rung() > reviewed:
        return spawn(flow, out, "Plan-Reviewer", reviewed + 1, reason)
    if plan:
        return ring_then_wait(flow, out)
    return out.finish(planner_wait(flow))


# --- return ---

def fixed_resume(flow, role, number):
    return ("Round %d is not finished: `%s` has not passed. Run it, fix what it reports until it passes, then end "
            "your turn with the line it prints." % (number, flow.check_command(role)))


def already(role, number):
    raise Failure(
        "%s round %d was already acted on." % (role, number),
        "Nothing to do for this return; go on with the step the tool printed before it.",
    )


def returned(flow, role):
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
        flow.state.append("return %s %d miss" % (role, number))
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
    flow.state.append("return %s %d ok" % (role, number))
    if role == "Coder":
        out.line("Code Loop: Coder round %d done." % number)
        return step(flow, out, "Code-Reviewer", number)
    if role == "Code-Reviewer":
        review = flow.state.review("code", number)
        if review.signed_off:
            return after_sign_off(flow, out)
        out.line("Code Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
            (number,) + tuple(review.counts)))
        return step(flow, out, "Coder", number + 1)
    review = flow.state.review("plan", number)
    if review.signed_off:
        out.line("Plan Loop: signed off in round %d." % number)
        first = "Run %s in the foreground; the plan Loop is over, so it names no wait." % flow.ring_command()
        return step(flow, out, "Coder", 1, first)
    out.line("Plan Loop: round %d reviewed, %d blocker, %d major, %d minor open." % (
        (number,) + tuple(review.counts)))
    return ring_then_wait(flow, out)


def planner_returned(flow):
    """After doorbell take printed the Planner's Doorbell: the Plan-Reviewer's
    spawn for the rung round, or its resume when one is live."""
    plan = flow.state.last_review("plan")
    number = (plan.round if plan else 0) + 1
    if flow.rung() < number:
        raise Failure(
            "The Planner has rung no round after the last plan review: there is nothing to act on.",
            "Nothing to do for this return; go on with the step the tool printed before it.",
        )
    live = flow.out("Plan-Reviewer")
    if flow.acted("Planner", number) or (live is not None and live[1] == number):
        already("Planner", number)
    flow.state.append("return Planner %d ok" % number)
    out = Output()
    out.line("Plan Loop: the Planner rang round %d." % number)
    return step(flow, out, "Plan-Reviewer", number)


# --- respawn and tokens ---

def respawn(flow, values):
    role = values["role"]
    if role not in HOSTED:
        raise Failure("--role takes Plan-Reviewer, Coder or Code-Reviewer.", "Run %s for the usage." % usage())
    if (values["policy"] is None) == (not values["once"]):
        raise Failure("Give --policy or --once, not both and not neither.", "Run %s for the usage." % usage())
    out = Output()
    if values["once"]:
        if not values["write"]:
            out.line("Would make the %s's next spawn fresh." % role)
            return out.finish("Run the same command with --write.")
        flow.state.append("respawn-once %s" % role)
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
    flow.state.append("respawn %s %s" % (role, policy))
    out.line(policies_line(flow))
    if flow.any_spawn():
        return out.finish("The policy applies from the Role's next round; go on with the step the tool printed "
                          "before it.")
    return out.finish("Run %s" % flow.command("orchestrator start --slug %s --harness %s" % (flow.slug,
                                                                                           flow.harness.name)))


def tokens(flow, values):
    args.require(values, ["role", "tokens"], usage())
    role = values["role"]
    if role not in HOSTED:
        raise Failure("--role takes Plan-Reviewer, Coder or Code-Reviewer.", "Run %s for the usage." % usage())
    if flow.harness.name != "claude-code":
        raise Failure(
            "%s reports no subagent token count, so there is none to record." % flow.harness_label,
            "Go on with the step the tool printed before it.",
        )
    if not values["tokens"].isdigit():
        raise Failure("--tokens takes a whole number: subagent_tokens from the completion notice.",
                      "Run the command again with the number.")
    live = flow.out(role)
    if live is None:
        raise Failure(
            "No %s is out in this Orchestrator session, so no count is asked for." % role,
            "Go on with the step the tool printed before it.",
        )
    count = int(values["tokens"])
    flow.state.append("tokens %s %d %d" % (role, live[1], count))
    out = Output()
    out.line("Recorded: %s round %d, %s tokens." % (role, live[1], size(count)))
    waiting = waiting_step(flow, role)
    if waiting is None or waiting == live[1]:
        return out.finish("Go on with the step the tool printed before it.")
    return step(flow, out, role, waiting)


def waiting_step(flow, role):
    """The round of role the Workflow waits to spawn or resume, or None."""
    if role == "Plan-Reviewer":
        plan = flow.state.last_review("plan")
        number = (plan.round if plan else 0) + 1
        return number if flow.rung() >= number else None
    where = code_place(flow)
    if where is None or where[0] != role:
        return None
    return where[1]
