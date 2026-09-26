import pytest

from dossier.feeds import FeedPolicyError, Greenhouse, adapter


def test_fixture_adapters():
    assert Greenhouse().parse({'jobs': [{'id': 1, 'title': 'X'}]})[0].title == 'X'


def test_prohibited_no_client():
    """A prohibited board is refused, and a refused board never reaches a client."""
    with pytest.raises(FeedPolicyError):
        adapter('linkedin').fetch()
