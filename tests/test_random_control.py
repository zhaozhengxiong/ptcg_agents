import random

import numpy as np

from core.random_control import rng_state_digest, seed_everything, global_rng


def test_seed_everything_resets_all_rngs() -> None:
    seed_everything(123)
    baseline_python = [random.random() for _ in range(3)]
    baseline_numpy = np.random.random(3)
    baseline_global = global_rng().random(3)

    seed_everything(123)
    assert baseline_python == [random.random() for _ in range(3)]
    np.testing.assert_allclose(baseline_numpy, np.random.random(3))
    np.testing.assert_allclose(baseline_global, global_rng().random(3))


def test_rng_state_digest_changes_after_sampling() -> None:
    seed_everything(9876)
    before = rng_state_digest()
    random.random()
    after = rng_state_digest()
    assert before != after
