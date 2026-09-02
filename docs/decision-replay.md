# Decision replay

For option `o`, scenario `s`, and criterion `c`:

```text
adjusted[o,s,c] = 50 + confidence[o,c] × (raw[o,s,c] − 50)
scenario_score[o,s] = Σ weight[c] × adjusted[o,s,c]
```

Then:

```text
base     = score in the declared base scenario
expected = probability-weighted score
worst    = minimum scenario score
regret   = maximum gap from the best option in each scenario
```

The robust score is:

```text
base_weight × base
+ expected_weight × expected
+ worst_weight × worst
+ regret_weight × (100 − maximum_regret)
```

Selection is restricted to options whose required gates do not fail and whose
minimum distributional score meets the rule floor. Stable tie-breaks ensure
input order does not change the result.
