import argparse

import pytest

from collection_naming import validate_collection_name


def test_versioned_collection_name_validation():
    assert (
        validate_collection_name("nmk_chatbot_collection_v20260730_bge_m3_1024")
        == "nmk_chatbot_collection_v20260730_bge_m3_1024"
    )


@pytest.mark.parametrize("value", ["x", "bad name", "/root/collection"])
def test_invalid_collection_name_is_rejected(value):
    with pytest.raises(argparse.ArgumentTypeError):
        validate_collection_name(value)
