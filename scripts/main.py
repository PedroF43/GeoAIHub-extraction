from scripts.locations.text_extractor import (
    get_location_frequencies,
)
from scripts.metadata.doi_extractor import (
    extract_doi_page_number_from_pdf,
    extract_first_page_text,
)
from scripts.locations.text_preparation import prepare_text_for_extraction
from scripts.services.endpoints import (
    check_if_doi_already_in_db,
    patch_extraction_time,
    post_central_repository,
    post_matched_locations_request,  # Added missing import
)
from scripts.services.llm import location_extractor, metadata_extractor
import time

from scripts.services.schemas import (
    PostPaperLocationData,
    PostPaperMetadata,
)


def extract_metadata(paper_path):
    start_time = time.time()
    first_page, page_number = extract_first_page_text(paper_path)

    try:
        doi = extract_doi_page_number_from_pdf(first_page)
        unique_status = check_if_doi_already_in_db(doi)

        # Check if DOI is already in the database
        if not unique_status:
            raise Exception(f"Paper with DOI {doi} already exists in the database")

    except Exception as e:
        doi = None
        # Re-raise the exception if it's about uniqueness
        if "already exists" in str(e):
            raise e

    # Extract metadata using LLM regardless of DOI extraction success
    metadata = metadata_extractor(first_page)

    # Common extraction logic
    title = metadata["paper_title"]
    authors = ", ".join([author["author_name"] for author in metadata["authors"]])
    journal = metadata["journal_name"]
    year = metadata["publication_year"]
    keywords = ", ".join([keyword["keyword_name"] for keyword in metadata["keywords"]])

    # Use DOI from metadata if extraction failed
    if not doi:
        doi = metadata["doi_number"]
        # Check uniqueness again if we got DOI from metadata
        unique_status = check_if_doi_already_in_db(doi)
        response = unique_status.json()
        if not response.get("unique", False):
            raise Exception(f"Paper with DOI {doi} already exists in the database")

    extraction_time = time.time() - start_time

    return PostPaperMetadata(
        title=title,
        authors=authors,
        doi=doi,
        journal=journal,
        page_number=page_number,
        year=year,
        keywords=keywords,
        location_number=0,
        extraction_time=extraction_time,
    )


def extract_locations(paper_path):
    start_time = time.time()
    found_locations = []
    frequencies_list = []

    try:
        extraction_text, total_tokens = prepare_text_for_extraction(paper_path)

        # Keep track of location names we've already seen
        seen_location_names = set()
        # Store the original location names for frequency calculation
        original_location_names = []
        # Store the display version with country for output
        display_location_names = []
        location_importance_scores = []
        for part in extraction_text:
            try:
                location_names = location_extractor(part)
                # Add only locations with unique location_name values
                for loc in location_names:
                    if (
                        loc.get("location_name")
                        and loc["location_name"] not in seen_location_names
                    ):
                        seen_location_names.add(loc["location_name"])
                        original_location_names.append(loc["location_name"])

                        # Format as "location_name, country" if country is available
                        location_display = loc["location_name"]
                        location_importance_score = loc.get("importance_score")

                        if loc.get("location_country"):
                            location_display = (
                                f"{loc['location_name']}, {loc['location_country']}"
                            )

                        display_location_names.append(location_display)
                        found_locations.append(loc)
                        location_importance_scores.append(location_importance_score)
            except Exception as e:
                print(
                    f"Error extracting locations from article {paper_path} error: {str(e)}"
                )
                continue

        # Get frequencies using the original location names (without country)
        try:
            frequencies_dict = get_location_frequencies(
                original_location_names, pdf_path=paper_path
            )
            # Convert dictionary to list in the same order as original_location_names
            frequencies_list = [
                frequencies_dict.get(name, 0) for name in original_location_names
            ]
        except Exception as e:
            print(f"Error getting location frequencies: {str(e)}")
            # Provide default frequencies if we encounter an error
            frequencies_list = [1] * len(original_location_names)

    except Exception as e:
        print(f"Error in location extraction process: {str(e)}")

    extraction_time = time.time() - start_time

    return PostPaperLocationData(
        location_number=len(display_location_names),
        location_names=display_location_names,
        location_importance_scores=location_importance_scores,
        location_frequencies=frequencies_list,
        extraction_time=extraction_time,
    ), total_tokens


# Process each paper without printing details for each one
def process_single_paper(paper_path):
    """Process a single paper and extract metadata and locations.

    Args:
        paper_path: Path to the paper file

    Returns:
        tuple: (metadata, locations) containing the extracted information
    """
    metadata = extract_metadata(paper_path)
    locations, _ = extract_locations(paper_path)

    metadata.location_number = locations.location_number
    return metadata, locations


def save_paper_to_repository(metadata, locations):
    """Save extracted paper data to central repository.

    Args:
        metadata: Paper metadata
        locations: Extracted locations

    Returns:
        str: The article ID from the repository
    """
    article_id = post_central_repository(metadata)
    article_id = article_id.json()

    for location_name, frequency in zip(
        locations.location_names, locations.location_frequencies
    ):
        post_matched_locations_request(article_id, location_name, frequency)

    extraction_time = metadata.extraction_time + locations.extraction_time
    patch_extraction_time(extraction_time, article_id)

    return article_id


if __name__ == "__main__":
    import os
    import json

    # Define the directory containing the papers
    papers_dir = "resultados/papers_professor"

    # Check if directory exists
    if not os.path.isdir(papers_dir):
        print(f"Error: Directory '{papers_dir}' not found")
        exit(1)

    # Get all PDF files in the directory
    pdf_files = [f for f in os.listdir(papers_dir) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print(f"No PDF files found in '{papers_dir}'")
        exit(0)

    # Define report file
    report_file = "location_extraction_report.json"

    # Load existing report if it exists
    report = {}
    if os.path.exists(report_file):
        try:
            with open(report_file, "r") as f:
                report = json.load(f)
            print(f"Loaded existing report with {len(report)} papers")
        except Exception as e:
            print(f"Could not load existing report: {str(e)}")

    print(f"Processing {len(pdf_files)} PDF files...")

    # Process each PDF file
    for pdf_file in pdf_files:
        # Skip if already processed (unless you want to reprocess)
        if pdf_file in report:
            print(f"Skipping already processed: {pdf_file}")
            continue

        paper_path = os.path.join(papers_dir, pdf_file)
        print(f"Processing: {pdf_file}")
        try:
            location_data, _ = extract_locations(paper_path)
            report[pdf_file] = {
                "location_names": location_data.location_names,
                "location_frequencies": location_data.location_frequencies,
                "location_number": location_data.location_number,
                "location_importance_scores": location_data.location_importance_scores,
            }
            print(f"✓ Found {location_data.location_number} locations in {pdf_file}")
        except Exception as e:
            print(f"✗ Error processing {pdf_file}: {str(e)}")
            report[pdf_file] = {"error": str(e)}

        # Save report after each paper is processed
        try:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"Updated report saved to '{report_file}'")
        except Exception as e:
            print(f"Warning: Could not save report: {str(e)}")

    # Print summary report
    print("\n===== LOCATION EXTRACTION REPORT =====")
    for paper_name, data in report.items():
        if "error" in data:
            print(f"\n{paper_name}: ERROR - {data['error']}")
            continue

        print(f"\n{paper_name}: {data['location_number']} locations found")
        if data["location_names"]:
            print("  Locations:")
            for loc, freq in zip(data["location_names"], data["location_frequencies"]):
                print(f"    - {loc} (mentioned {freq} times)")

    print(f"\nFinal report saved to '{report_file}'")
