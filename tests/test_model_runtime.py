from __future__ import annotations

import unittest
from pathlib import Path

from genomic_watermarks.models.huggingface import (
    CARBON_500M_FNS_REVISION,
    CARBON_500M_REVISION,
    CARBON_QWEN3_TOKENIZER_ID,
    CARBON_QWEN3_TOKENIZER_REVISION,
    GENERATOR_V2_1P2B_REVISION,
    POLICIES,
    _load_model_from_spec,
    _load_tokenizer_from_spec,
    carbon_prompt,
    generator_prompt,
)
from genomic_watermarks.models.runtime import choose_device


class ModelRuntimeTest(unittest.TestCase):
    def test_local_device_resolution(self) -> None:
        self.assertEqual(choose_device("auto", mps_available=True, allow_cpu_fallback=True), "mps")
        self.assertEqual(choose_device("mps", mps_available=False, allow_cpu_fallback=True), "cpu")
        with self.assertRaises(RuntimeError):
            choose_device("mps", mps_available=False, allow_cpu_fallback=False)

    def test_model_prompt_contracts(self) -> None:
        self.assertEqual(carbon_prompt("atcgat"), "<dna>ATCGAT")
        self.assertEqual(generator_prompt("atcgat"), "<s>ATCGAT")
        with self.assertRaises(ValueError):
            generator_prompt("ATCGA")

    def test_code_revisions_match_sources_file(self) -> None:
        text = Path("sources.yaml").read_text(encoding="utf-8")
        for revision in (
            CARBON_500M_REVISION,
            CARBON_500M_FNS_REVISION,
            CARBON_QWEN3_TOKENIZER_REVISION,
            GENERATOR_V2_1P2B_REVISION,
        ):
            self.assertIn(revision, text)

    def test_carbon_transitive_tokenizer_revision_is_injected_and_restored(self) -> None:
        class FakeAutoTokenizer:
            calls: list[tuple[str, dict[str, object]]] = []

            @classmethod
            def from_pretrained(cls, model_id: str, **kwargs: object) -> object:
                cls.calls.append((model_id, kwargs))
                if model_id == POLICIES["C_tok"].policy.model_id:
                    cls.from_pretrained(CARBON_QWEN3_TOKENIZER_ID)
                return object()

        original = FakeAutoTokenizer.__dict__["from_pretrained"]
        _load_tokenizer_from_spec(
            FakeAutoTokenizer,
            POLICIES["C_tok"],
            cache_dir="test-cache",
            local_files_only=True,
        )
        self.assertIs(FakeAutoTokenizer.__dict__["from_pretrained"], original)
        _, dependency_kwargs = FakeAutoTokenizer.calls[1]
        self.assertEqual(dependency_kwargs["revision"], CARBON_QWEN3_TOKENIZER_REVISION)
        self.assertEqual(dependency_kwargs["cache_dir"], "test-cache")
        self.assertTrue(dependency_kwargs["local_files_only"])

    def test_remote_model_tokenizer_reload_is_revision_pinned_and_restored(self) -> None:
        class FakeAutoTokenizer:
            calls: list[tuple[str, dict[str, object]]] = []

            @classmethod
            def from_pretrained(cls, model_id: str, **kwargs: object) -> object:
                cls.calls.append((model_id, kwargs))
                return object()

        class FakeAutoModel:
            @classmethod
            def from_pretrained(cls, model_id: str, **kwargs: object) -> object:
                FakeAutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
                return {"model_id": model_id, "kwargs": kwargs}

        original = FakeAutoTokenizer.__dict__["from_pretrained"]
        model = _load_model_from_spec(
            FakeAutoModel,
            FakeAutoTokenizer,
            POLICIES["G_tok"],
            model_kwargs={"revision": GENERATOR_V2_1P2B_REVISION},
            cache_dir="test-cache",
            local_files_only=True,
        )
        self.assertIs(FakeAutoTokenizer.__dict__["from_pretrained"], original)
        self.assertEqual(model["model_id"], POLICIES["G_tok"].policy.model_id)
        _, tokenizer_kwargs = FakeAutoTokenizer.calls[0]
        self.assertEqual(tokenizer_kwargs["revision"], GENERATOR_V2_1P2B_REVISION)
        self.assertEqual(tokenizer_kwargs["cache_dir"], "test-cache")
        self.assertTrue(tokenizer_kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
