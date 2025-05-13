import os
import re
from typing import List, Tuple
import tiktoken
from dotenv import load_dotenv
from scripts.locations.text_extractor import extract_text


class KeywordContextFinder:
    def __init__(self, keywords: List[str], window: int = 1200):
        self.window = 4000
        # Precompile the regex pattern
        self.pattern = re.compile(
            r"\b(?:" + "|".join(map(re.escape, keywords)) + r")\b", flags=re.IGNORECASE
        )

    def find_contexts(self, text: str) -> str:
        if not text:
            return ""

        # Find all matches
        matches = [
            (match.start(), match.end()) for match in self.pattern.finditer(text)
        ]

        if not matches:
            return ""

        # Process contexts more efficiently
        return self._process_contexts(text, matches)

    def _process_contexts(self, text: str, matches: List[Tuple[int, int]]) -> str:
        text_length = len(text)
        contexts = []
        current_start, current_end = None, None

        for start, end in matches:
            context_start = max(0, start - self.window)
            context_end = min(text_length, end + self.window)

            if current_start is None:
                current_start, current_end = context_start, context_end
            elif context_start <= current_end:
                # Extend current context
                current_end = max(current_end, context_end)
            else:
                # Add current context and start a new one
                contexts.append(text[current_start:current_end])
                current_start, current_end = context_start, context_end

        # Add the last context
        if current_start is not None:
            contexts.append(text[current_start:current_end])

        # Join contexts efficiently
        return " ".join(context.replace("\n", " ") for context in contexts)


# Example usage
def find_text_surrounding_keywords(text: str) -> str:
    load_dotenv()
    window = os.environ.get("PART_SIZE")

    keywords = [
        # Direct location indicators
        "study area",
        "study site",
        "field area",
        "sampling site",
        "sample location",
        # Administrative divisions likely to precede location names
        "province of",
        "district of",
        "county of",
        "city of",
        "town of",
        "village of",
        # Geological context terms often followed by location names
        "basin",  # e.g., "Michigan Basin"
        "formation",  # e.g., "Morrison Formation"
        "complex",  # e.g., "Stillwater Complex"
        "range",  # e.g., "Cascade Range"
        # Common geological paper phrasing
        "outcrop at",
        "exposed at",
        "collected from",
        "located in",
        "situated in",
        # Regional context often followed by location names
        "region of",
        "area of",
    ]
    finder = KeywordContextFinder(keywords, window)
    return finder.find_contexts(text)


# Optional: Add a context manager for processing multiple texts efficiently
class KeywordContextProcessor:
    def __init__(self, keywords: List[str], window: int = 1200):
        self.finder = KeywordContextFinder(keywords, int(window))

    def process_texts(self, texts: List[str]) -> List[str]:
        return [self.finder.find_contexts(text) for text in texts]


def split_text_into_balanced_parts(text):
    """
    Splits text into parts with evenly balanced token counts using tiktoken.

    Args:
        text (str): The text to split
        max_tokens_per_part (int): Target maximum tokens per part
        overlap_percentage (float): Percentage of tokens to overlap between parts

    Returns:
        list: List of text parts with balanced token counts
    """

    max_tokens_per_part = int(os.environ.get("MAX_TOKENS_PER_PART", 10000))
    overlap_percentage = float(os.environ.get("OVERLAP_PERCENTAGE", 0.15))

    # Input validation
    if not text:
        return []

    if max_tokens_per_part <= 0:
        raise ValueError("max_tokens_per_part must be positive")

    if not 0 <= overlap_percentage < 1:
        raise ValueError("overlap_percentage must be between 0 and 1")

    # Get the encoding (only created once)
    encoding = tiktoken.get_encoding("cl100k_base")

    # Tokenize the entire text
    all_tokens = encoding.encode(text)
    total_tokens = len(all_tokens)

    # If text is small enough, return it as is
    if total_tokens <= max_tokens_per_part:
        return [text]

    # Calculate the overlap size in tokens
    overlap_tokens = int(max_tokens_per_part * overlap_percentage)

    # Calculate the effective number of unique tokens per part
    effective_tokens_per_part = max_tokens_per_part - overlap_tokens

    # Calculate total number of parts needed (ceiling division)
    num_parts = (
        total_tokens - overlap_tokens + effective_tokens_per_part - 1
    ) // effective_tokens_per_part

    # Recalculate tokens per part to distribute evenly
    balanced_tokens_per_part = (
        total_tokens + (num_parts - 1) * overlap_tokens
    ) // num_parts

    parts = []
    start_idx = 0

    for i in range(num_parts):
        # For the last part, include all remaining tokens
        end_idx = (
            total_tokens
            if i == num_parts - 1
            else min(start_idx + balanced_tokens_per_part, total_tokens)
        )

        # Get tokens for this part and decode to text
        print(len(all_tokens[start_idx:end_idx]))
        part_text = encoding.decode(all_tokens[start_idx:end_idx])
        parts.append(part_text)

        # Move the start index for the next part, considering overlap
        start_idx = max(0, end_idx - overlap_tokens)

        # If we've used all tokens, break the loop
        if end_idx >= total_tokens:
            break

    return parts


def split_text_into_parts(text):
    append_abstract_to_context = os.environ.get("APPEND_ABSTRACT_TO_CONTEXT", "True")

    abstract = text[0]
    parts_with_abstract = []
    text_surrounding_keywords = find_text_surrounding_keywords(text[1])
    parts = split_text_into_balanced_parts(text_surrounding_keywords)

    if append_abstract_to_context == "True":
        for part in parts:
            parts_with_abstract.append(abstract + part)
    else:
        for part in parts:
            parts_with_abstract.append(part)

    return parts_with_abstract


def prepare_text_for_extraction(pdf_path):
    text = extract_text(pdf_path)
    prepared_text = split_text_into_parts(text)

    # Calculate total token count
    total_tokens = 0
    encoding = tiktoken.get_encoding("cl100k_base")  # Get the encoding
    for part in prepared_text:
        tokens = encoding.encode(part)
        total_tokens += len(tokens)

    return prepared_text, total_tokens


if __name__ == "__main__":
    pdf_path = "papers/Fassbender.pdf"
    # Update the call to handle the tuple return value
    prepared_text, total_tokens = prepare_text_for_extraction(pdf_path)
    for part in prepared_text:
        print(part)

    print(f"\nTotal tokens across all parts: {total_tokens}")
