import torch
from transformers import BertTokenizer, BertForSequenceClassification
from app.text_utils import preprocess_text_batch, contains_malay_slang
from typing import List, Dict

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load Stage 1 (binary: hate vs non-hate)
stage1_model     = BertForSequenceClassification.from_pretrained(
    "experiment/stage1/s1_mb_model"
).to(device)
stage1_tokenizer = BertTokenizer.from_pretrained(
    "experiment/stage1/s1_mb_model"
)
stage1_model.eval()

# Load Stage 2 (multilabel: hate types)
stage2_model     = BertForSequenceClassification.from_pretrained(
    "experiment/stage2/s2_mb_model"
).to(device)
stage2_tokenizer = BertTokenizer.from_pretrained(
    "experiment/stage2/s2_mb_model"
)
stage2_model.eval()

# Hate-type labels
LABELS = ["Race", "Religion", "Gender", "Sexual_Orientation"]

def predict_toxic_and_hate_type(
    texts: List[str], 
    batch_size: int = 32
) -> tuple[List[int], Dict[int, List[str]], List[str]]:
    """
    Predict hate and hate types for a batch of texts.

    Returns:
    - all_preds1: List[int], 0 = non-hate, 1 = hate
    - hate_type_dict: Dict[int, List[str]], indices -> hate types
    - cleaned_texts: List[str], preprocessed tweets
    """

    if not texts:
        return [], {}, []

    # Preprocess tweets
    cleaned_texts = preprocess_text_batch(texts)

    # Stage 1: Binary hate detection
    all_preds1: List[int] = []

    for i in range(0, len(cleaned_texts), batch_size):
        batch_cleaned = cleaned_texts[i : i + batch_size]
        inputs1 = stage1_tokenizer(
            batch_cleaned,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128
        )
        inputs1 = {k: v.to(device) for k, v in inputs1.items()}

        with torch.no_grad():
            logits1 = stage1_model(**inputs1).logits
            batch_preds = torch.argmax(logits1, dim=1).cpu().tolist()

        # Apply Malay toxic slang override
        for j, text_idx in enumerate(range(i, i + len(batch_cleaned))):
            if batch_preds[j] == 0 and contains_malay_slang(texts[text_idx]):
                batch_preds[j] = 1

        all_preds1.extend(batch_preds)

    # Stage 2: Hate type detection
    hate_indices = [idx for idx, p in enumerate(all_preds1) if p == 1]
    hate_type_dict: Dict[int, List[str]] = {}

    if hate_indices:
        toxic_cleaned = [cleaned_texts[idx] for idx in hate_indices]

        for i in range(0, len(toxic_cleaned), batch_size):
            batch_cleaned = toxic_cleaned[i : i + batch_size]
            inputs2 = stage2_tokenizer(
                batch_cleaned,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128
            )
            inputs2 = {k: v.to(device) for k, v in inputs2.items()}

            with torch.no_grad():
                logits2 = stage2_model(**inputs2).logits
                probs2 = torch.sigmoid(logits2).cpu()

            for j, row in enumerate(probs2):
                orig_idx = hate_indices[i + j]
                chosen = [LABELS[k] for k, v in enumerate(row) if v > 0.5]  # simple >0.5 cutoff
                hate_type_dict[orig_idx] = chosen if chosen else ["Other_Hate"]

    return all_preds1, hate_type_dict, cleaned_texts
