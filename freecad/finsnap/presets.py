# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The values new fins start with: the built-in ones, or the user's own, under
the standard profile or one of any number of named profiles.

The values of the task panel can be saved as the standard for new fins, and
the built-in values restored. Each profile holds all of them, and the one
active is the standard. They live in FreeCAD's user parameters, one entry per
FinParams field, so a field added in a later version starts with its built-in
value until it is saved. The standard profile is the group a standard was saved
in before there were profiles, so it stays as it was; it has no name of its own
here, None, and can be neither renamed nor deleted.

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

INPUTS this has to withstand (active_profile()):
  none activated yet                    ->  None, the standard profile
  a name whose profile is gone          ->  None, the standard profile

INPUTS this has to withstand (the name of a profile, add_profile() and rename_profile()):
  "0.4 mm & PETG", umlauts, any script  ->  taken as it is
  spaces round it                       ->  taken without them: FreeCAD drops them
  empty or only spaces                  ->  ProfileError
  a slash                               ->  ProfileError: FreeCAD takes it for a subgroup
  a tab, a line break, other control
    characters                          ->  ProfileError
  longer than PROFILE_NAME_MAX          ->  ProfileError
  a name in use, in any case            ->  ProfileError
  the name shown for the standard
    profile, in any case                ->  ProfileError
  a profile renamed to its own name,
    also in another case                ->  taken

INPUTS this has to withstand (add_profile()):
  invalid parameters                    ->  ParamError, no profile made

INPUTS this has to withstand (activate(), rename_profile() and delete_profile()):
  a name that is no profile             ->  ProfileError, nothing changes
  the active profile renamed            ->  it stays active under the new name
  the active profile deleted            ->  the standard profile is active
  another profile deleted               ->  the active one stays
"""

from dataclasses import fields

import FreeCAD as App

from .i18n import QT_TRANSLATE_NOOP, translate
from .params import FinParams, ParamError

# Where FinSnap keeps its settings in FreeCAD's user parameters.
PREFERENCES = "User parameter:BaseApp/Preferences/Mod/FinSnap"
# Subgroup holding the saved standard values of new fins. Tests point it
# elsewhere, so they never touch the user's own standard.
STANDARD_GROUP = "Standard"
# Subgroup holding a group of values for each named profile, and which is active.
# Tests point it elsewhere too.
PROFILES_GROUP = "Profiles"
ACTIVE_PROFILE = "Active"
# The longest name a profile can have: enough to tell nozzle, layers and material.
PROFILE_NAME_MAX = 64
# A slash in the name of a parameter group starts a subgroup.
GROUP_SEPARATOR = "/"
# The name shown for the standard profile.
STANDARD_PROFILE = QT_TRANSLATE_NOOP("FinSnap", "Standard")


class ProfileError(ValueError):
    """A name that cannot be given to a profile, or names no profile; its text says why."""


def _profiles():
    return App.ParamGet("%s/%s" % (PREFERENCES, PROFILES_GROUP))


def _group():
    """The group of values of the active profile."""
    name = active_profile()
    return App.ParamGet("%s/%s" % (PREFERENCES, STANDARD_GROUP)) if name is None else _profiles().GetGroup(name)


def _accessors(group):
    """For each type of field: the names saved with it, how to read and how to write one."""
    return {bool: (group.GetBools(), group.GetBool, group.SetBool),
            float: (group.GetFloats(), group.GetFloat, group.SetFloat),
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
    """Make `params` the standard for new fins: the values of the active profile."""
    params.validate()
    group = _group()
    group.Clear()
    accessors = _accessors(group)
    built_in = FinParams()
    for field in fields(FinParams):
        write = accessors[type(getattr(built_in, field.name))][2]
        write(field.name, getattr(params, field.name))


def reset():
    """Go back to the built-in values for new fins, in the active profile."""
    _group().Clear()


def profile_names():
    """The names of the named profiles, in the order of the alphabet."""
    return sorted(_profiles().GetGroups(), key=str.casefold)


def active_profile():
    """The name of the active profile; None for the standard profile."""
    name = _profiles().GetString(ACTIVE_PROFILE, "")
    return name if name in _profiles().GetGroups() else None


def _known(name):
    """`name`, the name of a named profile; ProfileError if it is none."""
    if name not in _profiles().GetGroups():
        raise ProfileError(translate("FinSnap", "there is no profile \"%s\"") % name)
    return name


def activate(name):
    """Make the profile `name` the standard for new fins; None for the standard profile."""
    if name is None:
        _profiles().RemString(ACTIVE_PROFILE)
    else:
        _profiles().SetString(ACTIVE_PROFILE, _known(name))


def _free_name(name, renamed=None):
    """`name` as a profile can be called, without spaces round it, the profile
    `renamed` aside; ProfileError saying why it cannot."""
    name = name.strip()
    if not name:
        raise ProfileError(translate("FinSnap", "a profile needs a name"))
    if GROUP_SEPARATOR in name or not name.isprintable():
        raise ProfileError(translate("FinSnap", "the name of a profile cannot hold a slash or a line break"))
    if len(name) > PROFILE_NAME_MAX:
        raise ProfileError(translate("FinSnap", "the name of a profile can have %d characters at most")
                           % PROFILE_NAME_MAX)
    taken = [other.casefold() for other in profile_names() if other != renamed]
    taken += [STANDARD_PROFILE.casefold(), translate("FinSnap", STANDARD_PROFILE).casefold()]
    if name.casefold() in taken:
        raise ProfileError(translate("FinSnap", "there is a profile \"%s\" already") % name)
    return name


def add_profile(name, params):
    """Make a profile `name` of `params` and activate it; returns the name as taken."""
    params.validate()
    name = _free_name(name)
    _profiles().GetGroup(name)
    activate(name)
    save(params)
    return name


def rename_profile(old, new):
    """Call the profile `old` `new`, with what it holds; returns the name as taken."""
    _known(old)
    new = _free_name(new, old)
    if new == old:
        return new
    active = active_profile() == old
    source, target = _accessors(_profiles().GetGroup(old)), _accessors(_profiles().GetGroup(new))
    for kind, (saved, read, _) in source.items():
        write = target[kind][2]
        for field in saved:
            write(field, read(field))
    _profiles().RemGroup(old)
    if active:
        activate(new)
    return new


def delete_profile(name):
    """Remove the profile `name`; where it was active, the standard profile is."""
    _known(name)
    active = active_profile() == name
    _profiles().RemGroup(name)
    if active:
        activate(None)
