# Document English person-name recognition migration

## Goal

Use the shared person-name recognition rules to find contextual people in the
English text of document entries. Books, notes, images, and other source types
continue to contribute contextual mentions from facts only. Recognized prose
mentions can support identity matching and contextual links, but never create
family relationship assertions.

## Migration steps

1. Port the recognizer's matching behavior for family graph use, driven by the
   same names, nobiliary particles, connectors, titles, and place variations as
   `docs/app/data/person-name-recognition.js`. Keep its rules aligned with
   `specs/person-names.md`.
2. Collect each document entry's `english` field as a contextual observation;
   do not collect book or other non-document prose.
3. Give each observation stable provenance by pointing to the exact
   `/entries/N/english` value and fingerprinting that value. Preserve the
   recognized literal name as the mention reference. Do not store offsets,
   which become stale after harmless edits.
4. Feed recognized mentions through existing contextual matching only. Keep
   typed facts and guesses as the sole source of relationships.
5. Update source validation, tree schema documentation, and algorithm rules to
   accept the text pointer and validate it against the current entry text.
6. Add focused regression coverage for document prose, fact-only behavior in
   books and other sources, ambiguity, deduplication, provenance, and the
   absence of prose-derived relationship edges.
7. Rebuild and review `data/tree.json` after implementation.

## Evidence and ambiguity rules

- A prose mention identifies a name form, not a registry identity. Registry
  identity still requires an explicit ID or the graph's existing evidence.
- Repeated occurrences of one recognized name in an entry count as one
  contextual mention.
- Distinct namesakes remain separate unless existing typed evidence joins
  them. A name mention alone does not make two people the same person.
- Text evidence is not a fact or guess and must not affect fact-versus-guess
  filtering or produce relationship derivations.
