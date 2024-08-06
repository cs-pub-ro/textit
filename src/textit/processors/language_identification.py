import fasttext
import fasttext.util
from pkg_resources import resource_filename


model_path = resource_filename('textit.processors.lang_id', 'lid.176.bin')
model = fasttext.load_model(model_path)

def get_romanian_score(text):
	# Get predictions for all languages
	
	normalized_text = ' '.join(text.split())
	predictions = model.predict(normalized_text, k=176)  # 176 is the total number of languages

	# Find the score for Romanian
	for lang, score in zip(predictions[0], predictions[1]):
		if lang == '__label__ro':  # 'ro' is the ISO 639-1 code for Romanian
			return score
	
	# If Romanian is not in the predictions (very unlikely), return 0
	return 0

def language_identification(text: str) -> str:
	"""
	Identify the language of the text and tag it.
	
	Args:
		text (str): The input text for language identification.
	
	Returns:
		str: The input text with a language tag prepended.
	"""
	
	score = get_romanian_score(text)
	print(score)
	return text
