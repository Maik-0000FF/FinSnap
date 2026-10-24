"""The values new fins start with: the built-in ones, or the user's own.

The values of the task panel can be saved as the standard for new fins, and
the built-in values restored. They live in FreeCAD's user parameters, one
entry per FinParams field, so a field added in a later version starts with its
built-in value until it is saved.

INPUTS this has to withstand (standard()):
  nothing saved                         ->  the built-in FinParams()
  some fields saved                     ->  those, the rest built-in
  a field saved with another type (an
    older version stored it otherwise)  ->  built-in value for that field
  saved values that do not validate
    together (a choice no longer
    offered, a bead too narrow)         ->  all built-in

INPUTS this has to withstand (save()):
  valid parameters                      ->  every field stored, the old ones replaced
  invalid parameters                    ->  ParamError, nothing stored

INPUTS this has to withstand (reset()):
  anything saved                        ->  all of it removed, standard() is built-in
  nothing saved                         ->  nothing changes
"""

from dataclasses import fields

import FreeCAD as App

from .params import FinParams, ParamError

# Where FinSnap keeps its settings in FreeCAD's user parameters.
PREFERENCES = "User parameter:BaseApp/Preferences/Mod/FinSnap"
# Subgroup holding the saved standard values of new fins. Tests point it
# elsewhere, so they never touch the user's own standard.
STANDARD_GROUP = "Standard"


def _group():
    return App.ParamGet("%s/%s" % (PREFERENCES, STANDARD_GROUP))


def _accessors(group):
    """For each type of field: the names saved with it, how to read and how to write one."""
    return {float: (group.GetFloats(), group.GetFloat, group.SetFloat),
            int: (group.GetInts(), group.GetInt, group.SetInt),
            str: (group.GetStrings(), group.GetString, group.SetString)}


def standard():
    """The parameters new fins start with."""
    built_in = FinParams()
    accessors = _accessors(_group())
    values = {}
    for field in fields(FinParams):
        default = getattr(built_in, field.name)
        saved, read, _ = accessors[type(default)]
        values[field.name] = read(field.name) if field.name in saved else default
    params = FinParams(**values)
    try:
        params.validate()
    except ParamError:
        return built_in
    return params


def save(params):
    """Make `params` the standard for new fins."""
    params.validate()
    group = _group()
    group.Clear()
    accessors = _accessors(group)
    for field in fields(FinParams):
        value = getattr(params, field.name)
        accessors[type(getattr(FinParams(), field.name))][2](field.name, value)


def reset():
    """Go back to the built-in values for new fins."""
    _group().Clear()
