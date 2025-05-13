import os
import json
import time
from dotenv import load_dotenv
import openai
from pydantic import BaseModel
from tqdm import tqdm
from interface import get_paper_files
from scripts.main import extract_locations

# Load environment variables from .env file at the start
load_dotenv()

# --- Constants ---
BASE_FOLDER = "./benchmark_papers"
PAPER_FOLDER = os.path.join(BASE_FOLDER, "papers")
EXTRACTED_LOCATIONS_FILE = os.path.join(BASE_FOLDER, "extracted_locations.json")
BENCHMARK_RESULTS_FILE = os.path.join(BASE_FOLDER, "benchmark_results.json")
GROUND_TRUTH_FILENAME = os.path.join(BASE_FOLDER, "ground_truth.json")


class TruthTable(BaseModel):
    True_Positive: int
    False_Positive: int
    False_Negative: int


# --- Functions ---


def load_configuration():
    """Loads benchmark configuration from environment variables."""
    try:
        config = {
            "PERCENTILE_CUTOFF": int(os.getenv("PERCENTILE_CUTOFF", 70)),
            "MAX_TOKENS_PER_PART": int(os.getenv("MAX_TOKENS_PER_PART", 10000)),
            "OVERLAP_PERCENTAGE": float(os.getenv("OVERLAP_PERCENTAGE", 0.15)),
            "SYSTEM_PROMPT": os.getenv(
                "SYSTEM_PROMPT", "Default system prompt if not set"
            ),
            "APPEND_ABSTRACT_TO_CONTEXT": os.getenv(
                "APPEND_ABSTRACT_TO_CONTEXT", "False"
            ).lower()
            in ["true", "1", "t", "y", "yes"],
            "LLM_API_URL_BENCHMARK_EVALUATOR": (
                os.getenv("LLM_API_URL_BENCHMARK_EVALUATOR")
            ),
            "LLM_API_KEY_BENCHMARK_EVALUATOR": (
                os.getenv("LLM_API_KEY_BENCHMARK_EVALUATOR")
            ),
            "LLM_MODEL_BENCHMARK_EVALUATOR": (
                os.getenv("LLM_MODEL_BENCHMARK_EVALUATOR")
            ),
            # Add other relevant config if needed for the extraction process itself
        }
        # Ensure required evaluator variables are present if evaluation is intended
        if not all(
            [
                config["LLM_API_URL_BENCHMARK_EVALUATOR"],
                config["LLM_API_KEY_BENCHMARK_EVALUATOR"],
                config["LLM_MODEL_BENCHMARK_EVALUATOR"],
            ]
        ):
            print(
                "Warning: LLM Evaluator environment variables (URL, KEY, MODEL) are not fully set. Evaluation step might fail."
            )

        return config
    except ValueError as e:
        print(
            f"Error processing environment variable: {e}. Please check your .env file."
        )
        exit(1)  # Exit if configuration is invalid


def benchmark_single_paper(paper_path):
    """Benchmarks a single paper file for location extraction."""
    start_time = time.time()
    try:
        # Assuming extract_locations uses environment variables or has defaults
        # Pass necessary config if extract_locations requires it explicitly
        locations_data, total_tokens = extract_locations(paper_path)
        end_time = time.time()
        duration = end_time - start_time
        return {
            "success": True,
            "data": {
                "locations": locations_data.location_names,
                "importance_scores": locations_data.location_importance_scores,
                "extraction_time_seconds": duration,
                "approx_input_token_count": total_tokens,
            },
        }
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"\nError processing {os.path.basename(paper_path)}: {e}")
        return {
            "success": False,
            "data": {
                "error": str(e),
                "extraction_time_seconds": duration,
                # Include other fields as None or default if needed downstream
                "locations": [],
                "importance_scores": [],
                "approx_input_token_count": None,
            },
        }


def generate_benchmark_input(papers_list, paper_folder_path):
    """Runs the location extraction benchmark over a list of paper files."""
    results = []
    if not papers_list:
        print("No papers found to benchmark.")
        return results

    progress_bar = tqdm(papers_list, desc="Extracting Locations", ncols=70)
    for paper_name in progress_bar:
        paper_full_path = os.path.join(paper_folder_path, paper_name)
        progress_bar.set_description(f"Processing {paper_name}")

        result = benchmark_single_paper(paper_full_path)
        # Always add paper name, regardless of success/failure
        result_data = result["data"]
        result_data["paper_name"] = paper_name
        results.append(result_data)  # Append the inner data dict

    return results


def save_extracted_locations(results_list, config, output_file):
    """Saves the extracted location results and configuration to a JSON file."""
    if not results_list:
        print("\nNo extraction results to save.")
        return

    final_output = {"configuration": config, "results": results_list}
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
        print(f"\nExtraction results saved to {output_file}")
    except Exception as e:
        print(f"\nError saving extraction results to {output_file}: {e}")


def evaluate_predictions(evaluation_set, config):
    """Evaluates predictions against ground truth using an LLM and saves results."""

    output_filename = BENCHMARK_RESULTS_FILE
    model = config.get("LLM_MODEL_BENCHMARK_EVALUATOR")
    base_url = config.get("LLM_API_URL_BENCHMARK_EVALUATOR")
    api_key = config.get("LLM_API_KEY_BENCHMARK_EVALUATOR")

    if not all([model, base_url, api_key]):
        print(
            "Error: Missing LLM Evaluator configuration. Cannot proceed with evaluation."
        )
        return []  # Return empty list or handle error as appropriate

    try:
        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
    except Exception as e:
        print(f"Error initializing OpenAI client for evaluation: {e}")
        return []

    # Load existing results to potentially append or overwrite based on logic
    # For simplicity, this version overwrites/creates the file each run.
    # If appending is needed, load logic similar to the original can be added.
    all_evaluation_results = []

    progress_bar = tqdm(evaluation_set.items(), desc="Evaluating Papers", ncols=70)
    for file_name, details in progress_bar:
        progress_bar.set_description(f"Evaluating {file_name}")

        ground_truth = details["ground_truth"]
        predicted_truth = details.get("predicted_values", [])

        try:
            # Get LLM evaluation
            completion = client.beta.chat.completions.parse(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Your job is to create a metadata based on a ground truth and a predicted truth. "
                            "You will get two lists of locations and if the names of the locations point to the same location, "
                            "you consider it a true positive. If they are not related, consider it a false positive. If something is missing in the predicted list compared to the ground truth, "
                            "consider it a false negative. Do not consider just pointing to the same country as a true positive unless the specific location matches. Respond in the truth table format in JSON.\n"
                            f"The JSON object must use the schema: {json.dumps(TruthTable.model_json_schema(), indent=2)}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Ground truth: {ground_truth}, Predicted truth: {predicted_truth}",
                    },
                ],
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
            )

            # Parse response
            evaluation_metrics = json.loads(completion.choices[0].message.content)

            # Create result dictionary including metadata
            response_dict = {
                "pdf_name": file_name,
                "ground_truth": ground_truth,
                "predicted_truth": predicted_truth,
                "true_positive": evaluation_metrics.get("True_Positive"),
                "false_positive": evaluation_metrics.get("False_Positive"),
                "false_negative": evaluation_metrics.get("False_Negative"),
                # Add metadata from the extraction step
                "extraction_time_seconds": details.get("extraction_time_seconds"),
                "approx_input_token_count": details.get("approx_input_token_count"),
                "importance_scores": details.get(
                    "importance_scores"
                ),  # Include scores if needed
            }

            all_evaluation_results.append(response_dict)

        except openai.APIError as e:
            print(f"\nOpenAI API error during evaluation for {file_name}: {e}")
            # Optionally add a placeholder error entry to all_evaluation_results
        except json.JSONDecodeError as e:
            print(f"\nError parsing LLM JSON response for {file_name}: {e}")
            # Optionally add a placeholder error entry
        except Exception as e:
            print(f"\nUnexpected error during evaluation for {file_name}: {e}")
            # Optionally add a placeholder error entry

    # Save all results at the end
    if all_evaluation_results:
        try:
            # Include configuration in the final benchmark results file as well
            final_output = {"configuration": config, "results": all_evaluation_results}
            with open(output_filename, "w", encoding="utf-8") as outfile:
                json.dump(final_output, outfile, indent=2, ensure_ascii=False)
            print(f"\nEvaluation results saved to {output_filename}")
        except Exception as e:
            print(f"\nError saving final evaluation results to {output_filename}: {e}")
    else:
        print("\nNo evaluation results were generated.")

    return all_evaluation_results


# --- Main Execution ---


def main():
    """Main function to run the benchmarking and evaluation process."""
    # 1. Load Configuration
    benchmark_config = load_configuration()
    print("Configuration loaded:")
    for key, value in benchmark_config.items():
        print(f"- {key}: {value}")
    print("-" * 20)

    # 2. Get Paper Files
    papers = get_paper_files(PAPER_FOLDER)
    if not papers:
        print(f"No PDF papers found in {PAPER_FOLDER}. Exiting.")
        return

    # 3. Run Location Extraction Benchmark
    print("Starting location extraction...")
    extracted_results_list = generate_benchmark_input(papers, PAPER_FOLDER)

    # 4. Save Extracted Locations Results
    save_extracted_locations(
        extracted_results_list, benchmark_config, EXTRACTED_LOCATIONS_FILE
    )

    # 5. Load Ground Truth Data
    ground_truth_file = GROUND_TRUTH_FILENAME
    ground_truth_data = {}
    try:
        with open(ground_truth_file, "r", encoding="utf-8") as f:
            ground_truth_data = json.load(f)
        print(f"Loaded ground truth from {ground_truth_file}")
    except FileNotFoundError:
        print(
            f"Error: Ground truth file not found at {ground_truth_file}. Cannot perform evaluation."
        )
        return
    except json.JSONDecodeError:
        print(
            f"Error: Could not decode JSON from {ground_truth_file}. Cannot perform evaluation."
        )
        return

    # 6. Prepare Data for Evaluation
    print("\nPreparing data for evaluation...")
    evaluation_set = {}
    papers_skipped_evaluation = 0
    for result in extracted_results_list:
        paper_name = result.get("paper_name")
        if not paper_name:
            print(
                "Warning: Skipping result with missing paper name during evaluation prep."
            )
            papers_skipped_evaluation += 1
            continue

        if "error" in result and result["error"]:
            print(
                f"Skipping evaluation for {paper_name} due to extraction error: {result['error']}"
            )
            papers_skipped_evaluation += 1
            continue

        predicted_locations = result.get("locations", [])
        ground_truth_str = ground_truth_data.get(paper_name)
        if ground_truth_str is None:
            print(
                f"Warning: Ground truth not found for {paper_name}. Skipping evaluation."
            )
            papers_skipped_evaluation += 1
            continue

        evaluation_set[paper_name] = {
            "ground_truth": ground_truth_str,
            "predicted_values": predicted_locations,
            "extraction_time_seconds": result.get("extraction_time_seconds"),
            "approx_input_token_count": result.get("approx_input_token_count"),
            "importance_scores": result.get("importance_scores"),
        }

    if not evaluation_set:
        print("\nNo papers eligible for evaluation after filtering.")
        if papers_skipped_evaluation > 0:
            print(
                f"({papers_skipped_evaluation} papers were skipped due to errors or missing ground truth)."
            )
        print("\nBenchmarking and evaluation process finished (no papers evaluated).")
        return

    else:
        print(f"Prepared {len(evaluation_set)} papers for evaluation.")
        if papers_skipped_evaluation > 0:
            print(
                f"({papers_skipped_evaluation} papers were skipped due to errors or missing ground truth)."
            )

        # 7. Evaluate Predictions
        print("\nStarting evaluation using LLM...")
        evaluation_results = evaluate_predictions(evaluation_set, benchmark_config)

        # 8. Calculate and Append Summary Totals to JSON if evaluation occurred
        if evaluation_results:
            total_tp = 0
            total_fp = 0
            total_fn = 0
            total_time = 0.0
            total_tokens = 0
            evaluated_papers_count = len(evaluation_results)

            for result in evaluation_results:
                total_tp += result.get("true_positive", 0) or 0
                total_fp += result.get("false_positive", 0) or 0
                total_fn += result.get("false_negative", 0) or 0
                total_time += result.get("extraction_time_seconds", 0.0) or 0.0
                total_tokens += result.get("approx_input_token_count", 0) or 0

            summary = {
                "total_papers_evaluated": evaluated_papers_count,
                "total_true_positives": total_tp,
                "total_false_positives": total_fp,
                "total_false_negatives": total_fn,
                "total_extraction_time_seconds": round(total_time, 2),
                "total_approx_input_tokens": total_tokens,
            }
            if evaluated_papers_count > 0:
                summary["average_extraction_time_per_paper_seconds"] = round(
                    total_time / evaluated_papers_count, 2
                )
                summary["average_approx_input_tokens_per_paper"] = round(
                    total_tokens / evaluated_papers_count
                )

            # Load the existing benchmark results, add the summary, and save again
            try:
                with open(BENCHMARK_RESULTS_FILE, "r", encoding="utf-8") as f:
                    benchmark_data = json.load(f)

                benchmark_data["summary"] = summary  # Add the summary block

                with open(BENCHMARK_RESULTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
                print(f"\nBenchmark summary appended to {BENCHMARK_RESULTS_FILE}")

            except FileNotFoundError:
                print(
                    f"\nError: {BENCHMARK_RESULTS_FILE} not found. Cannot append summary."
                )
            except json.JSONDecodeError:
                print(
                    f"\nError: Could not decode JSON from {BENCHMARK_RESULTS_FILE}. Cannot append summary."
                )
            except Exception as e:
                print(f"\nError updating {BENCHMARK_RESULTS_FILE} with summary: {e}")

        else:
            print("\nNo papers were successfully evaluated, summary not generated.")

    print("\nBenchmarking and evaluation process finished.")


if __name__ == "__main__":
    main()
