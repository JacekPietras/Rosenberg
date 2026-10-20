---
name: fact-person-identification
description: Identify which person record a source fact refers to and propose a people.json ID only when the evidence distinguishes that person.
---

# Fact person identification

Use when a fact needs to be linked to a specific person in `data/people.json`, especially when several people share a name. This is a research and recommendation workflow; do not change the fact or person record unless separately asked to edit it.

## Evidence review

1. Read `../../../rules/facts.md` and `../../../rules/json-formats.md`. Read the complete source entry, including the German text, date, citation, translation, and relevant image/seal annotations. Treat German as authoritative.
2. Read `../../../data/people.json` and compare every plausible candidate, including names, titles, dates, spouses, children, and other recorded relationships. Search related source facts and entries for each candidate. Follow connected people and family relations; inspect seal descriptions or linked seal evidence where available.
3. Weigh independent evidence together: distinctive relationships, places, offices, chronology, transactions, associates, and seals may identify a person. A matching name, family, place, or witness role by itself is not enough. Never infer kinship from proximity or business association.
4. Validate titles against dated evidence. Titles can change over a person's life: `der Jüngere` may later be `der Ältere`, and `Edelknecht` may later be `Ritter`. Treat these as time-sensitive clues, not automatic contradictions or proof of identity.
5. Use subagents for bounded, independent checks when available (for example, one for candidate biographies and relations, another for source/seal evidence). Give each the source citation and candidate IDs; reconcile their evidence yourself. Do not let consensus replace source support.

## Decision and report

- Propose one `people.json` ID only when the source and corroborating evidence rule out plausible same-name candidates. Cite the exact source passage and summarize the discriminating evidence, including relevant dates, relationships, titles, and seal evidence.
- If candidates remain indistinguishable, evidence conflicts, or needed source material is unavailable, say **Unresolved** and do not choose an ID. State what evidence is missing or ambiguous.
- Report the fact and source citation, candidate IDs considered, evidence for and against the leading candidate, conclusion (`Identified: <id>` or `Unresolved`), and recommendation. Separate explicit source statements from inferences.
- If asked to apply a replacement, edit only the specified fact after the identity decision is conclusive. Preserve its wording and all surrounding JSON structure unless the user requests a wording change; validate JSON and review the diff.
