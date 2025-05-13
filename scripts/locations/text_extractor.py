import fitz
import math
import re
from .abstract_extractor import abstract_extractor
from .table_extractor import extract_tables, patterns


def extract_text(pdf_path):
    """
    Extract text from a PDF document, separating abstract from main content.

    Args:
        pdf_path (str): Path to the PDF file

    Returns:
        tuple: (abstract_text, full_text) where both are strings
    """
    treated_text = []

    try:
        with fitz.open(pdf_path) as doc:
            if doc.page_count == 0:
                return "", ""

            num_pages = doc.page_count
            number_of_pages_to_start_checking_ending = (
                calculate_ignorable_page_threshold(num_pages)
            )

            # First extract abstract from first page
            first_page = doc.load_page(0)
            first_page_text = first_page.get_text("words")
            abstract = abstract_extractor(first_page_text)

            # Now process all pages
            for i in range(1, num_pages):
                page = doc.load_page(i)
                page_text = page.get_text("words")

                # Check if we've reached ending sections
                if i >= number_of_pages_to_start_checking_ending:
                    processed_text = process_page(page, page_text)
                    last_useful_page_text = check_ending_keywords(processed_text)
                    if last_useful_page_text:
                        try:
                            last_page_no_references = remove_references(
                                [last_useful_page_text]
                            )
                            if last_page_no_references and last_page_no_references[0]:
                                treated_text.append(last_page_no_references)
                        except Exception as e:
                            print(f"Error processing ending page {i}: {e}")
                        break

                # Process regular page content
                try:
                    processed_text = process_page(page, page_text)
                    text_content = " ".join(processed_text)
                    if text_content:
                        page_text_no_refs = remove_references([text_content])
                        treated_text.append(page_text_no_refs)
                except Exception as e:
                    print(f"Error processing page {i}: {e}")
                    continue

        # Create flattened text with proper error checking
        full_text = ""
        if treated_text:
            try:
                valid_elements = [
                    item[0]
                    for item in treated_text
                    if item and len(item) > 0 and item[0]
                ]
                full_text = " ".join(valid_elements)
            except Exception as e:
                print(f"Error flattening extracted text: {e}")

        return abstract, full_text

    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return "", ""


def process_page(page, page_text):
    table_pattern = patterns("table_pattern")
    extracted_tables = extract_tables(page, table_pattern)
    return_text = []

    # Get page height
    page_height = page.rect.height
    # Calculate thresholds at 5% and 95% of page height
    min_y = page_height * 0.05
    max_y = page_height * 0.95

    if extracted_tables:
        return process_page_with_tables(page_text, extracted_tables, min_y, max_y)
    else:
        for word in page_text:
            if min_y < word[1] < max_y:
                return_text.append(word[4])

        return return_text


def process_page_with_tables(page_text, tables, min_y, max_y):
    page_text_without_tables = []

    for word in page_text:
        if not is_word_inside_any_table(word, tables) and min_y < word[1] < max_y:
            page_text_without_tables.append(word[4])

    return page_text_without_tables


def is_word_inside_any_table(word, tables):
    word_coords = word[0:4]
    for table in tables:
        table_coords = table[0:4]
        if (
            word_coords[0] > table_coords[0]
            and word_coords[1] > table_coords[1]
            and word_coords[2] < table_coords[2]
            and word_coords[3] < table_coords[3]
        ):
            return True
    return False


def check_ending_keywords(text):
    ending_keywords = {
        "acknowledgments",
        "author contribution",
        "declarations",
        "references",
    }

    # Join the text into a single string and convert to lowercase
    text_lower = " ".join(text).lower()

    # Create a regular expression pattern
    pattern = (
        r"\b(?:" + "|".join(re.escape(keyword) for keyword in ending_keywords) + r")\b"
    )

    # Use re.search to find any match
    match = re.search(pattern, text_lower)
    if match:
        return " ".join(text)[: match.start() + len(match[0])]
    else:
        return None


def calculate_ignorable_page_threshold(page_number):
    """Calculate the threshold beyond which pages should be ignored."""
    return math.floor(page_number - math.log(page_number, 1.9))


def remove_references(text):
    """
    Remove references from text and print them.

    Args:
        text (list): List containing text to process

    Returns:
        list: List with processed text
    """
    if not text or not isinstance(text, list) or len(text) == 0:
        return [""]

    try:
        # Remove hyphenated words in line breaks
        cleaned_text = re.sub(r"- ", "", text[0])

        # Remove references
        cleaned_text = re.sub(r"\([^()]*\d{4}[^()]*\)", "", cleaned_text)
        return [cleaned_text]
    except Exception as e:
        print(f"Error removing references: {e}")
        return [""]


def get_location_frequencies(locations, pdf_path):
    """
    Count occurrences of location names in a PDF document.

    Args:
        locations (list): List of location names to search for
        pdf_path (str, optional): Path to the PDF file. If not provided,
                                  uses the path from the main function

    Returns:
        dict: Dictionary with locations as keys and their frequencies as values
    """

    frequencies = {location: 0 for location in locations}

    with fitz.open(pdf_path) as doc:
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            page_text = page.get_text()

            # Count occurrences of each location in this page
            for location in locations:
                # Case insensitive search using regular expressions
                pattern = r"\b" + re.escape(location) + r"\b"
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                frequencies[location] += len(matches)

    return frequencies
