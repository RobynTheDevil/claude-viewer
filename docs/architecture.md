<!--
    Seed instructions, delete this block once the file has real contents.

    This file starts nearly empty and earns its contents. It holds what is true about the
    external system the repo builds against: the engine, the framework, the host application,
    the API. A session loads it in full at startup, which is how it stops the same discovery
    being made twice.

    What belongs here:
      - The object model, stated once, with the consequence for the work drawn out.
      - The facts that cost a lot to rediscover, especially the ones that present as a dozen
        unrelated symptoms.
      - Where a call is made from, and what the call assumes, with file:line citations.
      - What the decompile, the docs or the source does NOT cover, under Gaps.

    What does not:
      - How one project uses it. That goes in the project's source guide.
      - What was tried and failed. That is a report in docs/<project>/issues.
      - Restating the external system's own documentation where it is accurate and available.

    The test for a finding belonging here rather than in a project guide: would the next
    project hit it too. See the `issues` skill, "Generalise before closing".

    Keep the structure below. The headings are the ones that get used.
-->

# Core architecture

<One paragraph: which system this describes, where the source of truth is, and how much of
it has been read. Name the version.>

## The one thing to know first

<The single structural fact that decides most of the work. A table or three bullets, then the
consequence for a change stated explicitly: to change X, touch A; to change Y, touch B.>

## <Subsystem>

<One section per subsystem that work lands in. Lead with the API or the entry point, cite
file and line, and state what it guarantees. Then the traps, each as its own bolded claim
followed by the evidence:>

**<The trap, stated as a fact>.** <What the code actually does, with the citation, and what
it looks like when you hit it. The symptom first if the symptom is what you will meet.>

## Gaps

- <What is not readable: files not decompiled, assets not extractable, behaviour only
  observable at runtime.>
- <What is known to be inaccurate in the extracted source.>
