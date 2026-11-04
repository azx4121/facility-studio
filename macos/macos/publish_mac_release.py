"""Retired 5.6 publisher. It cannot upload, alter or publish release assets."""

def main():
    raise SystemExit(
        "The historical 5.6 publisher is retired. No release was changed. "
        "Use the verified 5.7.3 artifacts and current release gate."
    )


if __name__ == "__main__":
    main()
