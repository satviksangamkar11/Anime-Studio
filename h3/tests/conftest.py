import pytest

from h3.tests.synth import build_story


@pytest.fixture
def story(tmp_path):
    return build_story(str(tmp_path))
