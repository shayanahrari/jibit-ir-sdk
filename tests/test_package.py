"""Package metadata tests."""

from jibit import __version__


def test_package_version_is_semantic() -> None:
    """The initial public version follows Semantic Versioning."""
    assert __version__ == "0.1.0"
