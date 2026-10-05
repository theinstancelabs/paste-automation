# Paper towel side-to-side wipe

`wipe-towel-side-to-side.py` previews by default. It starts from the exact verified source pose, assumes the operator has already positioned and reviewed the tip at the towel wipe Z, moves X to either side of that point for three cycles, returns to center, then lifts to a required numerically smaller raw Z using the existing reviewed Z-step owner. Defaults are a 0.5 mm halfspan and three cycles; halfspan is capped at 1 mm and cycles at five. Y, Z, A, and B stay fixed throughout the XY wipe.

Supply a verified source report, a fresh image showing the reviewed towel/corridor, review text describing that corridor and starting pose, and the desired clearance Z. The same image binds the full route. Preview does not dispatch. Use `--execute` only after reviewing the preview and confirming the machine is already at the wipe start pose. A 0.5 or 0.1 mm lift requires `--firmware-evidence` accepted by `observe-z-step.py`.

```sh
python3 automation/paste/wipe-towel-side-to-side.py SOURCE_REPORT IMAGE --review 'Reviewed towel corridor and start pose' --clearance-z RAW_Z
python3 automation/paste/wipe-towel-side-to-side.py SOURCE_REPORT IMAGE --review 'Reviewed towel corridor and start pose' --clearance-z RAW_Z --execute
```

The wrapper reuses `run-survey-route.py` for XY and `observe-z-step.py` for lift. Any uncertain route stops before lifting; any lift failure stops without retry or recovery. UUID run records preserve the route and Z evidence links. Completion awaits image review and sets no physical acceptance.

Use `--axis X` or `--axis Y` and `--stroke-mm -4` for one signed, nonzero stroke up to 4 mm without returning through the wiped track. Explicit `--halfspan` or `--cycles` cannot be combined with `--stroke-mm`. The default remains the original X wiggle. These options provide repeatable motion, not a qualified cleaning recipe: observed loose tissue can bunch and transfer fibers, so review contact and the lifted tip before dispensing.
