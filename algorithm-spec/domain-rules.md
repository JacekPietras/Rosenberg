# Domain rules

What the family reconstruction must respect, stated as genealogy rather than
code. Every rule here is a requirement; [algorithm.md](algorithm.md) and the pass
files describe how they are met. When a rule changes, change it here first.

## Sources and evidence

- Documents and images are primary evidence; books and notes retell them and
  count half as much. A guess is a fact with lower weight, never a special case.
- An unmarked mention means the person was alive at the fact's date. A deceased
  marker or a death fact means he was dead by then.
- Being named as someone's parent or sibling says nothing about being alive at
  that date ("Albrecht, son of the late Eberhard").
- A title belongs to its date. A title of a dead person describes his past.
- Repeating a fact, or reusing the algorithm's own conclusions, is not new
  evidence.
- Seals are compared by people, not by the algorithm.

## Names

- Records can only be the same person if their names match: the same given name
  (using the variants in `data/names.md`) and the same surname, or one record
  without a surname.
- A record without a surname needs family or an identifying title (office,
  designation) to join a full-name record; shared places or associates are not
  enough.
- The section of `data/names.md` (`# Men`, `# Women`) gives a person's gender.
  A given name that is not listed has no known gender.
- Equal names alone never prove identity.

## Identity

- Confirmed registry people (`data/people.json`) are different people and are
  never merged with each other. The reconstruction never changes the registry.
- A false split is an error, just as a false merge is. A record joins its most
  probable same-name candidate unless something forbids it, so that separate
  family trees grow together. The join still needs evidence beyond the name,
  the date and a rank.
- When two candidates are equally good, the record stays separate and both are
  shown as "possibly the same person".
- Within one document file, or one book or notes section, records with the
  same name and the same titles (or both untitled) are one person.

## What makes two records different people

- They are the two participants of one fact.
- In one passage: different age titles (`der Ältere`/`der Jüngere`), a knight
  and a squire (`Ritter`/`Edelknecht`), a deceased and a living mention, or the
  subjects of two separate facts with the same content (two "Hans" in one
  witness list).
- He would be mentioned alive after his death, have two incompatible death
  dates, be older than 80, have living mentions spanning more than 64 years, or
  have a child born more than a year after his death.
- They are known relatives: father and son, grandfather and grandson, uncle and
  nephew, cousins, in-laws. Records of one sibling group, the parents of one
  sibling group, or the spouses of one person may still be one person.
- A kinship term excludes it: a `Vetter` is never the relative's own brother.
  Term meanings are listed in `data/kinship.md`.
- The merged person would be his own relative, his own ancestor, or both
  parent and sibling of someone.

## Parents and siblings

- **One father, one mother.** A person has one father and one mother. Two
  records whose fathers (or mothers) cannot be one person are different people.
  This counts recorded fathers and fathers inherited from a sibling (below).
  Fathers with the same name that can be one person are not a conflict; they
  are joined.
- **Same-named relatives are one person.** Two people with the same name in the
  same role to one person (two fathers, two brothers, two wives or two sons
  named Konrad) are one person, unless something above forbids it.
- **Father from a sibling.** A person takes the recorded father of his sibling
  when the sibling and that father have his surname. Only a father is taken,
  never a mother: siblings with one surname can have different mothers.
  - This rule only adds: the inherited father counts as family evidence and
    lets separate records of that father join.
  - It is not taken if the person already has a different father, or if it
    would make him his own father, an ancestor of himself, or break
    generations. It is withdrawn when a later merge brings such a contradiction.
  - Only recorded fathers are passed on; an inherited father is not passed on
    again.
- Marriage does not supply a second parent, and siblings of siblings are not
  added as siblings.

## Titles and age

- Edelknecht before Ritter is a normal career; Ritter before Edelknecht is
  unlikely. `der Jüngere` before `der Ältere` is normal; the reverse is unlikely.
- A rank, office, `der Ältere`, being a parent or a spouse means he was an adult
  (16). Nobody is older than 80. Ages above 60 are increasingly unlikely.
- Long time distance alone is not evidence against identity; it only weakens
  shared titles, places and family, and raises the implied age.

## Special records

- A standalone widow record may join an established family with the same full
  name that already records her widowhood earlier, unless another person with
  that name could also be meant.
- "May have been the father of X" joins a same-named father only when X's
  parentage is recorded independently as a fact. It never creates a
  relationship itself.

## Results

- Results do not depend on the order of the input.
- Every decision is explainable: features, sources, blocks and alternatives are
  stored in `data/tree.json`.
- Probabilities are uncalibrated estimates, not measured accuracy.
- Expected results are not obtained by person-specific exceptions or by
  lowering thresholds.
