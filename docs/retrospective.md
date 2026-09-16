# Retrospective

Kanban asks you to inspect the process, not only the product, and this is the
part we had left out. What follows is what actually happened between `WA-01` and
`WA-28`, including the maintenance we did after the project was delivered.

## Where we ended up

| | |
|---|---|
| Work items | 28 cards (`WA-01`–`WA-22` delivery, `WA-23`–`WA-28` after it) |
| Effort planned for the delivery | 95 SP, split 47 / 48 |
| Pull requests | 37 |
| Tests | 177, at 98.77% line and branch coverage against a 90% floor |
| Python versions verified | 3.10 through 3.13 |

## What worked

The rule we were most tempted to skip turned out to be the one that paid. Nobody
approved their own pull request, and the review caught things neither of us
would have found alone — the `WineryTransformer` constructor below being the
clearest case.

The WIP limit of one card each was useful for a reason we did not anticipate. We
expected it to keep us focused; what it actually did was make blockages visible.
When `WA-09` turned out to depend on a class that did not exist yet, there was
no second card to quietly switch to, so we had to deal with it.

And we are glad we wrote the requirements matrix before writing any code. The
material we were given was a test suite and an empty package, so `WA-02` meant
reading the tests and working backwards. Where the tests did not pin the answer
down — the exact stress formula — we wrote the ambiguity down as an open
question instead of guessing, and closed it when the assignment text confirmed
the formula.

## What went wrong

### The fixture that shaped our code

This is the one worth telling properly.

The `conftest.py` we were given replaced Joblib's parallel execution with a
sequential version, so the tests would be deterministic. That replacement ran
every task but never returned the results — a missing `return`. Under test,
`joblib.Parallel(...)(tasks)` therefore always evaluated to `None`.

We did not recognise it as a bug in the fixture. We assumed the test was right
and wrote `run_full_pipeline` around it: small wrapper functions writing into a
shared dictionary as a side effect, and threads instead of processes so the
mutation would be visible. It passed. It stayed that way for nine cards.

It was only during final verification that we looked at the fixture itself and
found the missing word. Adding it let us delete the workaround and read Joblib's
return value directly, which is what the function does today.

**When production code needs an odd shape to satisfy a test, the test is worth
suspecting first.** A test double that quietly differs from the real thing does
not just miss bugs; it puts them there.

### Two ways to break reproducibility without an error

The data generator kept producing different output across runs even though the
seed was fixed, and it took us a while because there were two independent causes
stacked on top of each other.

The first was a Python `set` used to deduplicate labels. Its iteration order is
randomised per process and ignores the seed entirely, so sorting the result
fixed it. The second was Joblib: worker processes do not inherit the parent's
random state, so we had to draw a seed per row in the parent and hand it to each
worker explicitly.

Neither failed. They just produced numbers that changed.

### What integration found and unit tests could not

`WA-08` gave `WineryTransformer.__init__` a required `tank_info` parameter, and
every unit test for that class passed. The pipeline tests constructed
`WineryTransformer()` with no arguments, and nobody noticed until `WA-12` wired
the two together. Unit tests check a component against the assumptions of
whoever wrote it; only integration checks it against the assumptions of whoever
calls it.

### Three defects that did not crash anything

Final verification turned up an inner join dropping readings whose tank was
unknown, null quantities spreading `NaN` across a whole tank's score, and TSV
column types inferred from the first hundred rows only. What they had in common
is that none of them raised anything. Each one produced a CSV that looked
perfectly normal and was wrong.

That is where the rule we now apply everywhere comes from: **fail loudly rather
than return something plausible.**

### Tools that lied to us

The `setup-uv` action accepts a `python-version` input and ignores it, so for a
while we believed CI was pinned to 3.10 when it was running on whatever the
runner happened to provide. Separately, an editable install silently kept
exposing the old package list after `WA-18` changed it, which produced a
`ModuleNotFoundError` that made no sense. And three UML exports came out
byte-identical because the diagram editor's *Save As* had been used instead of
*Export as → PNG*.

### The notebook nobody else could open

After delivery we found that `demo.ipynb` needed `ipykernel`, which was not
declared anywhere. Anyone cloning the repository and following our own setup
guide could not open it. It was invisible to whoever wrote it, because the
package was already on that machine, and invisible to CI, which analysed the
notebook but never ran it.

We fixed both halves: `WA-23` declared the dependency, `WA-24` made CI execute
the notebook so the same kind of defect cannot get through again. Along the way
we found that the notebook also pointed at a kernel that existed on exactly one
computer, which nobody had noticed for the same reason.

### A check that had stopped checking

While setting up the dependency lock we discovered that `black` was skipping
`demo.ipynb` entirely. Checking notebooks needs an extra we had not declared, so
the tool printed one line saying so and carried on. In a job that ends green,
nobody reads that line. `ruff` had been checking the notebook the whole time,
which made it even easier to assume `black` was too.

### Codes that pointed nowhere

We worked on the four maintenance cards before creating them on the board, so
`WA-23` to `WA-26` appeared in branch names and commit messages while no card
with those codes existed. Following one back from a commit led nowhere. `WA-27`
put that right, but it was our own traceability rule that we had broken, in the
space of two days, by moving faster than the board.

## What we would do differently

Treat inherited code with the same suspicion as code under review. The fixture
bug was there from `WA-01` and cost us a workaround that survived nine cards.

Test contracts, not just values. Both reproducibility bugs and the silent join
would have shown up much earlier against assertions like *the same seed produces
the same output* or *a join preserves the row count*, rather than against
specific expected numbers.

Run the formatter before pushing. CI rejected us for the same avoidable reason
across several cards.

Check a deliverable from a clean environment rather than from the machine that
built it. Three separate defects — the undeclared kernel dependency, the
machine-specific kernel name, the formatter that had stopped covering the
notebook — all come back to that one habit.

Create the card before starting the work, not after.

## One thing we did not expect

Four of the problems above turned up *after* the project was delivered and
graded, during maintenance nobody required us to do. We were not looking for
them. They surfaced because we read the CI logs instead of trusting the green
tick, and because each fix was verified from a clean environment rather than
from the machine that produced it.

If there is one thing this project taught us, it is that a green build only
tells you that the checks which ran, passed. It does not tell you that the right
checks ran.
