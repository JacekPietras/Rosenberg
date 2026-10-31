# Worked identity-weight calculations

These fictional examples illustrate the
[specification](family-tree-algorithm-plan.md). They are not identifications of
historical people or output from the current engine. Every probability below is
uncalibrated.

## Calculation rules

```text
prior = 0.05
initial L = ln(0.05 / 0.95) = -2.944439
P = 1 / (1 + exp(-L))
reliability = source factor × guess factor (if guessed)
pair reliability = min(left reliability, right reliability)
evidence = base × pair reliability × 2^(-gap / halfLife)
age = -max(0, minAge - 60) / 10 × pair reliability; minAge > 80 is impossible
```

Values use the current configuration. Dates in these examples are exact days
(for example 1 May of each year), so a 57-year gap is exactly 57 years; with
year-only dates the engine reads the gap permissively (end of the first year to
start of the second).

Each example starts fresh from the prior. Distinct signals are assumed
independent, caps are not exceeded, and unlisted features contribute `0`.

## 1. Source and guess reliability

Two records name fictional Otto von Beispiel. Both show the same scoped office
(base `8`) and the same property (base `4`) at the same historical date. The
other record is always a document fact.

| Weaker source | Pair reliability | Office | Property | Final L | P |
| --- | --- | --- | --- | --- | --- |
| Document fact | 1 | +8.000 | +4.000 | 9.056 | 99.99% |
| Book fact | 0.5 | +4.000 | +2.000 | 3.056 | 95.50% |
| Document guess | 0.45 | +3.600 | +1.800 | 2.456 | 92.10% |
| Book guess | 0.225 | +1.800 | +0.900 | -0.244 | 43.92% |

The same name adds no extra weight.

## 2. Increasing time distance

Keep the two document-fact signals above, but place the records progressively
farther apart. The office makes him adult at the first record, so
`minAge = gap + 16` at the second. Office half-life is 15 years; property 20.

| Gap (years) | Office | Property | Min age | Age | Final L | P |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | +8.000 | +4.000 | 16 | 0.000 | 9.056 | 99.99% |
| 15 | +4.000 | +2.378 | 31 | 0.000 | 3.434 | 96.87% |
| 57 | +0.574 | +0.555 | 73 | -1.300 | -3.115 | 4.25% |
| 75 | +0.250 | +0.297 | 91 | impossible | blocked | — |

At 75 years the birth interval is empty: born no later than `d - 16` and no
earlier than `d + 75 - 80`. Both are document facts, so the merge is blocked.
With a book or guess involved it would instead receive `-20 × pair reliability`.

## 3. A deceased participant remains matchable

Two records share an independently identified child (base `9`, relation factor
`1.0`), 10 years apart, family half-life 35. One record is a widow's reference
marking her husband deceased. An independent record dates his death to 1330.
A 1357 reference also marks him deceased.

```text
family = 9 × 1.0 × 1 × 2^(-10/35) = 7.383018
compatible deceased markers = 0
compatible death bound = 0
L = -2.944439 + 7.383018 = 4.438579
P = 98.83%
```

If the 1357 reference did **not** mark him deceased, it would be a mention after
death: blocked for document facts.

## 4. Mention after death

Start with compatible contextual evidence totaling `+8`: 99.37%. One source
says he died before 1300; a 1328 fact mentions him without a deceased marker.

| Death source | Contribution | Final L | P |
| --- | --- | --- | --- |
| Document fact | blocked | — | — |
| Book fact (0.5) | `-20 × 0.5 = -10` | -4.944 | 0.71% |
| Book guess (0.225) | `-20 × 0.225 = -4.5` | 0.556 | 63.54% |
| 1328 mention marked deceased | 0 | 5.056 | 99.37% |

## 5. Earlier younger, later elder; comparing generations

A 1300 `parent` fact names an elder parent (`der Ältere`) and a younger child
(`der Jüngere`). A separately established person is mentioned alive in 1357
and called `der Ältere` then. Both early candidates have contextual support
`+6`. All sources are document facts.

| Candidate | Latest birth | Min age 1357 | Context | Age | Age title | Final L | P |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Earlier elder | 1284 | 73 | +6 | -1.300 | +0.111 | 1.867 | 86.61% |
| Earlier younger | 1300 | 57 | +6 | 0 | 0 | 3.056 | 95.50% |

The elder is a parent and `der Ältere` in 1300, so he was born no later than
1284. The younger has no adult constraint. Younger → elder has no opposed-title
penalty. The elder's matching title earns only `3 × 2^(-57/12) = 0.111`.

The younger leads by `1.189` log-odds units, above the margin `1`, so he is the
preferred candidate. If the elder is also marked deceased by 1300, the unmarked
1357 mention blocks him outright.

## 6. Duplicate support and close rivals

Candidate A receives independent evidence `+5` and candidate B `+4.8`: `L =
2.056` (88.65%) and `L = 1.856` (86.48%). Both clear 80%, but the difference
`0.2` is below the margin `1`. Keep the assignment unresolved.

Extracting A's same family assertion twice adds `0`. Reusing an inferred parent
to confirm the child that identified that parent also adds `0`.
