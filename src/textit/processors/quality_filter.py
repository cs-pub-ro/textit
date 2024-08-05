from collections import Counter
import unicodedata
import re
import string
import numpy as np

TRANSLATION_TABLE_PUNCTUATION = str.maketrans("", "", string.punctuation)
PRECISION = 8

NGRAM_DUPE_THRESHOLD = 2


def normalize(
        text: str,
        remove_punct: bool = True,
        lowercase: bool = True,
        nfd_unicode: bool = True,
        white_space: bool = True
) -> str:
    """ Normalize the text by lowercasing and removing punctuation. """
    # remove punctuation
    if remove_punct:
        text = text.translate(TRANSLATION_TABLE_PUNCTUATION)

    # lowercase
    if lowercase:
        text = text.lower()

    if white_space:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)

    # NFD unicode normalization
    if nfd_unicode:
        text = unicodedata.normalize("NFD", text)

    return text


def form_ngrams(sequence, n):
    history = []
    # build the first ngram, yielding only when we have a full ngram
    while n > 1:
        try:
            next_item = next(sequence)
        except StopIteration:
            # no more data, terminate the generator
            return
        history.append(next_item)
        n -= 1

    # yield each ngram we have, then add the next item and repeat
    for item in sequence:
        history.append(item)
        yield tuple(history)
        del history[0]


def RPS_Frac_Chars_In_Top_NGram(text: str, NGRAM_SIZE: int):  # noqa

	normalized_content = normalize(text)

	normalized_words = tuple(normalized_content.split())

	# get the most common ngram
	most_common_ngram = Counter(
		# fetch the ngrams from the document if they exist, otherwise
		# compute them
		form_ngrams(iter(normalized_words), NGRAM_SIZE)
	).most_common(1)

	if len(most_common_ngram) == 0:
		return 0.0

	ngram, count = most_common_ngram[0]

	if count <= 1:
		return 0.0

	total_chars = sum(len(w) for w in normalized_words)
	score = sum(len(w) for w in ngram) * count / total_chars
	score = round(score, PRECISION)
	return score

def RPS_Frac_Chars_In_Dupe_NGrams(text: str, NGRAM_SIZE: int):
	r""" Computes the fraction of characters in
	duplicate word N-grams. This operates on the lower-cased, punctation
	removed content. The function also ensures that characters in overlapping
	ngrams are only counted once."""

	normalized_content = normalize(text)
	normalized_words = tuple(normalized_content.split())

	if len(normalized_words) < NGRAM_SIZE:
		return 0.0

	doc_n_grams = (
			tuple(form_ngrams(
				iter(normalized_words), NGRAM_SIZE
			))
	)

	# keep only ngrams which occur at least twice
	ngram_dupes = {
		ngram for ngram, count in Counter(doc_n_grams).items() if count > 1
	}

	duplicated_grams = np.zeros(len(normalized_words), dtype=int)

	i = 0
	for ngram in doc_n_grams:
		if ngram in ngram_dupes:
			duplicated_grams[i: i + NGRAM_SIZE] = 1

		i += 1

	word_lengths = np.array(list(map(len, normalized_words)))
	chars_duped = np.sum(word_lengths * duplicated_grams)
	total_chars = np.sum(word_lengths)

	if total_chars == 0:
		return 0.0

	score = float(chars_duped / total_chars)
	score = round(score, PRECISION)
	return score



def quality_filter(text: str) -> str:
	"""
	Filter the text based on quality criteria.

	Args:
		text (str): The input text to be filtered.

	Returns:
		str: The filtered text, or an empty string if it doesn't meet quality standards.
    """
	ngram_2 = RPS_Frac_Chars_In_Top_NGram(text, 2)
	ngram_3 = RPS_Frac_Chars_In_Top_NGram(text, 3)
	ngram_4 = RPS_Frac_Chars_In_Top_NGram(text, 4)

	ngram_5 = RPS_Frac_Chars_In_Dupe_NGrams(text, 5)
	ngram_6 = RPS_Frac_Chars_In_Dupe_NGrams(text, 6)
	ngram_7 = RPS_Frac_Chars_In_Dupe_NGrams(text, 7)
	ngram_8 = RPS_Frac_Chars_In_Dupe_NGrams(text, 8)
	ngram_9 = RPS_Frac_Chars_In_Dupe_NGrams(text, 9)
	ngram_10 = RPS_Frac_Chars_In_Dupe_NGrams(text, 10)

	return text
