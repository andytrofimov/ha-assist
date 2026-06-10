from functools import lru_cache

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter
from pydantic import BaseModel, ConfigDict


class NormalizedText(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_text: str
    tokens: tuple[str, ...]
    normal_forms: tuple[str, ...]
    normalized_text: str
    state_forms: tuple[str, ...] = ()


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
        state_forms: list[str] = []

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
            state_form = state_predicate_form(token)
            if state_form:
                state_forms.append(state_form)

        return NormalizedText(
            original_text=text,
            tokens=tokens,
            normal_forms=normal_forms,
            normalized_text=" ".join(normal_forms),
            state_forms=state_forms,
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


def state_predicate_form(token) -> str | None:
    if (
            token.feats.get("VerbForm") == "Part"
            and token.feats.get("Voice") == "Pass"
            and token.feats.get("Variant") == "Short"
    ):
        return token.lemma or token.text
    if token.text == "открыто":
        return "открыть"
    return None


STOP_WORDS = {
    "пожалуйста",
    "сейчас",
    "немедленно",
    "быстро",
    "срочно",
    "ну",
    "давай",
}


# Возвращает нормализованный текст без общих слов, например "сейчас"
def remove_generic_words(text: NormalizedText) -> str:
    return " ".join(
        word for word in text.normal_forms
        if word not in STOP_WORDS
    )


@lru_cache(maxsize=8192)
def normalize(text: str) -> NormalizedText:
    # Результат нормализации не изменяется после создания, поэтому его можно
    # переиспользовать для стабильных имен entity, alias и локаций.
    return get_text_normalizer().normalize(text)


def normalized_words(text: NormalizedText) -> set[str]:
    return set(text.normal_forms) | set(text.tokens)


def normalized_form_words(text: NormalizedText) -> set[str]:
    return set(text.normal_forms)


def normalized_token_words(text: NormalizedText) -> set[str]:
    return set(text.tokens)


def split_aliases(aliases: str) -> list[str]:
    return [
        alias.strip()
        for alias in aliases.replace(",", "/").split("/")
        if alias.strip() and not alias.strip().startswith("ComputedNameType.")
    ]


@lru_cache(maxsize=1)
def get_text_normalizer() -> RussianTextNormalizer:
    return RussianTextNormalizer()
