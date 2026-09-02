# Threat model

## Protected properties

- point-in-time integrity;
- source-vintage integrity;
- claim/evidence traceability;
- rule immutability;
- approval and external-action boundaries;
- reproducible selection;
- separation of process quality and outcome luck;
- public privacy boundary.

## Threats and controls

| Threat | Control |
|---|---|
| future evidence inserted into a replay | explicit cutoff filtering and hard gate |
| later revision substituted for original vintage | lineage-aware active vintage |
| several pages counted as independent evidence | independence groups |
| weights changed after seeing outcomes | rule digest and prospective-only changes |
| rationale rewritten after results | rationale timestamp hard gate |
| incomplete approval treated as authorization | required-role set comparison |
| external execution falsely claimed | receipt-bound action gate |
| circular assumptions hide model dependence | dependency-cycle detection |
| good luck launders a bad process | process/outcome quadrant |
| CSV formula execution | formula-prefix neutralization |
| HTML injection | escaping and static-resource checks |
| personal or secret data published | synthetic-only contract and public scan |

## Residual risk

The tool cannot prove that source metadata is truthful, that timestamps are
externally trusted, that a human approval is informed, or that an external
system honored the record. A malicious author can fabricate an internally
consistent synthetic ledger.
