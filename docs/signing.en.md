# Security prompts and distribution signing

[繁體中文](signing.md) · [Downloads](../README.en.md#download-and-run)

Updated 2026-10-08. The current Windows EXE is unsigned. The Mac app uses ad-hoc integrity signing without Developer ID or Apple notarization. Native launch tests and SHA256 comparison do not replace publisher certification or guarantee a malware-free file.

## Windows

| Prompt | What to do |
| --- | --- |
| SmartScreen: Windows protected your PC / unknown publisher | Check the official download and SHA256. New files and publishers may lack reputation; follow your personal or organizational policy. |
| Smart App Control or a managed-device policy blocks execution | A bypass may be unavailable. Ask IT to evaluate the app or wait for a signed release; keep security features enabled. |
| Antivirus names a specific threat | Stop and report the detection name, EXE SHA256, OS version and download URL. The maintainer must inspect the actual file rather than assume a false positive. |
| Administrator elevation prompt | Normal application use does not require administrator access. Verify the executable and action, and report the complete dialog. |

Moving the same EXE into a ZIP does not certify its publisher. The public delivery remains a standalone EXE with its runtime and offline help.

For a formally signed release, the maintainer must obtain an eligible, trusted code-signing certificate or signing service, confirming availability for Taiwan and individual developers. Sign the final, tested EXE with a trusted timestamp; verify its Authenticode chain on Windows, retest that signed executable, and publish its new SHA256 in a new release. Do not change the binary after signing.

**A valid signature does not guarantee immediate removal of SmartScreen warnings.** File and publisher reputation still matter; EV certificates no longer automatically bypass SmartScreen. Microsoft Store distribution is Microsoft's documented way to avoid its download-reputation warnings, but Store packaging and acceptance are separate work and have not been completed here.

Reference: [Microsoft's developer guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation). No certificate or paid service was purchased during this update.

## macOS

Formal distribution requires Apple Developer Program membership and a **Developer ID Application** certificate. Sign native code and nested frameworks before the outer App, configure hardened runtime and necessary entitlements, verify and retest the app, then create and sign the DMG. Submit it to Apple notarization, require **Accepted**, staple and validate the ticket, and test Gatekeeper with an actual quarantined download on a native Mac before publishing a new final SHA256.

Notarization addresses developer-verification blocking. A normal first-launch confirmation for an internet download can remain. It is not App Store review, engineering certification, or acceptance on every managed device and OS version.

Apple's standard program fee is **US$99 per membership year**, with local pricing shown during enrollment. The current release pipeline has no configured Developer ID/notarization identity and must not claim an Apple-notarized release.

References: [Developer ID](https://developer.apple.com/developer-id/) · [Notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) · [Membership and fees](https://developer.apple.com/programs/enroll/).

Keep signing private keys, certificate passwords and notarization keys out of this public repository and Releases. Use a controlled signing service or Actions Secrets after enrollment; testers do not need account credentials.
