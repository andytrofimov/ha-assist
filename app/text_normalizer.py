from functools import lru_cache

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter
from pydantic import BaseModel


class NormalizedText(BaseModel):
    original_text: str
    tokens: list[str]
    normal_forms: list[str]
    normalized_text: str


class RussianTextNormalizer:
    def __init__(self) -> None:
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        embedding = NewsEmbedding()
        self.morph_tagger = NewsMorphTagger(embedding)

    def normalize(self, text: str) -> NormalizedText:
        doc = Doc(text.lower())
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)

        tokens: list[str] = []
        normal_forms: list[str] = []

        for token in doc.tokens:
            if not any(char.isalpha() for char in token.text):
                continue

            token.lemmatize(self.morph_vocab)
            tokens.append(token.text)
            normal_forms.append(token.lemma or token.text)

        return NormalizedText(
            original_text=text,
            tokens=tokens,
            normal_forms=normal_forms,
            normalized_text=" ".join(normal_forms),
        )

@lru_cache(maxsize=1)
def get_text_normalizer() -> RussianTextNormalizer:
    return RussianTextNormalizer()
