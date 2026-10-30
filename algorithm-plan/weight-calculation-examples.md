# Worked identity-weight calculations

These fictional examples illustrate the
[specification](family-tree-algorithm-plan.md). They are not identifications of
historical people or output from the current engine. Source facts and matching
parameters are unchanged. Every probability below is uncalibrated.

## Calculation rules

```text
prior = 0.05
initial L = ln(0.05 / 0.95) = -2.944439
P = 1 / (1 + exp(-L))
reliability = source factor × guess factor (if guessed)
pair reliability = min(left reliability, right reliability)
evidence = base × pair reliability × 2^(-gap / halfLife)
time = -S/35 - max(0, S-60)/20
```

The source factors, guess factor `0.45`, title/place bases and half-lives, prior,
threshold `0.85`, death penalty `20`, and rival margin `1` below use the current
configuration. Complete active-span timing is **proposed behavior**, replacing
the current nearest-pair term. The hypothetical generation preference `1` below
is for demonstration only; it has not been approved as a production parameter.

Each example starts fresh from the prior. Distinct signals are assumed
independent for the illustration, caps are not exceeded, and unlisted features
(including rarity) contribute `0`. Calculations use unrounded values internally.
No earlier probability is reused as new evidence. Before any automatic merge,
check chronology, distinct identities, cluster consistency, and rival margin.

## 1. Source and guess reliability

Two records name fictional Otto von Beispiel. Independent observations support
both the same scoped office (base `8`) and the same property (base `4`) at the
same historical date. No activity-span penalty applies. Vary the weaker source;
the other record is always a document fact with reliability `1`.

| Weaker source | Pair reliability | Office | Property | Final L | P |
| --- | --- | --- | --- | --- | --- |
| Document fact | 1 | +8.000 | +4.000 | 9.056 | 99.99% |
| Book fact | 0.5 | +4.000 | +2.000 | 3.056 | 95.50% |
| Document guess | 0.45 | +3.600 | +1.800 | 2.456 | 92.10% |
| Book guess | 0.225 | +1.800 | +0.900 | -0.244 | 43.92% |

For the book guess: `0.5 × 0.45 = 0.225`, so the total evidence is
`(8 + 4) × 0.225 = 2.7`. We scale evidence, not the final percentage.
The same name adds no extra weight. Crossing 85% still requires a sufficient
margin over rivals and no cluster conflict.

## 2. Increasing time distance

Keep the two document-fact signals above, but place the two verified active
events progressively farther apart. With only these events, `S = gap`.
Office half-life is 15 years; property half-life is 20 years.

| Gap / active span (years) | Office | Property | Time | Final L | P |
| --- | --- | --- | --- | --- | --- |
| 0 | +8.000 | +4.000 | 0.000 | 9.056 | 99.99% |
| 15 | +4.000 | +2.378 | -0.429 | 3.005 | 95.28% |
| 57 | +0.574 | +0.555 | -1.629 | -3.444 | 3.10% |
| 75 | +0.250 | +0.297 | -2.893 | -5.290 | 0.50% |

For 57 years, the time contribution is `-57/35 = -1.629`; the extra span term
starts only above 60 years. Office/property support also decays independently.
Adding intermediate active records must not turn the 57-year cluster penalty
into a short-gap penalty. New independent evidence can change the other terms,
but simply inserting a bridge does not reset the span.

## 3. A deceased participant remains matchable

Two records share an independently identified child (family base `9`) with
full document reliability and historical family attestations 10 years apart.
For this example family support has a 35-year half-life. One record is a widow's
reference marking her husband deceased; it supplies no living activity. An
independent record dates his death to 1330. A 1357 deceased reference is compatible.

```
family = 9 × 1 × 2^(-10/35) = 7.383018
compatible deceased marker = 0
compatible death upper bound = 0
time = 0 (no pair of dated active events in this example)
L = -2.944439 + 7.383018 = 4.438579
P = 98.83%
```

Neither the deceased marker nor the absence of that marker in another reference
causes a death penalty. A second reference saying “already deceased by 1357” is
also compatible with “already deceased by 1300”; neither implies life in 1357.
The marker does not add a bonus either. The dated family evidence supplies the
positive support; the later reference does not extend the activity span.

## 4. Actual conflict versus uncertain death

Start with independent, otherwise compatible contextual evidence totaling `+8`
after all reliability and decay factors. Its raw estimate is 99.37%.

- **Factual impossibility:** one document establishes death before 1300 and an
  independently identified event requires personal sealing in 1328. Mark the
  proposed merge **ineligible: conflicting chronology**. Do not display a
  computed 0% merely because death appears. The contextual estimate cannot
  authorize this merge.
- **Guessed conflict:** the death bound is instead a guess in a book, with
  reliability `0.5 × 0.45 = 0.225`. A fully incompatible chronology contributes
  `-20 × 0.225 = -4.5`. The total becomes `L = -2.944439 + 8 - 4.5 = 0.555561`,
  giving 63.54%. This falls below 85%; it is not a hard exclusion.
- **Compatible deceased reference:** the 1328 record merely calls the person
  deceased. Death contribution is `0`; the baseline contextual estimate stays
  99.37%. No later living activity has been established.

An uncertain date overlap must not automatically receive the full `-4.5`.
Report the unresolved interval and apply only a justified conflict contribution.

## 5. Earlier younger, later elder; comparing generations

A fictional 1300 source distinguishes an elder parent from a younger child.
A separately established person acts in 1357 and is called elder then. Assume
both early candidates have the same independent contextual support `+6`, after
its own decay/reliability adjustments. Assume all relevant sources are document
facts. The full activity span for each proposed identity is 57 years.

For this illustration only, use `generationPreferenceWeight = 1` for the younger
candidate, with reliability and dependency confidence both `1`. Do not award an
additional family bonus for the same generational distinction.

| Candidate | Context | Time | Age-title contribution | Generation | Final L | P |
| --- | --- | --- | --- | --- | --- | --- |
| Earlier elder | +6 | -1.629 | +0.111 | +0 | 1.538 | 82.32% |
| Earlier younger | +6 | -1.629 | 0 | +1 | 2.427 | 91.89% |

The younger candidate ranks higher. Younger → elder carries **no opposed-title
penalty**. The elder's matching designation earns only
`3 × 2^(-57/12) = 0.111` with the current age-title half-life of 12 years.
If new evidence changes context or title contributions, recalculate both
candidates rather than forcing the younger to win.

Here the younger clears 85%, but leads by only `1 - 0.111 = 0.889` log-odds
units, below the required margin of `1`. Keep the comparison unresolved. If the
elder is additionally established as deceased by 1300, verified later personal
activity makes that elder merge ineligible. A mere 1357 mention does not.

## 6. Duplicate support and close rivals

Suppose candidate A receives independent evidence `+5` and candidate B `+4.8`.
Their final estimates are `L = 2.056`, 88.65% and `L = 1.856`, 86.48% respectively. Both clear 85%,
but their log-odds difference is only `0.2`, below the required margin `1`.
Keep the assignment unresolved. These pairwise probabilities need not sum to 1.

Extracting A's same family assertion twice adds `0`, not another `+5`. Reusing
an inferred parent to confirm the child that originally identified that parent
also adds `0`. Duplicating records or iterating the matcher therefore cannot
turn this unresolved comparison into a confident assignment.
