import re
import fitz  # PyMuPDF
from typing import List, Dict


def extract_first_page_text(pdf_path: str) -> tuple[str, int, int]:
    """
    Extract all text from the first page of a PDF document.

    Args:
        pdf_path: Path to the PDF file
    Returns:
        Tuple of (extracted text from the first page, page number, total pages)
    """
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        if total_pages > 0:
            page = doc[0]  # Get the first page
            text = page.get_text()
            return text, total_pages
        else:
            print(f"Error: PDF '{pdf_path}' has no pages.")
            return "", 0, 0
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return "", 0, 0


def backup_page_counter(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    return total_pages


def find_doi_matches(text: str) -> List[str]:
    """
    Apply DOI regex patterns to find matches in the extracted text.
    Return as soon as a match is found.

    Args:
        text: The extracted text to search for DOIs

    Returns:
        List of DOI strings found in the text
    """
    # Convert the regex patterns to Python format
    patterns = [
        r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",  # General DOI
        r"10\.1002/[^\s]+",  # Wiley DOI
        r"10\.\d{4}/\d+-\d+X?(\d+)\d+<[\d\w]+:[\d\w]*>\d+\.\d+\.\w+;\d",  # Complex Format DOI
        r"10\.1021/\w\w\d+",  # ACS DOI
        r"10\.1207/[\w\d]+\&\d+_\d+",  # Special Format DOI
    ]

    # Process text line by line for more accurate matching
    lines = text.split("\n")

    for pattern in patterns:
        # Check individual lines first
        for line in lines:
            line = line.strip()
            found = re.findall(pattern, line, re.IGNORECASE)
            if found:
                return found[0]

        # If no match in lines, try whole text
        found_in_whole = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if found_in_whole:
            return found_in_whole[0]

    return None


def extract_doi_page_number_from_pdf(text: str) -> Dict[str, List[str]]:
    """
    Extract DOIs from the first page of a PDF document.

    Args:
        pdf_path: Path to the PDF file
        verbose: Whether to print progress information

    Returns:
        Dictionary of DOI matches by pattern type
    """

    matches = find_doi_matches(text)

    return matches
