from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ingestion.config import Config
from ingestion.textpipe import Chunk
from ingestion.triples import EXTRACTOR_MODEL as NAIVE_MODEL
from ingestion.triples import Triple, extract_triples


@dataclass
class ExtractorHandle:
    model: str
    extract: Callable[[str, Chunk], list[Triple]]


def get_extractor(cfg: Config) -> ExtractorHandle:
    if cfg.extractor == "naive":
        return ExtractorHandle(model=NAIVE_MODEL, extract=extract_triples)
    if cfg.extractor == "llm":
        from ingestion.llm_extractor import LlmExtractor

        inst = LlmExtractor(cfg.llm_url, model_label=cfg.llm_model, timeout=cfg.llm_timeout)
        return ExtractorHandle(model=inst.model, extract=inst.extract)
    raise ValueError(f"unknown extractor: {cfg.extractor!r} (expected 'llm' or 'naive')")
