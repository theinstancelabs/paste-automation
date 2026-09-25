# Paste Automation

MPL-2.0 fork of opulo-inc/paste-utility, upstream commit 56c091d058915a91b1b1ed3fb917af7484d781b4.

- Read docs/COMMISSIONING.md and docs/HARDWARE_FIRMWARE.md before motion-related changes.
- Keep planning pure and offline; reject invalid jobs before serial writes.
- M400 checkpoints used by the runner must occur only at safe clearance.
- Preserve single machine ownership. No automatic replay after uncertain dispense completion.
- Never promote example measurements to calibrated machine facts.
- npm test and npm run build are required checks for code changes.
- Preserve license notices and keep upstream branding out of derivative UI.
