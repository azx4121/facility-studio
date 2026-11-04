"""Independent exact-checkout verification, using only the Python standard library."""
import argparse
from pathlib import Path

from acceptance_validation import validate_acceptance
from source_provenance import expected_source_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    expected = expected_source_manifest(Path(__file__).resolve().parents[1], 'windows',
                                        expected_commit=args.commit)
    for suite in ('fusion', 'facilities'):
        report = validate_acceptance(args.evidence / (suite + '.json'), expected_commit=args.commit,
                                     expected_manifest=expected, expected_suite=suite)
        print(suite, len(report['checks']), 'checks passed with exact-checkout provenance')


if __name__ == '__main__':
    main()
