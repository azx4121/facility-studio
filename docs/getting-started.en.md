# Installation and first run | Facility Studio

[繁體中文](getting-started.md) · [Visual tour](visual-tour.en.md) · [Home](../README.en.md)

## 1. Find the correct package

Open [Releases](https://github.com/azx4121/facility-studio/releases), select the intended version and expand **Assets**. Check its platform, architecture, status and SHA256. Tutorial ZIPs and GitHub's automatic **Source code** archives are not ready-to-run application packages.

- **Windows x64:** select the installer or portable ZIP explicitly listed for that release.
- **Apple Silicon Mac:** the 5.7.3 target is an ARM64 `.app` ZIP, not Intel, Universal or DMG.
- **Prerelease/candidate:** follow that attachment's limitations; do not treat it as full formal acceptance.
- If the version has no matching platform package and SHA256, documentation alone does not establish a download. Keep historical win.10/mac.8 releases separate from newer source.

## 2. Verify SHA256

In your download folder, replace the placeholder with the actual filename and compare all 64 hexadecimal characters with the Release's SHA256. These commands only read the file; they do not install it.

Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\downloaded-package.zip'
```

macOS Terminal:

```sh
shasum -a 256 '/full/path/downloaded-package.zip'
```

Matching names do not establish matching contents. Stop if the hash differs and check the version/source again. A matching SHA256 establishes file identity, not trusted publisher signing or Apple notarization.

## 3. Extract or install completely

**Windows installer:** choose a new empty folder, preserving older applications and projects. **Portable:** extract the entire ZIP into a new folder and run the EXE inside; do not copy only the EXE or run it from inside the ZIP.

**Mac:** extract the entire ZIP and retain all `.app` contents. Follow the attachment's instructions and keep accompanying guidance, evidence and checksums. If security prompts appear, check [signing and security](signing.en.md); do not disable Gatekeeper, antivirus or system protections.

Packaged applications contain their Python runtime. Source development is a separate workflow described in [development](development.md#english).

## 4. Complete one practice run

1. Verify the in-app version and choose Traditional Chinese or English.
2. Open the first [offline practice project](tutorial/README.md#english), then save your own copy.
3. Follow the [six-step workflow](visual-tour.en.md#workflow): enter inputs, recalculate and read engineering states.
4. Save the project before exporting reports. Explicitly reimport changed upstream values into downstream tools.

The formal 5.7.3 entry uses `Facility Studio Data-5.7.3` under your home directory by default. Back up older data before upgrading; do not assume older applications can read newer formats. See [saving and rollback](faq.en.md#saving).

## 5. If launch fails

Report the Release link, full asset filename, SHA256, OS/CPU, application version, reproduction steps and error text in [Issues](https://github.com/azx4121/facility-studio/issues). Remove company/client data, private paths and sensitive information; do not post original projects. For calculation issues, supply public-safe minimal inputs, units, expected formulas and actual results.

**DESIGNED BY ANDY HUANG ©**
