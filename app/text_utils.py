import re
from langdetect import detect
from slangdict.malaytoxicdict import malaytoxicdict  # toxic Malay words
import nltk
import os

def ensure_nltk_resources():
    """Ensure NLTK resources are available; download if missing."""
    resources = {
        'tokenizers/punkt': 'punkt',
        'corpora/stopwords': 'stopwords'
    }
    
    for path, name in resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            print(f"Resource '{name}' not found. Downloading...")
            nltk.download(name, quiet=True)

# Execute the check immediately upon import
ensure_nltk_resources()

# Language detection
def fast_lang(text: str) -> str:
    try:
        return detect(text)
    except:
        return "ms"

# Preprocessing for Stage 1
def preprocess_text(text: str) -> str:
    """
    Minimal cleaning: lowercase + collapse spaces
    Keeps emojis, URLs, mentions, and slang intact
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def preprocess_text_batch(texts):
    return [preprocess_text(t) for t in texts]

# Malay toxic slang checker
def contains_malay_slang(text: str) -> bool:
    """
    Return True if any toxic Malay slang word is present.
    """
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    for slang in malaytoxicdict:
        if re.search(r"\b" + re.escape(slang) + r"\b", text):
            return True
    return False
