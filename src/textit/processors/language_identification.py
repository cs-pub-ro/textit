import fasttext
import fasttext.util
from pkg_resources import resource_filename


# model_path = resource_filename('textit.processors.lang_id', 'lid.176.bin')
model_path = "/workspace/fasttext/lid.176.bin"
model = fasttext.load_model(model_path)

def get_romanian_score(text):
    normalized_text = ' '.join(text.split())
    predictions = model.predict(normalized_text, k=176)  # 176 is the total number of languages

    for lang, score in zip(predictions[0], predictions[1]):
        if lang == '__label__ro':  # 'ro' is the ISO 639-1 code for Romanian
            return score
    
    return 0

# Identifies the language and drops the text entries with less than 0.5 romanian score
def language_identification(text: str) -> str:
    """
    Identify the language of the text and tag it.
    
    Args:
        text (str): The input text for language identification.
    
    Returns:
        str: The input text with a language tag prepended.
    """
    
    score = get_romanian_score(text)

    if score < 0.5:
        return ""
    return text
