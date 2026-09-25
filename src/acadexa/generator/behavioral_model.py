"""Synthetic behavioral model (memory.md §6, prd.md §13.1, F-B02).

Produces the hidden per-student traits that drive generated academic
behavior together with course difficulty, school profiles and
controlled noise:

- ``ability``, ``diligence`` and ``engagement`` are drawn per student
  from the Normal distributions configured in
  ``behavior.student_traits`` (means/stds), with
  ``observation_noise_std`` added before clipping to ``[0, 1]`` —
  outcome models consume noisy observations of the latent traits.
- Traits are internal to the generator: they are never written to the
  ``students`` collection (the frozen students schema documents them
  as hidden traits, F-B02).

Outcome models apply the configured influence weights, each relative
to the trait's configured mean (all parameters in configuration,
none hard-coded):

- ``ability_marks_weight`` — marks points per unit of ability above
  the mean (academic records),
- ``diligence_attendance_weight`` and
  ``engagement_attendance_weight`` — weekly attendance probability
  shifts (attendance),
- ``diligence_late_weight`` — relative reduction of the late
  probability (coursework).

Every consumer validates the weight it reads. The decliner population
lives in ``decliners`` (task 4.8); LMS rhythms (5.2) are not applied
here.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from acadexa.generator.foundation import GeneratorError, GeneratorRun
from acadexa.generator.students import generate_students

_TRAIT_KEYS = ("ability", "diligence", "engagement")


def _check(condition: bool, message: str) -> None:
    """Raise GeneratorError with ``message`` when ``condition`` is false."""
    if not condition:
        raise GeneratorError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def generate_behavioral_traits(
    run: GeneratorRun,
    students: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, float]]:
    """Generate hidden behavioral traits for every student (task 4.7).

    Args:
        run: Seeded generator run whose ``configs`` contain the
            validated ``behavior.student_traits`` configuration.
        students: Previously generated student documents. When
            omitted, :func:`generate_students` is called for this run.

    Returns:
        Mapping of ``student_id`` to ``{"ability": …, "diligence":
        …, "engagement": …}`` values clipped to ``[0, 1]``.

    Raises:
        GeneratorError: if required trait configuration is missing or
            out of range.
    """
    configs = run.configs
    _check(
        "generator" in configs and "behavior" in configs.get("generator", {}),
        "configs missing generator behavior configuration",
    )
    behavior = configs["generator"]["behavior"]
    _check(
        "student_traits" in behavior,
        "configs missing generator behavior.student_traits",
    )
    traits_config = behavior["student_traits"]
    for trait in _TRAIT_KEYS:
        _check(
            trait in traits_config,
            f"generator behavior.student_traits missing '{trait}'",
        )
        params = traits_config[trait]
        _check(
            isinstance(params, dict) and "mean" in params and "std" in params,
            f"generator behavior.student_traits.{trait} requires 'mean' and 'std'",
        )
        mean = params["mean"]
        _check(
            _is_number(mean) and 0.0 <= mean <= 1.0,
            f"generator behavior.student_traits.{trait}.mean must be in [0, 1]",
        )
        std = params["std"]
        _check(
            _is_number(std) and 0.0 < std <= 1.0,
            f"generator behavior.student_traits.{trait}.std must be in (0, 1]",
        )
    _check(
        "observation_noise_std" in traits_config,
        "generator behavior.student_traits missing 'observation_noise_std'",
    )
    observation_noise = traits_config["observation_noise_std"]
    _check(
        _is_number(observation_noise) and observation_noise >= 0.0,
        "generator behavior.student_traits.observation_noise_std must be >= 0",
    )

    if students is None:
        students = generate_students(run)

    rng = run.child_rng("behavioral_model")
    size = len(students)
    latent = np.empty((size, len(_TRAIT_KEYS)), dtype=float)
    for column, trait in enumerate(_TRAIT_KEYS):
        params = traits_config[trait]
        latent[:, column] = rng.normal(
            params["mean"], params["std"], size=size
        )
    if observation_noise > 0.0:
        latent += rng.normal(0.0, observation_noise, size=(size, len(_TRAIT_KEYS)))
    np.clip(latent, 0.0, 1.0, out=latent)

    return {
        student["student_id"]: {
            "ability": float(latent[index, 0]),
            "diligence": float(latent[index, 1]),
            "engagement": float(latent[index, 2]),
        }
        for index, student in enumerate(students)
    }
