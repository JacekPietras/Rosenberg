# Research: genealogical record linkage and historical family reconstruction

Research date: 29 October 2026.

This is a research companion to [the implementation plan](family-tree-algorithm-plan.md).
It distinguishes published methods from proposed adaptations for this repository.
No historical assertions or relationships in `data/` were changed.

## 1. What this problem is called

Yes: identifying repeated references to people and rebuilding their families is
an established genealogical problem. Useful search terms are **genealogical
record linkage**, **entity resolution**, **family reconstitution**, and
**historical population reconstruction**. Family reconstitution has a long
history in linking baptism, marriage, and burial registers. George Alter's
account of the Cambridge family reconstitutions also discusses how selection
and registration affect the reconstructed population.
[Alter, 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC10923557/).

For this repository, **medieval record linkage** and **prosopography** are
particularly relevant. The chapter *Record Linkage in Medieval and Early Modern
Text* addresses inconsistent identification in historical texts and the need to
use titles, professions, provenance, and family relationships in addition to
names. It discusses ChartEx and Traces Through Time.
[Georgala et al., 2015, chapter DOI](https://doi.org/10.1007/978-3-319-19884-2_9);
[chapter text indexed in a repository copy](https://ndl.ethernet.edu.et/bitstream/123456789/53729/1/243.pdf).

The research divides our task into three related problems:

1. Extract what a source asserts about its participants.
2. Decide which mentions refer to the same historical person.
3. Reconstruct relationships while preserving contradictory and uncertain evidence.

**Project interpretation:** our typed source assertions already provide much of
the first layer. The main missing capability is the second layer, followed by
an uncertainty-aware relationship export.

## 2. The closest precedents

### 2.1 ChartEx: people, property, and relationships in medieval charters

ChartEx investigated extracting and linking people, places, events, and
relationships from medieval charters. Its researchers combined historical
expertise, natural language processing, and data mining, and developed an
interactive workbench where historians could inspect and augment the results.
Property transactions were central to the source material.
[University of Brighton project description](https://research.brighton.ac.uk/en/projects/chartex/);
[project authors' conference description](https://dh-abstracts.library.virginia.edu/works/1626).

**Application here:** this is a closer source match than a modern census linker.
Property succession, transaction parties, associates, and offices deserve
structured representation. They can support identity without establishing
kinship. A property transaction involving two Rosenbergs must not automatically
create a family relationship.

### 2.2 LINKS: reproducible historical family reconstruction

LINKS reconstructs individuals and families from Dutch civil certificates. Its
published architecture distinguishes source data, standardized data, linked and
enriched data, and released data, and emphasizes repeatable processing. The
paper describes both its original database approach and the graph-based
burgerLinker system.
[Mandemakers et al., 2023](https://hlcs.nl/article/view/14685).

**Application here:** keep the same conceptual separation without creating a
second facts database. Source JSON remains authoritative; normalization,
candidate identities, and reconstructed edges can exist in memory. Generated
relationships must be reproducible from a declared evidence policy.

### 2.3 Family-group linkage

Akgün and colleagues studied a strategy that first links births into sibling
groups and then links families across generations. Their evaluation concerned
two nineteenth-century Scottish districts and compared results with existing
demographers' reconstructions. It supports family-level linkage as a practical
research direction, but its reported performance does not establish accuracy for
medieval charters.
[Akgün et al., 2020, author-hosted paper](https://ozgurakgun.github.io/files/fulltext/2020/Linking%20Scottish%20vital%20event%20records%20using%20family%20groups.pdf).

Gellatly separately describes comparing family structures when aggregating
genealogical files, alongside conventional name and birth-date comparisons.
[Gellatly, 2014, Utrecht University research record](https://research-portal.uu.nl/en/publications/reconstructing-historical-populations-from-genealogical-data-an-o/).

**Application here:** evaluate a mention together with its source-stated
relatives. An Eberhard associated with a distinctive spouse and children is more
informative than an isolated Eberhard. Use relationships from source assertions,
never the relationships being replaced in `people.json`.

### 2.4 Collective entity resolution

Bhattacharya and Getoor distinguish independent pairwise matching from joint
resolution of connected references. Their model uses attributes and relational
structure together; their experiments show improvements over the compared
attribute-only and non-collective baselines on the studied datasets.
[Bhattacharya and Getoor, 2007, author-group paper](https://linqs.org/assets/resources/bhattacharya-tkdd07.pdf).

**Application here:** do not treat every name occurrence as an isolated
classification. Compare competing assignments for a connected set of mentions.
Keep explicit cannot-link constraints between distinct anchors. A chain of
plausible pairwise similarities must not merge the Lauda and Dürn identities.

Joint reasoning does not mean counting the same evidence repeatedly. Each
score contribution should identify the source assertions on which it depends.

## 3. A principled alternative to arbitrary matching weights

Fellegi and Sunter's foundational record-linkage model distinguishes a link,
a non-link, and a possible link requiring further consideration. Its decision
framework uses the likelihood of the observed agreement pattern among true
matches versus nonmatches.
[Fellegi and Sunter, 1969](https://www.tandfonline.com/doi/abs/10.1080/01621459.1969.10501049).

A simplified feature-wise score is:

```text
score = sum over features j of log(m_j / u_j)

m_j = P(observed comparison outcome j | same person)
u_j = P(observed comparison outcome j | different people)
```

This is a likelihood-ratio score, not automatically a posterior match
probability. Summing feature contributions assumes conditional independence;
dependencies require further modeling. Winkler discusses both the
Fellegi–Sunter framework and extensions involving dependent comparisons and
Bayesian networks.
[Winkler, 2002, U.S. Census Bureau research report](https://www.census.gov/content/dam/Census/library/working-papers/2002/adrm/rrs2002-05.pdf).

**Proposed adaptation:** estimate comparison frequencies among the actual
candidate namesakes and period, not indiscriminately across the entire dataset.
If the candidate pool already consists of Eberhards von Rosenberg, agreement on
that name contributes little discrimination. Similarly, Boxberg may be common
among the relevant family, even if uncommon in the full place registry.

Titles and places also overlap: `Vogt zu Lauda` and a Lauda place match may come
from one phrase. Treating these as two independent strong signals exaggerates
the evidence.

Until a sufficiently varied reviewed set exists, use explainable scores and
three decisions: accepted assignment, rejected assignment, unresolved. Do not
label a hand-tuned score as a measured percentage probability.

## 4. Source assertions and historical conclusions need separate layers

### 4.1 Factoid prosopography

The Prosopography of Anglo-Saxon England records source assertions as factoids
and acknowledges that identifying the people behind them requires historical
judgment. Its methodology permits unresolved possibilities that separately
represented people were actually identical.
[PASE research methodology](https://pase.ac.uk/about/research-methodology/).

King's College London's Factoid Prosopography Ontology explicitly connects
assertions to source citations, participant references, roles, and dates. It
distinguishes the date an assertion was made from dates associated with its
historical content.
[FPO factoids](https://www.kcl.ac.uk/factoid-prosopography/fpo-factoids);
[FPO sources](https://www.kcl.ac.uk/factoid-prosopography/fpo-sources).

**Application here:** a source-supported assertion and the identity assignment
for its participant are different claims. A reliable parent assertion does not
make an uncertain Eberhard identification reliable. Preserve both confidence
dimensions and every supporting source location.

Distinguish a historical event date, a retrospective attestation, and a later
publication date. The repository's current historical-date rules remain
authoritative; any additional date roles require a documented schema extension.

### 4.2 Genealogical proof and machine scores

The Board for Certification of Genealogists describes five interdependent
elements of the Genealogical Proof Standard: thorough research, adequate
citations, analysis and correlation, conflict resolution, and a reasoned written
conclusion.
[BCG description of the standard](https://www.bcgcertification.org/about).

**Application here:** a numerical score helps rank hypotheses; it does not
replace an explanation of why a particular namesake is identified. The review
view should show decisive evidence, alternatives, contradictions, and remaining
uncertainty. Unresolved is a legitimate result.

### 4.3 Existing genealogical data models

GEDCOM X provides conceptual structures for persons, relationships, source
references, analysis, confidence, and attribution. Its specification warns that
its technical term `Conclusion` does not necessarily mean an accepted conclusion
under genealogical proof standards.
[FamilySearch GEDCOM X conceptual model](https://github.com/FamilySearch/gedcomx/blob/master/specifications/conceptual-model-specification.md?plain=1).

**Application here:** borrow the separation of evidence, reasoning, and
conclusions. There is no need to adopt the complete serialization or replace
the source JSON. These concepts can guide a future generated relationship
schema, which must be documented before use.

## 5. Existing software: what to borrow and what to avoid copying

burgerLinker is an open-source civil-register linking tool. Its documentation
describes lexical name comparison, relatives' names, dates, expert rules,
candidate explanations, RDF input, and closure over identity links. It also
states that candidate discovery emphasizes recall and that rules can be adapted.
Its documented defaults include assumptions about ages, marriage, and births.
[CLARIAH burgerLinker repository and documentation](https://github.com/CLARIAH/burgerLinker).

**Assessment for this project:** inspect its candidate explanations, separation
of matching from filtering, and configurable rules as implementation precedents.
It is not a demonstrated drop-in solution for this repository's mixed medieval
sources and JSON assertions.

Do not copy civil-registration demographic defaults into medieval research as
hard historical truths. In particular:

- An attestation date is not necessarily a birth, marriage, or death event date.
- A parent may be deceased when a child is mentioned.
- A title can be omitted or change over time.
- A place in a property deed need not indicate personal presence.
- Candidate identity links need validation before taking transitive closure.

These are proposed adaptation requirements, not claims that burgerLinker itself
handles this repository's cases.

## 6. Changes and refinements to the original plan

The following are project recommendations drawn from the precedents above,
not algorithms copied verbatim from a single publication.

| Area | Refined recommendation | Reason |
| --- | --- | --- |
| Architecture | Separate mentions, source assertions, identity hypotheses, and generated relationships | Supports provenance and alternative interpretations |
| Candidate retrieval | Start with normalized compatible names, then expand through contextual clues | Retrieves possibilities without treating retrieval as identification |
| Scoring | Use frequency-aware comparisons and later calibrate them | Common names and family locations have limited discriminatory value |
| Decisions | Preserve accepted, rejected, and unresolved states | Avoids forced assignment |
| Family context | Resolve small connected groups jointly | Relatives can distinguish otherwise identical namesakes |
| Constraints | Separate hard logical constraints from soft historical expectations | Missing titles and uncertain ages are not logical contradictions |
| Provenance | Track source/event dependencies | A charter quoted in several books is not several independent witnesses |
| Guesses | Track which conclusions depend on a guess | The facts-only view must remain reproducible |
| Export | Treat the family tree as a view of a relationship graph | Several marriages and repeated ancestry do not fit a simple tree |

The family graph needs particular care: repeated ancestry through separate
branches is permissible; a directed parentage cycle is not. Spouse links do not
mean that every child of either spouse belongs to that couple. Neither a shared
associate nor a shared property creates a kinship edge.

## 7. Titles, death, and geography: limits of the evidence found

The medieval literature supports using titles and contextual information. The
sources reviewed here do not establish a universal rule that a particular office
title uniquely identifies its holder across all dates. Therefore `Vogt zu Lauda`
should identify an anchor through a reviewed project-specific rule with a scope.
The distinction between Lauda and Dürn remains a fixed project constraint.

For death evidence, follow `rules/json-formats.md`: an ordinary mention does not
prove life. Exclusion requires an incompatible assertion of living activity,
not simply a later document date. Research on dated civil events cannot justify
treating all medieval mentions as contemporary actions.

For geography, begin with direct-ID observations. Do not build a person's place
profile from all same-name matches returned by a broad search. Count independent
events, distinguish place roles, and allow mobility. The historical family
reconstitution literature's discussion of selection and registration makes it
especially important to evaluate difficult and mobile cases, not only easy
local matches.

## 8. Evaluation before automatic rebuilding

Create a reviewed set containing both matches and nonmatches, with deliberate
coverage of difficult cases:

- Same name and same rank, but different people.
- Similar title and overlapping places, but distinct anchored IDs.
- One person changing rank or relative age designation.
- A deceased person mentioned retrospectively.
- An apparent match supported only by repeated editions of one source.
- A family-context match whose relatives also have ambiguous identities.
- A case that remains unresolved with all currently available evidence.

Measure identity precision, recall, unresolved coverage, and erroneous cluster
merges. Separately evaluate generated parent, spouse, sibling, and kin edges.
Good pairwise scores alone do not guarantee a correct genealogy.

When evaluating learned parameters, keep editions of the same event together
and hold out connected identity groups where feasible. Otherwise related
evidence can leak between training and evaluation. Compare a name/date baseline
with added titles, places, family context, and joint constraints, then repeat
with and without guesses.

These are proposed evaluation procedures. No published accuracy figure reviewed
here should be presented as an expected result for this dataset.

## 9. Recommended next implementation step

Build an explainable, read-only linkage prototype before changing relationships:

```text
source assertions
    -> participant mentions with provenance
    -> candidate identities
    -> chronology and cannot-link checks
    -> contextual and family-group comparison
    -> accepted / rejected / unresolved hypotheses
    -> generated relationship graph with evidence and uncertainty
```

For each unresolved Eberhard, show the candidate IDs, independent supporting
events, chronological compatibility, title evidence, place-role evidence, and
the reason alternatives remain possible or are excluded.

The research supports the original plan's broad architecture. Its strongest
refinement is to make family context and evidence dependencies explicit, while
using established record-linkage decision states rather than a forced best
match. The medieval-charter precedents and factoid models are the most directly
relevant; civil-register systems provide useful techniques that need adaptation.

## Research scope

Sources above are original research papers, author or university research
records, project descriptions, official specifications, and the software's own
documentation. Coverage is targeted rather than a systematic literature review.
The medieval chapter was available through indexed text; its full PDF could not
be retrieved during this session. The Gellatly comparison is based on the
university research abstract. No linked software was installed or benchmarked,
and no claim is made that it supports this repository without adaptation.
