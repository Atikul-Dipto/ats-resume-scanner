from app.jobs.aggregator import _is_worldwide_remote


def test_worldwide_marker_detected():
    assert _is_worldwide_remote("Worldwide")
    assert _is_worldwide_remote("Remote - Anywhere")
    assert _is_worldwide_remote("Global")


def test_geo_restricted_remote_not_flagged():
    assert not _is_worldwide_remote("Remote - US only")
    assert not _is_worldwide_remote("USA")
    assert not _is_worldwide_remote("Philadelphia, PA metro area")
    assert not _is_worldwide_remote("")
    assert not _is_worldwide_remote(None)
