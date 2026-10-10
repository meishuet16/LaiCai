from types import SimpleNamespace

from examples.member2_standard_synthetic_demo_training import _passes_frozen_support


def _class_rows(prefix: str, count: int, unique_accounts: int):
    return [
        (SimpleNamespace(account_key=("tenant-01", f"{prefix}-{index % unique_accounts}")), None)
        for index in range(count)
    ]


def test_frozen_class_support_accepts_minimum_rows_and_unique_accounts():
    positives = _class_rows("positive", 50, 20)
    negatives = _class_rows("negative", 50, 20)

    assert _passes_frozen_support(positives, negatives)


def test_frozen_class_support_rejects_seven_day_train_and_validation_counts():
    # STANDARD's frozen 7d TRAIN/VALIDATION cohorts have 27/28 positive rows.
    assert not _passes_frozen_support(
        _class_rows("positive", 27, 20), _class_rows("negative", 6_389, 323)
    )
    assert not _passes_frozen_support(
        _class_rows("positive", 28, 20), _class_rows("negative", 5_138, 431)
    )


def test_frozen_class_support_rejects_repeated_rows_without_unique_account_support():
    positives = _class_rows("positive", 50, 19)
    negatives = _class_rows("negative", 50, 20)

    assert not _passes_frozen_support(positives, negatives)
