# Test plan, records and errata

Testing is planned from the requirements, not improvised at the bench. The scaffold
(`scripts/new_project.py`) creates the files named here under `testing/` and `docs/`.

## 1. Traceability
`testing/test-plan.md` has one row per test. Every requirement from G0 (R1, R2, ... in
`docs/design-notes.md`) is covered by at least one test, and every test names the
requirement it verifies. Limits come from the calculations and simulations in the
design report; a test without numeric limits is not a test. Show coverage as a table:

| Requirement | Tests | Covered |
|---|---|---|

A requirement with no test is listed as a gap, with the reason.

## 2. Stages
| Stage | When | Typical content |
|---|---|---|
| First article | First board of each fab or assembly batch | `testing/first-article.md`: dimensions, finish, silkscreen and QR, orientation of polarised parts, mating, fit |
| Bring-up | First power-on of each board | `testing/bringup.md`, generated from `dft-bringup.md` §6 with this board's rails and expected values |
| Functional | Every board | Interfaces, loopbacks, analogue performance against limits |
| Production | Every board, on a fixture | Automated subset of functional, programming, serial number |
| Qualification | Once per revision | Temperature, supply corners, EMC pre-compliance, long run |

## 3. Records
One file per board in `testing/results/<serial>.md` from `TEMPLATE.md`: serial, revision,
who, when, firmware, equipment with calibration, measured values against limits, a
photo of the board as tested, deviations and rework, verdict. Add scope screenshots and
plots as images next to the numbers they support.

Summarise a batch in one table and one chart per key measurement (value per serial
against its limits) rather than in prose.

## 4. Design for the test
Decide at G2, with `dft-bringup.md`: testpoints for every limit in the plan, a way to
load each rail, a programming path, and what the production fixture touches (pogo-pin
pads on a grid, tooling holes). If a test in the plan cannot be executed on the board
as designed, change the board.

## 5. Errata and the next revision
Every problem found on real boards goes into `docs/errata.md`: revision, serial, problem,
root cause, workaround for built boards, fix for the next revision. Starting a new
revision begins by reading it and turning each open row into a change or an explicit
decision not to change.
