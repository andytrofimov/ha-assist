import re

from .text_normalizer import NormalizedText, get_text_normalizer


def normalize(text: str) -> NormalizedText:
    return get_text_normalizer().normalize(text)


def normalized_words(text: NormalizedText) -> set[str]:
    words = set(text.normal_forms) | set(text.tokens)
    expanded: set[str] = set()
    for word in words:
        if word and not word.isdigit():
            expanded.update(word_variants(word))
    return expanded


def raw_words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-zА-Яа-яЁё]+", text.lower()))


def raw_word_variants(text: str) -> set[str]:
    return expanded_words(raw_words(text))


def word_variants(word: str) -> set[str]:
    variants = {word}
    if word.endswith(("ы", "и")) and not word.endswith(("ами", "ями")) and len(word) > 4:
        variants.add(word[:-1])
    if word.endswith("ая") and len(word) > 3:
        variants.add(f"{word[:-2]}ый")
        variants.add(f"{word[:-2]}ой")
    if word.endswith("яя") and len(word) > 3:
        variants.add(f"{word[:-2]}ий")
        variants.add(f"{word[:-2]}ей")
    if word.endswith(("а", "я")) and len(word) > 3:
        variants.add(f"{word[:-1]}е")
    if word.endswith("а") and len(word) > 3:
        variants.add(f"{word[:-1]}ами")
    if word[-1:] not in {"а", "е", "ё", "и", "й", "о", "у", "ы", "ь", "э", "ю", "я"}:
        variants.add(f"{word}е")
    return variants


def expanded_words(words: set[str]) -> set[str]:
    expanded: set[str] = set()
    for word in words:
        expanded.update(word_variants(word))
    return expanded


def split_aliases(aliases: str) -> list[str]:
    return [
        alias.strip()
        for alias in aliases.replace(",", "/").split("/")
        if alias.strip() and not alias.strip().startswith("ComputedNameType.")
    ]
