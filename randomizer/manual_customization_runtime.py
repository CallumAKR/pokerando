#!/usr/bin/env python3
"""In-process source-species filter used by manual customisation.

Legacy component scripts are executed with ``runpy`` in the GUI process, so
this small module can carry one component's source filter without changing the
scripts' command-line interfaces.  Direct script execution keeps the default
"all species enabled" behaviour.
"""

_customized_species = frozenset()
_explicitly_enabled_species = frozenset()
_global_enabled = True


def configure_component_filter(
    customized_species=(),
    explicitly_enabled_species=(),
    global_enabled=True,
):
    global _customized_species
    global _explicitly_enabled_species
    global _global_enabled

    _customized_species = frozenset(customized_species)
    _explicitly_enabled_species = frozenset(explicitly_enabled_species)
    _global_enabled = bool(global_enabled)


def reset_component_filter():
    configure_component_filter()


def species_is_enabled(species):
    """Return whether the current component may modify this source species."""
    if species in _explicitly_enabled_species:
        return True

    return (
        _global_enabled
        and species not in _customized_species
    )

