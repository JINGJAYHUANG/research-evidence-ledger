# Point-in-time discipline

A decision snapshot includes only records knowable by the cutoff.

For sources, both conditions must hold:

```text
published_at <= cutoff
observed_at  <= cutoff
```

For assumptions, assessments, rules, claims, and forecasts, their own recorded
or issued timestamps must be no later than the cutoff. A forecast may be present
while its later outcome is absent.

## Vintages

A lineage may contain several versions. The active vintage is the latest version
that was observed by the cutoff, not the latest version available today.

## Common violations

- using a revised economic series in an earlier decision replay;
- citing a report published before the cutoff but not actually observed until later;
- editing the rationale after the outcome;
- replacing the original option assessment with a later assessment;
- applying a rule that was adopted after the decision.
