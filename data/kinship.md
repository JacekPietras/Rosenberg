// Meaning of source kinship terms (kin.term), one term group per line:
// forms: allowed positions | excluded positions | specificity (exact, narrow, broad)
// Positions are read from the named relative X: P parent, C child, S sibling, Sp spouse;
// PS = X's parent's sibling, SC = X's sibling's child, PSC = cousin, CSp = X's child's spouse.
// "blood" = any path without a spouse step; "any" = any path; "in-law" = any path with a spouse step.
// Combined terms ("Vetter und Schwager") use the union of allowed and the intersection of excluded positions.
patruus, patruo, patrui: PS | S P C Sp | exact
Bruderstochter: SC | S P C Sp | exact
Eidam, gener: CSp | blood | exact
Ahnherr: PP PPP | S C Sp | narrow
Vetter, Vettern, vetter: PS SC PSC | S P C Sp | narrow
Base: PS SC PSC | S P C Sp | narrow
Oheim, öheim, oheim, avunculus: PS SC | S P C Sp | narrow
Nichte: SC SpSC | S P C Sp | narrow
nepos, nepotes: SC CC | S P Sp | narrow
fratruelis, fratrueles, fratruales: SC PSC | S P C Sp | narrow
Schwager, swager, Schwägerin: SpS SSp SpSSp | blood | narrow
consanguineus, consanguineos, consanguinei: blood | Sp in-law | broad
