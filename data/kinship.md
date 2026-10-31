// Meaning of source kinship terms (kin.term), one term group per line:
// forms: allowed positions | excluded positions | specificity (exact, narrow, broad)
// Positions are read from the named relative X: P parent, C child, S sibling, Sp spouse;
// PS = X's parent's sibling, SC = X's sibling's child, PSC = cousin, CSp = X's child's spouse.
// "blood" = any path without a spouse step; "any" = any path; "in-law" = any path with a spouse step.
// Combined terms ("Vetter und Schwager") use the union of allowed and the intersection of excluded positions.
// Historical usage varies by date and region; the positions below are this project's matching limits.

// Latin paternal uncle: specifically the father's brother.
patruus, patruo, patrui: PS | S P C Sp | exact
// Brother's daughter: a niece explicitly related through a brother.
Bruderstochter: SC | S P C Sp | exact
// Son-in-law: a daughter's husband, linking families through marriage.
Eidam, gener: CSp | blood | exact
// Forefather: a grandfather or more remote male ancestor; the generation may be unclear.
Ahnherr: PP PPP | S C Sp | narrow
// Originally a father's brother; medieval usage also includes nephews and male cousins.
Vetter, Vettern, vetter: PS SC PSC | S P C Sp | narrow
// Originally a father's sister; also used for a niece or female cousin.
Base: PS SC PSC | S P C Sp | narrow
// Originally a mother's brother; medieval usage can also denote a nephew or wider male kin.
Oheim, öheim, oheim, avunculus: PS SC | S P C Sp | narrow
// Niece: a sibling's daughter, including a niece through marriage in this model.
Nichte: SC SpSC | S P C Sp | narrow
// Latin nephew or grandson: the word alone does not distinguish the two generations.
nepos, nepotes: SC CC | S P Sp | narrow
// Latin brother's son or cousin: collateral male kin whose exact position needs context.
fratruelis, fratrueles, fratruales: SC PSC | S P C Sp | narrow
// Kin through marriage: brother-/sister-in-law or a related marriage connection; usage can be wider.
Schwager, swager, Schwägerin: SpS SSp SpSSp | blood | narrow
// Latin blood relative: shared ancestry is asserted, without specifying the degree.
consanguineus, consanguineos, consanguinei: blood | Sp in-law | broad
