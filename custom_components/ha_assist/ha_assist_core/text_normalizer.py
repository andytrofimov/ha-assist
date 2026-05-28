from functools import lru_cache

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter
from pydantic import BaseModel


class NormalizedText(BaseModel):
    original_text: str
    tokens: list[str]
    normal_forms: list[str]
    normalized_text: str


class AgreementFeatures(BaseModel):
    number: str | None = None
    gender: str | None = None
    word: str


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
            has_parseable_text = (
                    any(char.isalpha() or char.isdigit() for char in token.text)
                    or token.text in {"%", "°"}
            )
            if not has_parseable_text:
                continue

            if any(char.isalpha() for char in token.text):
                token.lemmatize(self.morph_vocab)
            tokens.append(token.text)
            normal_forms.append(token.lemma or token.text)

        return NormalizedText(
            original_text=text,
            tokens=tokens,
            normal_forms=normal_forms,
            normalized_text=" ".join(normal_forms),
        )

    def first_word_agreement(self, text: str) -> AgreementFeatures:
        doc = Doc(text.lower())
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)

        fallback_word = ""
        for token in doc.tokens:
            if not any(char.isalpha() for char in token.text):
                continue
            if not fallback_word:
                fallback_word = token.text
            token.lemmatize(self.morph_vocab)
            if token.pos in {"NOUN", "PROPN"}:
                return AgreementFeatures(
                    number=token.feats.get("Number"),
                    gender=token.feats.get("Gender"),
                    word=token.lemma or token.text,
                )

        return AgreementFeatures(word=fallback_word or text.lower().strip())


def agree_adjective(
        features: AgreementFeatures,
        masculine: str,
        feminine: str,
        neuter: str,
        plural: str,
) -> str:
    if features.number == "Plur":
        return plural
    if features.gender == "Fem":
        return feminine
    if features.gender == "Neut":
        return neuter
    return masculine


@lru_cache(maxsize=1)
def get_text_normalizer() -> RussianTextNormalizer:
    return RussianTextNormalizer()
