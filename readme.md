# Geological Paper Data Extraction Scripts

This project provides a suite of Python scripts designed to extract metadata and geographical locations from geological research papers in PDF format. It leverages Large Language Models (LLMs) for extraction tasks, offers geocoding capabilities, and includes a command-line interface (CLI) for interacting with a central data repository.

## GeoAIHub frontend

https://geoaihub.dtx-colab.com/

!TODO add repo

## GeoAIHub backend

https://geoaihub-back.dtx-colab.com/

!TODO add repo

## Features

- **Metadata Extraction**: Extracts title, authors, DOI, journal, publication year, and keywords from the first page of PDF papers.
- **Location Extraction**: Identifies and extracts geographical location names mentioned within the papers using LLMs.
- **Location Importance Scoring**: Assigns an importance score to extracted locations.
- **Location Frequency Calculation**: Counts the occurrences of each identified location within the paper.
- **Text Preparation**: Prepares paper text for efficient LLM processing by focusing on relevant sections and splitting large texts.
- **Geocoding**: Geocodes extracted locations using Nominatim, Google Geocoding API, and a local cache.
- **Central Repository Integration**: Saves extracted metadata and locations to a central application and manages API interactions.
- **User Authentication**: Securely authenticates users before interacting with the central repository.
- **Account Verification**: Provides an interface for administrators to verify new user accounts for the central repository.
- **Benchmarking**: Includes a script to benchmark the performance of the location extraction process against ground truth data.
- **Command-Line Interface**: An interactive CLI ([`interface.py`](/home/dtx/tese/extraction_scripts/interface.py)) for easy operation of the extraction, geocoding, and account verification processes.

## Setup

1.  **Clone the repository:**

    ```bash
    git clone git@github.com:PedroF43/extraction_scripts.git
    cd extraction_scripts
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Copy the example environment file and fill in your details.
    Edit `.env` with your API keys, URLs, and desired configurations. Key variables include:
    - `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODEL_METADATA`
    - `PERCENTILE_CUTOFF`, `MAX_TOKENS_PER_PART`, `OVERLAP_PERCENTAGE`, `SYSTEM_PROMPT`
    - `CENTRAL_APP_URL` (URL of your central data repository/application)
    - `GOOGLE_GEOCODING_API_KEY`
    - Benchmark-specific LLM variables (e.g., `LLM_API_URL_BENCHMARK_EVALUATOR`)

## Usage

The primary way to use this project is through the command-line interface.

1.  **Place PDF papers** you want to process into the `papers/` directory (create it if it doesn't exist).
2.  **Run the interface:**
    ```bash
    python interface.py
    ```
3.  **Follow the on-screen menu:**
    - **Login:** You will be prompted to log in with credentials for the central repository.
    - **Process papers:** (Option 1) Extracts metadata and locations from PDFs in the `papers/` folder and saves them to the central repository.
    - **Geocoding menu:** (Option 2) Fetches locations marked for geocoding from the repository and attempts to geocode them.
    - **Verify new accounts:** (Option 3) For admin users, lists pending account verification requests and allows verification.

## Benchmarking

To evaluate the performance of the location extraction process:

1.  **Place PDF papers** for benchmarking into the `benchmark_papers/papers/` directory.
2.  **Prepare ground truth data:** Create or update the `benchmark_papers/ground_truth.json` file. This file should contain a JSON object where keys are the PDF filenames (e.g., "mypaper.pdf") and values are lists of the expected location names.
    Example `ground_truth.json`:
    ```json
    {
      "paper1.pdf": "Location A", "Location B",
      "paper2.pdf": "Location C", "Location D", "Location E"
    }
    ```
3.  **Ensure environment variables** for the benchmark evaluator LLM are set in your `.env` file (e.g., `LLM_API_URL_BENCHMARK_EVALUATOR`, `LLM_API_KEY_BENCHMARK_EVALUATOR`, `LLM_MODEL_BENCHMARK_EVALUATOR`).
4.  **Run the benchmark script:**
    ```bash
    python benchmark.py
    ```
5.  **Review results:**
    - Extracted locations for each paper during the benchmark run are saved in `benchmark_papers/extracted_locations.json`.
    - The detailed evaluation, including True Positives, False Positives, False Negatives, and performance metrics, is saved in `benchmark_papers/benchmark_results.json`.
