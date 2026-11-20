# Document English person-name recognition migration

## Goal

Use the shared person-name recognition rules to find contextual people in the
English text of document entries. Books, notes, images, and other source types
continue to contribute contextual mentions from facts only. Recognized prose
mentions can support identity matching and contextual links, but never create
family relationship assertions.

## Where recognition happens

Recognition runs only in the linter. `scripts/linters/generate_mentions.mjs`
uses `docs/app/data/person-name-recognition.js` and the place list to write a
`mention` list on each document entry (for its `english` text and the
document's place) and on each generic fact (for its `content`); see
`specs/json-formats.md`. The family graph reads those lists and never
recognizes names or places itself.

- Each observation points at the exact `/entries/N/english` value (or the
  fact) and fingerprints it. A `person` item is the mention reference. Offsets
  are never stored.
- Mentions feed existing contextual matching only. Typed facts and guesses are
  the sole source of relationships.
- Browser verification checks that a prose mention's name appears in the stored
  `mention` list of its entry or fact.

## Evidence and ambiguity rules

- A prose mention identifies a name form, not a registry identity. Registry
  identity still requires an explicit ID or the graph's existing evidence.
- A `mention` list is unique, so repeated occurrences of one recognized name
  count as one contextual mention.
- For a form introduced by `née` or `nee`, use the given name and birth name
  as the contextual name; do not also emit the preceding married surname as a
  separate contextual person. For example, `Elisabeth von Rosenberg, née
  Marschalk von Pappenheim` yields `Elisabeth Marschalk von Pappenheim`.
- Distinct namesakes remain separate unless existing typed evidence joins
  them. A name mention alone does not make two people the same person.
- Text evidence is not a fact or guess and must not affect fact-versus-guess
  filtering or produce relationship derivations.
