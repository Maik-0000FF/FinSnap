"""Parameters of one fin set, with validation.

INPUTS this has to withstand (validate()):
  all defaults                          ->  valid
  any length <= 0 where a size is meant ->  ParamError naming the field
  gap <= 0                              ->  ParamError: fin and part would fuse
  bead_width < nozzle_diameter / 2      ->  ParamError: not a printable bead
  layer_height > nozzle_diameter        ->  ParamError: not printable
  tine_layers or tine_width_beads < 1   ->  ParamError
  foot_width_ratio <= 0                 ->  ParamError
  tine_count < 0                        ->  ParamError; 0 means automatic
  fin_thickness, fin_height, tine_first,
    foot_half_width, counter_tine_count
    < 0                                 ->  ParamError; 0 means automatic
  foot_overhang < 0                     ->  ParamError; 0 ends the foot at the fin
  fin_count < 1 with "distributed"      ->  ParamError
  unknown connection / placement / foot ->  ParamError listing the choices
  tine wider than a manual fin_thickness ->  ParamError: tine would stick out
  NaN or infinity in any number         ->  ParamError naming the field
"""

import math
from dataclasses import dataclass, fields

from . import defaults as d


class ParamError(ValueError):
    """The parameters cannot produce a printable fin."""


@dataclass
class FinParams:
    # Slicer settings
    nozzle_diameter: float = d.NOZZLE_DIAMETER
    bead_width: float = d.BEAD_WIDTH
    layer_height: float = d.LAYER_HEIGHT
    first_layer_height: float = d.FIRST_LAYER_HEIGHT
    # Connection
    connection: str = d.CONNECTION
    gap: float = d.GAP
    # Tines
    tine_spacing: float = d.TINE_SPACING
    tine_first: float = d.TINE_FIRST_AUTO
    tine_layers: int = d.TINE_LAYERS
    tine_width_beads: int = d.TINE_WIDTH_BEADS
    tine_count: int = d.TINE_COUNT_AUTO
    # Fin body
    fin_plateau: float = d.FIN_PLATEAU
    fin_thickness: float = d.FIN_THICKNESS_AUTO
    fin_height: float = d.FIN_HEIGHT_AUTO
    # Placement
    placement: str = d.PLACEMENT
    fin_count: int = d.FIN_COUNT
    end_inset: float = d.END_INSET
    face_length_per_fin: float = d.FACE_LENGTH_PER_FIN
    # Foot
    foot_shape: str = d.FOOT_SHAPE
    foot_thickness: float = d.FOOT_THICKNESS
    foot_overhang: float = d.FOOT_OVERHANG
    foot_half_width: float = d.FOOT_HALF_WIDTH_AUTO
    foot_width_ratio: float = d.FOOT_WIDTH_RATIO
    # Counter fin
    counter_tine_count: int = d.COUNTER_TINE_COUNT_AUTO

    def validate(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, float) and not math.isfinite(value):
                raise ParamError("%s is not a finite number" % f.name)

        positive = ("nozzle_diameter", "bead_width", "layer_height", "first_layer_height",
                    "gap", "tine_spacing", "fin_plateau", "end_inset",
                    "face_length_per_fin", "foot_thickness", "foot_width_ratio")
        for name in positive:
            if not getattr(self, name) > 0:
                raise ParamError("%s must be greater than 0" % name)

        automatic = ("fin_thickness", "fin_height", "foot_half_width", "tine_count", "tine_first",
                     "counter_tine_count")
        for name in automatic:
            if getattr(self, name) < 0:
                raise ParamError("%s must be 0 (automatic) or greater" % name)

        if self.foot_overhang < 0:
            raise ParamError("foot_overhang must be 0 or greater")
        if self.bead_width < self.nozzle_diameter / 2:
            raise ParamError("bead_width is less than half the nozzle diameter")
        if self.layer_height > self.nozzle_diameter:
            raise ParamError("layer_height is greater than the nozzle diameter")
        if self.tine_layers < 1:
            raise ParamError("tine_layers must be at least 1")
        if self.tine_width_beads < 1:
            raise ParamError("tine_width_beads must be at least 1")

        choices = (("connection", d.CONNECTIONS), ("placement", d.PLACEMENTS),
                   ("foot_shape", d.FOOT_SHAPES))
        for name, allowed in choices:
            if getattr(self, name) not in allowed:
                raise ParamError("%s must be one of %s" % (name, ", ".join(allowed)))

        if self.placement == d.PLACEMENT_DISTRIBUTED and self.fin_count < 1:
            raise ParamError("fin_count must be at least 1")
        if self.fin_thickness > 0 and self.tine_width > self.fin_thickness:
            raise ParamError("tines (%.2f mm) are wider than the fin (%.2f mm)"
                             % (self.tine_width, self.fin_thickness))

    # Derived sizes, so no caller repeats the arithmetic.
    @property
    def tine_width(self):
        return self.tine_width_beads * self.bead_width

    @property
    def tine_height(self):
        return self.tine_layers * self.layer_height

    @property
    def foot_height(self):
        """Height of the foot on the layer grid, 0 without a foot."""
        return 0.0 if self.foot_shape == d.FOOT_NONE else self.snap_to_layer(self.foot_thickness)

    @property
    def first_tine(self):
        """Bottom of the lowest tine above the bed: as given, or on the top of the foot."""
        if self.tine_first > 0:
            return self.tine_first
        return self.foot_height if self.foot_height > 0 else self.first_layer_height

    def snap_to_layer(self, z):
        """The nearest layer boundary at or above the first layer, z above the bed."""
        if z <= self.first_layer_height:
            return self.first_layer_height
        steps = round((z - self.first_layer_height) / self.layer_height)
        return round(self.first_layer_height + steps * self.layer_height, d.LENGTH_DECIMALS)
