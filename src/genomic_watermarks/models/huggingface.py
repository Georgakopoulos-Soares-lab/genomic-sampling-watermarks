"""Revision-pinned Hugging Face adapters for Carbon and GENERator-v2."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from genomic_watermarks.dna import normalize_dna
from genomic_watermarks.models.base import DistributionState, ModelPolicy
from genomic_watermarks.models.policy_math import apply_generation_policy, canonical_softmax
from genomic_watermarks.models.runtime import resolve_torch_runtime
from genomic_watermarks.models.vocabulary import CanonicalVocabulary, extract_canonical_vocabulary

CARBON_500M_REVISION = "9796b752108258c1d365089f842e62e6c0547704"
CARBON_500M_FNS_REVISION = "974bc8a54e95d72af5c909416f1b0473e11b7bf4"
CARBON_QWEN3_TOKENIZER_REVISION = "906bfd4b4dc7f14ee4320094d8b41684abff8539"
GENERATOR_V2_1P2B_REVISION = "c41b0018da9ee13b9e96ee54647de8da381ccd72"
CARBON_QWEN3_TOKENIZER_ID = "Qwen/Qwen3-4B-Base"

_AUTO_TOKENIZER_PATCH_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class DependencyPin:
    model_id: str
    revision: str


@dataclass(frozen=True, slots=True)
class PolicySpec:
    policy: ModelPolicy
    prompt_builder: Callable[[str], str]
    transitive_tokenizer_pin: DependencyPin | None = None


def carbon_prompt(dna_context: str) -> str:
    """Format an open Carbon DNA region for continuation."""

    return f"<dna>{normalize_dna(dna_context)}"


def generator_prompt(dna_context: str) -> str:
    """Format a GENERator continuation prompt without silently changing phase."""

    normalized = normalize_dna(dna_context)
    if len(normalized) % 6:
        raise ValueError("GENERATOR context length must be a multiple of 6 bases")
    return f"<s>{normalized}"


POLICIES: dict[str, PolicySpec] = {
    "C_tok": PolicySpec(
        policy=ModelPolicy(
            policy_id="C_tok",
            model_id="HuggingFaceBio/Carbon-500M",
            revision=CARBON_500M_REVISION,
            tokenizer_revision=CARBON_500M_REVISION,
        ),
        prompt_builder=carbon_prompt,
        transitive_tokenizer_pin=DependencyPin(
            CARBON_QWEN3_TOKENIZER_ID,
            CARBON_QWEN3_TOKENIZER_REVISION,
        ),
    ),
    "C_bp": PolicySpec(
        policy=ModelPolicy(
            policy_id="C_bp",
            model_id="HuggingFaceBio/Carbon-500M",
            revision=CARBON_500M_FNS_REVISION,
            tokenizer_revision=CARBON_500M_FNS_REVISION,
        ),
        prompt_builder=carbon_prompt,
        transitive_tokenizer_pin=DependencyPin(
            CARBON_QWEN3_TOKENIZER_ID,
            CARBON_QWEN3_TOKENIZER_REVISION,
        ),
    ),
    "G_tok": PolicySpec(
        policy=ModelPolicy(
            policy_id="G_tok",
            model_id="GenerTeam/GENERator-v2-eukaryote-1.2b-base",
            revision=GENERATOR_V2_1P2B_REVISION,
            tokenizer_revision=GENERATOR_V2_1P2B_REVISION,
        ),
        prompt_builder=generator_prompt,
    ),
    "G_bp": PolicySpec(
        policy=ModelPolicy(
            policy_id="G_bp",
            model_id="GenerTeam/GENERator-v2-eukaryote-1.2b-base",
            revision=GENERATOR_V2_1P2B_REVISION,
            tokenizer_revision=GENERATOR_V2_1P2B_REVISION,
        ),
        prompt_builder=generator_prompt,
    ),
}


def _load_tokenizer_from_spec(
    auto_tokenizer: Any,
    spec: PolicySpec,
    *,
    cache_dir: str | None,
    local_files_only: bool,
) -> Any:
    shared = {
        "revision": spec.policy.tokenizer_revision,
        "trust_remote_code": True,
        "cache_dir": cache_dir,
        "local_files_only": local_files_only,
    }
    dependency = spec.transitive_tokenizer_pin
    if dependency is None:
        return auto_tokenizer.from_pretrained(spec.policy.model_id, **shared)

    # Carbon's remote tokenizer hard-codes AutoTokenizer.from_pretrained(Qwen ID)
    # without forwarding a revision or cache settings. Scope the replacement to
    # construction and restore the class descriptor immediately afterward.
    with _AUTO_TOKENIZER_PATCH_LOCK:
        original_descriptor = inspect.getattr_static(auto_tokenizer, "from_pretrained")
        original_loader = auto_tokenizer.from_pretrained

        def pinned_loader(
            cls: Any,
            model_id: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if str(model_id) == dependency.model_id:
                requested = kwargs.get("revision")
                if requested not in {None, dependency.revision}:
                    raise RuntimeError(
                        f"conflicting revision for transitive tokenizer {dependency.model_id}"
                    )
                kwargs["revision"] = dependency.revision
                kwargs.setdefault("cache_dir", cache_dir)
                kwargs.setdefault("local_files_only", local_files_only)
            return original_loader(model_id, *args, **kwargs)

        auto_tokenizer.from_pretrained = classmethod(pinned_loader)
        try:
            return original_loader(spec.policy.model_id, **shared)
        finally:
            auto_tokenizer.from_pretrained = original_descriptor


def load_tokenizer(
    policy_id: str,
    *,
    cache_dir: str | None = None,
    local_files_only: bool = False,
) -> Any:
    """Load a policy tokenizer with direct and transitive revisions enforced."""

    if policy_id not in POLICIES:
        raise ValueError(f"unknown model policy: {policy_id}")
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error
    return _load_tokenizer_from_spec(
        AutoTokenizer,
        POLICIES[policy_id],
        cache_dir=cache_dir,
        local_files_only=local_files_only,
    )


def _load_model_from_spec(
    auto_model: Any,
    auto_tokenizer: Any,
    spec: PolicySpec,
    *,
    model_kwargs: dict[str, Any],
    cache_dir: str | None,
    local_files_only: bool,
) -> Any:
    """Load a model while pinning any tokenizer its remote code loads internally."""

    with _AUTO_TOKENIZER_PATCH_LOCK:
        original_descriptor = inspect.getattr_static(auto_tokenizer, "from_pretrained")
        original_loader = auto_tokenizer.from_pretrained

        def pinned_loader(
            cls: Any,
            model_id: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if str(model_id) == spec.policy.model_id:
                requested = kwargs.get("revision")
                if requested not in {None, spec.policy.tokenizer_revision}:
                    raise RuntimeError(
                        f"conflicting tokenizer revision for model {spec.policy.model_id}"
                    )
                kwargs["revision"] = spec.policy.tokenizer_revision
                kwargs["cache_dir"] = cache_dir
                kwargs["local_files_only"] = local_files_only
            return original_loader(model_id, *args, **kwargs)

        auto_tokenizer.from_pretrained = classmethod(pinned_loader)
        try:
            return auto_model.from_pretrained(spec.policy.model_id, **model_kwargs)
        finally:
            auto_tokenizer.from_pretrained = original_descriptor


class HuggingFaceDNAAdapter:
    """Expose a declared canonical next-token distribution from a causal LM."""

    def __init__(
        self,
        policy_id: str,
        *,
        tokenizer: Any,
        model: Any,
        device: str,
        dtype_name: str,
    ) -> None:
        if policy_id not in POLICIES:
            raise ValueError(f"unknown model policy: {policy_id}")
        self._spec = POLICIES[policy_id]
        self._tokenizer = tokenizer
        self._model = model
        self._device = device
        self._dtype_name = dtype_name
        self._vocabulary = extract_canonical_vocabulary(tokenizer)

    @property
    def policy(self) -> ModelPolicy:
        return self._spec.policy

    @property
    def canonical_tokens(self) -> tuple[str, ...]:
        return self._vocabulary.tokens

    @property
    def canonical_vocabulary(self) -> CanonicalVocabulary:
        return self._vocabulary

    def next_distribution(self, dna_context: str) -> DistributionState:
        try:
            import torch
        except ImportError as error:
            raise RuntimeError(
                "model-backed work requires the optional 'models' dependencies"
            ) from error

        prompt = self._spec.prompt_builder(dna_context)
        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            add_special_tokens=False,
        )
        inputs = {name: value.to(self._device) for name, value in inputs.items()}
        with torch.inference_mode():
            outputs = self._model(**inputs, return_dict=True)
        logits = outputs.logits[0, -1].detach().float().cpu().tolist()
        direct = canonical_softmax(logits, self._vocabulary.ids)
        probabilities = apply_generation_policy(
            self.policy.policy_id,
            self._vocabulary.tokens,
            direct,
        )
        return DistributionState(
            tokens=self._vocabulary.tokens,
            probabilities=probabilities,
            metadata={
                "policy_id": self.policy.policy_id,
                "model_id": self.policy.model_id,
                "revision": self.policy.revision,
                "device": self._device,
                "dtype": self._dtype_name,
                "context_bases": len(normalize_dna(dna_context)),
            },
        )


def load_adapter(
    policy_id: str,
    *,
    device: str = "auto",
    dtype: str = "auto",
    allow_cpu_fallback: bool = True,
    cache_dir: str | None = None,
    local_files_only: bool = False,
) -> HuggingFaceDNAAdapter:
    """Load a pinned model policy locally.

    This function downloads weights when they are not already cached. Call it
    only after the caller has explicitly chosen to hydrate model artifacts.
    """

    if policy_id not in POLICIES:
        raise ValueError(f"unknown model policy: {policy_id}")
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError("install the optional 'models' dependencies first") from error

    runtime = resolve_torch_runtime(
        device,
        allow_cpu_fallback=allow_cpu_fallback,
        dtype=dtype,
    )
    spec = POLICIES[policy_id]
    shared = {
        "revision": spec.policy.revision,
        "trust_remote_code": True,
        "cache_dir": cache_dir,
        "local_files_only": local_files_only,
    }
    tokenizer = load_tokenizer(
        policy_id,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
    )
    model = _load_model_from_spec(
        AutoModelForCausalLM,
        AutoTokenizer,
        spec,
        model_kwargs={"dtype": runtime.torch_dtype, **shared},
        cache_dir=cache_dir,
        local_files_only=local_files_only,
    ).to(runtime.device)
    model.eval()
    setup = getattr(model, "setup_tokenizer", None)
    if callable(setup):
        setup(tokenizer)
    return HuggingFaceDNAAdapter(
        policy_id,
        tokenizer=tokenizer,
        model=model,
        device=runtime.device,
        dtype_name=runtime.dtype_name,
    )
