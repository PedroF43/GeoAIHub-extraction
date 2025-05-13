# Standard library imports
import os
import sys
import getpass

# Third-party imports
from tqdm import tqdm
from colorama import init, Fore
from dotenv import load_dotenv

# Local imports
from scripts.main import (
    process_single_paper,
    save_paper_to_repository,
)
from scripts.services.endpoints import (
    get_account_verification_requests,
    get_locations_marked_for_geocoding,
    verify_account,
    health_check,
)
from scripts.services.geocoding import geocode_location
from scripts.services.authentication import (
    post_token_request,
    set_session_credentials,
)


# Initialize colorama
init(autoreset=True)

# Define the folder where papers are stored.


def get_paper_files(paper_folder):
    """
    Get list of PDF paper files from the paper folder.

    Returns:
        list: List of PDF filenames in the paper folder
    """
    if not os.path.exists(paper_folder):
        print(f"{Fore.YELLOW}Warning: Paper folder '{paper_folder}' does not exist.")
        return []

    files = [
        f
        for f in os.listdir(paper_folder)
        if os.path.isfile(os.path.join(paper_folder, f)) and f.lower().endswith(".pdf")
    ]

    if not files:
        print(f"{Fore.YELLOW}Paper folder '{paper_folder}' contains no PDF files.")

    return files


def geocode_locations(locations_response):
    """
    Geocode locations from the API response.

    Args:
        locations_response: API response containing locations to geocode
    """
    locations = locations_response.json()
    if not locations:
        print(f"{Fore.YELLOW}No locations found for geocoding.")
        return

    progress_bar = tqdm(locations, desc="Geocoding locations", ncols=70)
    for location in progress_bar:
        try:
            geocode_location(location)
        except Exception as e:
            print(
                f"{Fore.RED}Error geocoding location '{location['location']}': {str(e)}"
            )


def extract_papers_and_metadata():
    """Process each paper sequentially with a clean progress bar interface."""
    print(f"{Fore.CYAN}Starting paper processing...")

    papers = get_paper_files("papers")

    if not papers:
        print(f"{Fore.YELLOW}No papers found in the folder.\n")
        return

    # Initialize counters for summary
    processed = 0
    failed = 0
    results = []

    # Create progress bar
    progress_bar = tqdm(papers, desc="Processing papers", ncols=70)
    paper_folder = "papers"  # Define the folder containing the papers
    # Process each paper without printing details for each one
    for paper in progress_bar:
        paper_path = os.path.join(paper_folder, paper)
        progress_bar.set_description(f"Processing {paper}")

        try:
            # Extract data and save to repository
            metadata, locations = process_single_paper(paper_path)
            save_paper_to_repository(metadata, locations)
            processed += 1
        except Exception as e:
            failed += 1
            results.append((paper, f"Error: {str(e)}"))

    # Print summary after all papers are processed
    print(f"\n{Fore.CYAN}Processing complete: {processed} successful, {failed} failed")

    # Only show details if explicitly requested
    if failed > 0 and input("Show error details? (y/n): ").lower() == "y":
        for paper, result in results:
            if isinstance(result, str) and result.startswith("Error"):
                print(f"{Fore.RED}{paper}: {result}")

    print("")


def display_menu():
    """Display the main menu of the application."""
    print(f"{Fore.CYAN}----------------------------------------------")
    print(f"{Fore.CYAN}         Paper Extraction Terminal          ")
    print(f"{Fore.CYAN}----------------------------------------------\n")

    print("Choose an action by entering the corresponding number:")
    print(" 1: Process papers (extract locations and metadata)")
    print(" 2: Geocoding menu")
    print(" 3: Verify new accounts")
    print(" 0: Exit\n")


def handle_account_verification():
    """Handle the account verification process."""
    try:
        accounts = get_account_verification_requests()

        if not accounts:
            print(f"{Fore.YELLOW}No accounts pending verification.")
            return

        print(f"{Fore.YELLOW}\nAccounts Pending Verification:")
        print(f"{Fore.YELLOW}{'-' * 80}")

        for i, account in enumerate(accounts, 1):
            print(f"{Fore.CYAN}Account #{i}: {account[0]}")

        verify_account_id = (
            int(input("Enter the account Number to verify (0 to cancel): ")) - 1
        )

        if verify_account_id < 0:
            return

        if verify_account_id >= len(accounts):
            print(f"{Fore.RED}Invalid account number.")
            return

        account_id = accounts[verify_account_id][1]
        print(f"Verifying account with ID: {accounts[verify_account_id][0]}")

        if input("Type 'yes' to confirm: ").lower() == "yes":
            response = verify_account(account_id)
            if response.status_code == 200:
                print(f"{Fore.GREEN}Account verified successfully.")
            else:
                print(
                    f"{Fore.RED}Failed to verify account. Status: {response.status_code}"
                )
    except Exception as e:
        print(f"{Fore.RED}Error during account verification: {str(e)}")


def handle_geocoding():
    """Handle the geocoding process."""
    try:
        result = get_locations_marked_for_geocoding()
        locations = result.json()

        print(f"{Fore.YELLOW}\nLocations Marked for Geocoding:")
        print(f"{Fore.YELLOW}{'-' * 80}")

        if not locations:
            print("No locations found for geocoding.")
            return

        for i, loc in enumerate(locations, 1):
            status_color = (
                Fore.RED if "failed" in loc["geocoded_status"].lower() else Fore.GREEN
            )
            print(f"{Fore.CYAN}Location #{i}:")
            print(f"  {Fore.WHITE}ID: {loc['id']}")
            print(f"  {Fore.WHITE}Paper: {loc['paper_name']}")
            print(f"  {Fore.WHITE}Location: {loc['location']}")
            print(f"  {Fore.WHITE}Status: {status_color}{loc['geocoded_status']}")
            print(f"{Fore.YELLOW}{'-' * 80}")

        print(
            "Type 'yes' to start geocoding all of these locations (or any other key to cancel)"
        )
        if input().lower() == "yes":
            geocode_locations(result)
    except Exception as e:
        print(f"{Fore.RED}Error loading geocoding data: {str(e)}")


def check_system_health():
    """
    Check if the API server is accessible before proceeding.

    Returns:
        bool: True if the API is accessible, False otherwise
    """
    print(f"{Fore.CYAN}Checking connection to API server...")

    # Load only the API URL from the .env file
    load_dotenv()

    try:
        response = health_check()
        if response.status_code == 200:
            print(f"{Fore.GREEN}API server is accessible ✓")
            return True
        else:
            print(f"{Fore.RED}API server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error connecting to API server: {str(e)}")
        return False


def login():
    """Handle user login and store credentials."""
    print(f"{Fore.CYAN}----------------------------------------------")
    print(f"{Fore.CYAN}                   Login                     ")
    print(f"{Fore.CYAN}----------------------------------------------\n")

    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    # Store credentials in the session (not in environment variables)
    # Make sure we're storing clean values without quotes
    set_session_credentials(username.strip("'\""), password.strip("'\""))

    # Test credentials
    try:
        token = post_token_request()
        if token:
            print(f"{Fore.GREEN}Login successful!")
            return True
        else:
            print(f"{Fore.RED}Login failed. Invalid credentials.")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error during login: {str(e)}")
        return False


def main():
    """Main entry point for the application."""
    # Load minimal environment variables for API URLs
    load_dotenv()

    # Perform health check first
    if not check_system_health():
        print(f"{Fore.RED}Cannot proceed without a connection to the API server.")
        print(
            f"{Fore.YELLOW}Please check your network connection and API server status."
        )
        if input("Try again? (y/n): ").lower() != "y":
            print(f"{Fore.CYAN}Exiting program. Goodbye!")
            sys.exit(1)
        else:
            if not check_system_health():
                print(f"{Fore.RED}Still unable to connect. Exiting program.")
                sys.exit(1)

    # Require login every time the application starts
    login_successful = False
    while not login_successful:
        login_successful = login()
        if not login_successful:
            if input("Try again? (y/n): ").lower() != "y":
                print(f"{Fore.CYAN}Exiting program. Goodbye!")
                sys.exit(1)

    while True:
        display_menu()
        choice = input("Enter your choice (0-3): ").strip()
        print("")

        if choice == "0":
            print(f"{Fore.CYAN}Exiting program. Goodbye!")
            sys.exit(0)
        elif choice == "1":
            extract_papers_and_metadata()
        elif choice == "2":
            handle_geocoding()
        elif choice == "3":
            handle_account_verification()
        else:
            print(f"{Fore.RED}Invalid choice. Please enter a number between 0 and 3.")

        print("\nPress Enter to continue...")
        input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Program interrupted. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {str(e)}")
        sys.exit(1)
