# Signing and security | Facility Studio 5.7.3

[繁體中文](signing.md) · [Downloads/status](../README.en.md#download-and-run)

Native acceptance, Windows trusted Authenticode publisher signing and Mac Developer ID/Apple notarization status must be established by evidence for the exact artifact in matching commit CI records and Release attachments; missing evidence is not verification. Mac ad-hoc signing validates integrity only. A formal release name, SHA256 match or native test pass does not certify publisher identity or absence of malware.

1. Obtain packages only from the linked repository Releases. Match platform, version, size and the SHA256 published for that exact artifact. Use a platform download only when its matching Release provides the package and SHA256; never invent a hash.
2. Extract all portable/ARM64 ZIP contents. ZIP is packaging, not a security bypass. This release does not provide a Mac DMG or Intel/Universal package.
3. Read the exact warning. For enterprise policy or Smart App Control blocks, ask IT to assess it; do not disable protection. For named malware detections, damaged-app warnings or hash mismatch, stop and report the full warning and file identity.
4. Do not disable antivirus, Gatekeeper or quarantine protection, and do not use blanket bypass commands. Normal application use should not require elevation; verify any unexpected privilege prompt.

## Future trusted signing

Windows requires authorized code-signing credentials, timestamping and native verification of the final signed files. Mac requires authorized Developer ID signing, appropriate entitlements and successful notarization before claiming notarized distribution. Signing changes bytes: rebuild the artifact hashes and rerun acceptance after signing. Credentials and private keys must never be committed or attached to releases.

Provide signature/notarization results with the matching Release using the [formal acceptance evidence schema](verification/5.7.3-release-acceptance.md), without rewriting frozen source documentation. Historical signatures and test reports do not transfer to the new package.

[Microsoft signing/reputation guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) · [Apple Developer ID](https://developer.apple.com/developer-id/)
