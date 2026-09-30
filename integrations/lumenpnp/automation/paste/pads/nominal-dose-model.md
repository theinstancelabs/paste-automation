# Nominal resistor dose scale

This is an offline scale estimate for initial coupon planning, not a recipe or executable command. The [actual FTP source geometry](README.md) gives rounded-rectangle pad area

`A = 0.8 × 0.95 − (4 − π) × 0.2² = 0.725663706 mm²`.

The [CAD displacement extractor](../extract-cad-parameters.py) gives 0.0584531901µL per motor degree, assuming B units are motor degrees. For this conditional example, use 4.44 controller steps per B unit; substitute the actual queried setting for another machine. Under those assumptions one controller step represents 0.225225225 degrees and 0.013165133µL ideal piston displacement. This is nominal commanded resolution, not measured delivered-paste resolution; pressure compliance, backlash, bubbles and delayed flow can dominate it.

| Illustrative equivalent uniform thickness | Pad volume | Ideal motor angle | Ideal controller steps |
|---|---:|---:|---:|
|0.08mm|0.0580531µL|0.993155°|4.40961|
|0.10mm|0.0725664µL|1.241444°|5.51201|
|0.12mm|0.0870796µL|1.489733°|6.61441|

These thicknesses are comparison examples, not requirements inferred from this board. A dispensed dome does not have a uniform stencil-like thickness. The small number of nominal steps makes rounding and absolute cumulative B targets relevant: a future dosing adapter must account for actual controller step counts, commanded vs observed state, direction, priming and gross stroke. Rounding an ideal volume does not establish a good joint.

Reproduce the arithmetic without connecting to hardware:

```sh
python3 - <<'PY'
import math
area = .8 * .95 - (4 - math.pi) * .2**2
ul_per_degree = math.pi * (9.5 / 2)**2 * .5 * (19 / 32) / 360
for equivalent_thickness in (.08, .10, .12):
    volume = area * equivalent_thickness
    angle = volume / ul_per_degree
    print(equivalent_thickness, volume, angle, angle * 4.44)
PY
```

## Material reference

Henkel's March 2019 GC10 technical sheet describes T4 particles as 20–38 µm and SAC305 as Sn96.5/Ag3.0/Cu0.5. It gives T4 viscosity measured under specified rheometer conditions and documents stencil printing; it does not supply a 22-gauge syringe dispensing pressure, motor current or dose. Use coupon observations to establish those. Its stated storage life applies to original-container storage and is not a guarantee for paste already loaded into this syringe. [Henkel GC10 technical data sheet, distributed by Mouser](https://www.mouser.com/datasheet/2/773/GC_10-EN-1761007.pdf).

A 22-gauge, 6.35 mm metal needle length does not by itself verify the exact bore or hub dead volume. Do not compute a guaranteed priming dose from gauge alone. Priming is established by observed consistent flow at the tip over the identified waste target; no amount is automatically dispensed by this model.
