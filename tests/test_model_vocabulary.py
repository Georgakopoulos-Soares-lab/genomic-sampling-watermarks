from __future__ import annotations

import unittest

from genomic_watermarks.dna import canonical_kmers
from genomic_watermarks.models.vocabulary import extract_canonical_vocabulary


class FakeCarbonTokenizer:
    k = 6
    kmers = list(canonical_kmers())
    dna_token_to_id = {token: 1003 + index for index, token in enumerate(kmers)}
    dna_id_to_token = {token_id: token for token, token_id in dna_token_to_id.items()}

    def get_vocab(self) -> dict[str, int]:
        # Carbon's combined public mapping can retain a BPE ID for an
        # overlapping string. The dedicated DNA mapping must win.
        combined = dict(self.dna_token_to_id)
        combined["CCCCCC"] = 17
        return combined

    def convert_ids_to_tokens(self, token_id: int) -> str:
        return self.dna_id_to_token[token_id]


class FakeGeneratorTokenizer:
    k = 6
    kmers = list(canonical_kmers())
    vocab = {token: 32 + index for index, token in enumerate(kmers)}
    ids_to_tokens = {token_id: token for token, token_id in vocab.items()}

    def convert_ids_to_tokens(self, token_id: int) -> str:
        return self.ids_to_tokens[token_id]


class ModelVocabularyTest(unittest.TestCase):
    def test_carbon_uses_dedicated_dna_mapping(self) -> None:
        vocabulary = extract_canonical_vocabulary(FakeCarbonTokenizer())
        self.assertEqual(vocabulary.mapping_source, "dna_token_to_id")
        self.assertEqual(vocabulary.first_id, 1003)
        self.assertEqual(vocabulary.last_id, 5098)
        self.assertTrue(vocabulary.is_contiguous)
        cccccc = vocabulary.tokens.index("CCCCCC")
        self.assertNotEqual(vocabulary.ids[cccccc], 17)

    def test_generator_uses_vocab_after_32_specials(self) -> None:
        vocabulary = extract_canonical_vocabulary(FakeGeneratorTokenizer())
        self.assertEqual(vocabulary.mapping_source, "vocab")
        self.assertEqual(vocabulary.first_id, 32)
        self.assertEqual(vocabulary.last_id, 4127)
        self.assertTrue(vocabulary.is_contiguous)

    def test_wrong_k_is_rejected(self) -> None:
        tokenizer = FakeGeneratorTokenizer()
        tokenizer.k = 5
        with self.assertRaises(ValueError):
            extract_canonical_vocabulary(tokenizer)


if __name__ == "__main__":
    unittest.main()
