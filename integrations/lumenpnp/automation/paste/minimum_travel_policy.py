"""Offline policy for pairing paste retraction with short same-component moves.

This module produces review metadata only. It does not emit commands or alter
the paste dose, clearance lift, native validators, or dispatch path.
"""
from __future__ import annotations

import math


DEFAULT_MAXIMUM_XY_TRAVEL_MM = 2.0


def plan_minimum_travel_transitions(pads, maximum_xy_travel_mm=DEFAULT_MAXIMUM_XY_TRAVEL_MM):
    """Annotate adjacent-pad transitions with a matched retract/restore decision.

    Each pad must provide ``reference`` (component reference, e.g. ``R17``),
    ``pad`` and a two-number ``xy_mm`` coordinate. A skip is proposed only
    when adjacent pads belong to the same component and their XY travel is
    strictly below the configured limit. Clearance lift and dose are unchanged.
    """
    limit = float(maximum_xy_travel_mm)
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("maximum_xy_travel_mm must be finite and positive")
    items = list(pads)
    for item in items:
        if not isinstance(item, dict) or not item.get("reference") or not item.get("pad"):
            raise ValueError("each pad needs reference and pad identifiers")
        xy = item.get("xy_mm")
        if not isinstance(xy, (list, tuple)) or len(xy) != 2:
            raise ValueError("each pad needs a two-coordinate xy_mm")
        if any(not math.isfinite(float(v)) for v in xy):
            raise ValueError("pad coordinates must be finite")

    transitions = []
    for current, following in zip(items, items[1:]):
        distance = math.dist(tuple(map(float, current["xy_mm"])), tuple(map(float, following["xy_mm"])))
        same_component = current["reference"] == following["reference"]
        skip = same_component and distance < limit
        transitions.append({
            "from": f'{current["reference"]}.{current["pad"]}',
            "to": f'{following["reference"]}.{following["pad"]}',
            "xyTravelMm": distance,
            "retractBeforeMove": not skip,
            "restoreAfterMove": not skip,
            "matchedRetractRestorePair": True,
            "skipRequiresNoPriorRetract": skip,
            "forwardCompensation": False,
            "preserveClearanceLift": True,
            "reason": "same-component-short-move" if skip else (
                "component-boundary" if not same_component else "travel-at-or-above-limit"),
        })
    return {
        "policy": "minimum-xy-travel-review-only",
        "maximumXYTravelMm": limit,
        "strictlyBelowLimit": True,
        "doseChanged": False,
        "endRunRetractRequired": True,
        "transitions": transitions,
    }
