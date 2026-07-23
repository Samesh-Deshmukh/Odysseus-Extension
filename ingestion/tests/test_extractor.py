import pytest

from ingestion.config import Config
from ingestion.extractor import ExtractorHandle, get_extractor


def test_naive_selection_returns_naive_handle():
    cfg = Config(extractor="naive")
    handle = get_extractor(cfg)
    assert isinstance(handle, ExtractorHandle)
    assert handle.model == "naive-v1"


def test_llm_selection_returns_llm_handle_with_model_tag():
    cfg = Config(extractor="llm", llm_model="qwen3-14b-instruct-q4_k_m")
    handle = get_extractor(cfg)
    assert handle.model == "llm-v1:qwen3-14b-instruct-q4_k_m"
    assert callable(handle.extract)


def test_unknown_extractor_raises():
    cfg = Config(extractor="banana")
    with pytest.raises(ValueError):
        get_extractor(cfg)
