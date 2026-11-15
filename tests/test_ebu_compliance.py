"""Conformité aux cas d'essai EBU Tech 3341 / 3342, tolérances de la norme."""

import numpy as np
import pytest

from mixlab.ebu_cases import all_cases
from mixlab.measures.loudness import measure_loudness
from mixlab.measures.truepeak import true_peak_dbtp

CASES = all_cases()


def evaluate(case) -> list[float]:
    values = []
    for sig in case.signals:
        if case.measure == "true_peak":
            values.append(true_peak_dbtp(sig))
            continue
        m = measure_loudness(sig, case.fs)
        if case.measure == "short_term_flat":
            values += list(m.short_term)                 # chaque valeur couvre déjà 3 s pleines
        elif case.measure == "momentary_flat":
            values += list(m.momentary[6:])               # fenêtres finissant à 1 s ou plus
        elif case.measure == "lra":
            values.append(m.lra)
        else:
            values.append(getattr(m, case.measure))
    return values


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_ebu_case(case):
    values = evaluate(case)
    assert values
    bad = [round(v, 3) for v in values if not case.accepts(v)]
    assert not bad, f"{case.id} ({case.description}) attendu {case.expected} : {bad}"


def test_case_20_signal_is_built_as_specified():
    """Garde-fou sur la construction du cas 20 : crête des échantillons sous la crête réelle."""
    case = next(c for c in CASES if c.id == "3341-20")
    sig = case.signals[0]
    assert np.max(np.abs(sig)) < 1.0
    assert np.max(np.abs(sig)) > 0.5
