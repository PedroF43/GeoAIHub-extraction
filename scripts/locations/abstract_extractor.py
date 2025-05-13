def bbox_calculator(bbox):
    """Calculate where the abstract section ends based on bounding box coordinates."""
    for i in range(len(bbox) - 1):
        right_x, right_y = bbox[i][2], bbox[i][3]
        left_x, left_y = bbox[i + 1][0], bbox[i + 1][1]
        if abs(right_x - left_x) > 20 and abs(left_y - right_y) > 5:
            return i
    return len(bbox) - 1


def abstract_extractor(page_text):
    """Extract the abstract from page text."""
    extracted_text = []

    # Default method: find "abstract" in a single word
    abstract_start_index = None

    # Try each keyword from the list of words
    for keyword in [
        "abstract",
        "resumen",
    ]:  # Default keyword
        # Method 1: Find keyword as a substring in a single word
        start_idx = next(
            (
                i
                for i, word in enumerate(page_text)
                if keyword.lower() in word[4].lower()
            ),
            None,
        )
        if start_idx is not None:
            abstract_start_index = start_idx
            break

        # Method 2: Detect spaced letters (e.g., "a b s t r a c t")
        keyword_length = len(keyword)
        for i in range(len(page_text) - (keyword_length - 1)):
            # Check if consecutive words spell the keyword
            potential_keyword = "".join(
                [word[4].lower() for word in page_text[i : i + keyword_length]]
            )
            if potential_keyword == keyword.lower():
                abstract_start_index = i + (
                    keyword_length - 1
                )  # Use the index after the last letter
                break

        if abstract_start_index is not None:
            break

    if abstract_start_index is not None:
        # Get the text after "abstract" word or sequence
        abstract_text = page_text[abstract_start_index + 1 :]

        # Use bbox_calculator to find where the abstract ends
        abstract_end_idx = bbox_calculator(abstract_text)

        # Extract only the text that belongs to the abstract section
        for word in abstract_text[: abstract_end_idx + 1]:
            text = word[4]  # actual word text
            extracted_text.append(text)

        return " ".join(extracted_text)
    else:
        return ""
