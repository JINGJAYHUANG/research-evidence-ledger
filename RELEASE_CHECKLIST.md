# Release checklist

- [ ] versions agree across package, citation, rubric, and release notes;
- [ ] all reference cases pass strict validation;
- [ ] every mutant fails exactly the expected hard gate set;
- [ ] generated artifacts have no drift;
- [ ] source hashes, snapshot fingerprints, rule digests, and audit chains verify;
- [ ] schema parity, documentation links, workflow syntax, and public scan pass;
- [ ] Python 3.11, 3.12, and 3.13 pass;
- [ ] independently built Wheels are byte-identical;
- [ ] release tag points to the tested main commit;
- [ ] release assets include source, Wheel, generated reports, checksums, and provenance.
