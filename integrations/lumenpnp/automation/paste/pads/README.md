# FTP resistor paste geometry (offline)

`extract_ftp_pads.py` extracts the actual FTP board's resistor pads and independently matches their complete rounded-rectangle geometry to the fork's front-paste Gerber. It is a deliberately narrow reader for these source formats, not a general KiCad/Gerber importer. Unexpected paste overrides, footprint/side/shape, aperture macro, units, polarity, missing or duplicate references/flashes, and geometry differences fail closed.

From the canonical repository:

```sh
python3 automation/paste/pads/extract_ftp_pads.py \
  --pcb pnp/pcb/ftp/ftp.kicad_pcb \
  --gerber /home/lumen/paste-automation/test/ftp-F_Paste.gbr \
  --output /absolute/new-private-geometry-plan.json
```

The output path must be new. The CLI verifies both the pinned fork commit and the exact committed Gerber bytes, so a dirty file cannot inherit clean provenance. The report records both input paths, byte counts and SHA-256 hashes; it adds no timestamp, making identical source inputs deterministic. Generated plans remain private and are not part of the source mirror.

The actual sources have 40 resistors (R1–R40), two paste pads each. Every pad is a 0.8 × 0.95 mm rounded rectangle with radius 0.2 mm; the pair's center spacing is 1.65 mm. All 80 centers match the Gerber within 0.000000134 mm. Comparison tolerance is 0.000002 mm solely for source-format rounding, not machine accuracy. The check also compares every relative corner center and radius, so matching centers alone cannot hide a different aperture or rotation.

The design frame uses the KiCad file origin, X right and Y up (`designX = KiCadX`, `designY = -KiCadY`). The footprint angle transforms each local pad center, while the pad's own stored angle determines its absolute rectangle orientation. No translation is needed to compare this Gerber. **This is not an OpenPnP transform or physical board registration.** The output retains source UUIDs and Gerber aperture matches for audit.

Candidate deposits are pad centers only: no machine XY, surface Z, standoff or dose is assigned, and `executionReady` is always false. Fresh physical-board registration, both-head clearance, tip transform/heights, dose/retraction/current verification, and review of which physical pads remain available are explicitly pending. Existing job flags or a partly assembled FTP board do not authorize depositing paste on those pads. Pad geometry cannot determine deposited volume or extrusion settings.

Checks: `python3 -m unittest discover -s automation/tests -p 'test_ftp_pad_geometry.py'`. Actual-source tests require the canonical board and pinned fork; provenance tests use synthetic data and run without them. No machine connection or G-code is produced.
