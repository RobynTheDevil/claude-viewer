<!-- SEED:
    The source guide: the document a session reads before editing the project, and the one
    a confirmed fix's reasoning moves into. It describes what is true now. It is not a
    history, a plan, or a list of what was tried.

    Invariants go near the top, before the detail, because they are what a change is checked
    against and the reason the guide is read at all.
-->

# claude-viewer

<Two or three sentences: what it does, for whom, and its state. Working, in progress, or
proposed.>

Open work is in [todo.md](todo.md).

## Invariants

Rules to check a change against. Each one is here because breaking it produced a defect that
took more than one round to find, and each names the mechanism rather than the symptom.

- **<The rule, as an imperative or a fact>.** <Why it holds, and what it looks like when it
  is broken.>

## Structure

<One entry per part of the project, named as the source names it, saying what it owns. A
reader should be able to go from a symptom to a file with this section alone.>

## <Mechanism>

<One section per mechanism worth explaining: what happens, in what order, and which decisions
are made where. Cite file and line for anything load-bearing. If the order matters, say so;
if a diagram would carry it better, that is a separate document this one links to.>

## Tunables

<Constants a person may want to change, with the value, what it controls, and how the value
was arrived at. A measured constant says it was measured.>

## Open design decisions

<Questions not yet settled, and what would settle each. Delete the section when there are
none rather than leaving it saying "none".>
