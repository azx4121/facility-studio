# Engineering test policy

State physical units, design conditions, defaults, applicability, source references, platform and tolerances for every engineering change. Identify affected formulas and assumptions, negative and boundary cases, and rollback strategy. Keep Windows and macOS implementations distinct. Never equate repeated execution with physical correctness or a library result with a design standard.

Run existing documented standalone regression scripts in an isolated checkout, plus relevant engineering, reporting, 100-case and GUI checks. Record commands, exit codes, test counts, source platform, host OS and commit. Document failed, skipped and unavailable checks. Independent library comparisons must state assumptions and traceable reference inputs. Source tests, native package tests and real-device acceptance are separate gates. Existing golden fixtures and published artifacts must remain intact.
