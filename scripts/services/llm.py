import json
import math
import os
import sys
import openai

from scripts.services.schemas import Locations, Metadata


# Add this to fix import path issues when running directly as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from dotenv import load_dotenv

PERCENTILE_CUTOFF = os.environ.get("PERCENTILE_CUTOFF", 70)


def location_extractor(text: str):
    load_dotenv()
    base_url = os.environ.get("LLM_API_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL")
    system_prompt = os.environ.get("SYSTEM_PROMPT")

    client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    completion = client.beta.chat.completions.parse(
        messages=[
            {
                "role": "system",
                "content": system_prompt
                + f" The JSON object must use the schema: {json.dumps(Locations.model_json_schema(), indent=2)}",
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        model=model,
        temperature=0,
        max_tokens=5000,
        response_format={"type": "json_object"},
    )

    event = completion.choices[0]
    data = json.loads(event.message.content)

    # Sort locations by importance score (descending) and store in a list

    locations = data.get(
        "locations", []
    )  # Use .get for safety if 'locations' might be missing

    if not locations:
        top_locations = []
        score_threshold = None
    else:
        # 1. Extract all importance scores
        all_scores = [loc["importance_score"] for loc in locations]

        if not all_scores:
            # This case should ideally not be hit if locations is not empty, but for safety:
            top_locations = []
            score_threshold = None
        elif len(all_scores) == 1:
            # If only one location, it's trivially above any percentile threshold
            score_threshold = all_scores[0]
            top_locations = locations  # Keep the single location
        else:
            # 2. Sort scores in ascending order to calculate percentile
            sorted_scores = sorted(all_scores)
            n = len(sorted_scores)

            # 3. Calculate the 70th percentile score using linear interpolation
            percentile = int(PERCENTILE_CUTOFF)
            # Calculate the index (0-based)
            index_float = (percentile / 100.0) * (n - 1)

            # Find integer and fractional parts of the index
            k = math.floor(index_float)
            f = index_float - k

            # Ensure k doesn't go out of bounds if index_float is exactly n-1
            if k >= n - 1:
                score_threshold = sorted_scores[n - 1]  # The highest score
            else:
                # Linear interpolation: value = lower_val + fraction * (upper_val - lower_val)
                score_threshold = sorted_scores[k] + f * (
                    sorted_scores[k + 1] - sorted_scores[k]
                )

            # 4. Filter locations keeping those with score >= threshold
            #    Also sort the final list by score descending for clarity
            if score_threshold <= 5:
                score_threshold = 5
            top_locations = sorted(
                [
                    loc
                    for loc in locations
                    if loc["importance_score"] >= score_threshold
                ],
                key=lambda x: x["importance_score"],
                reverse=True,
            )

    return top_locations


def metadata_extractor(first_page):
    load_dotenv()
    base_url = os.environ.get("LLM_API_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL_METADATA")
    client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    completion = client.beta.chat.completions.parse(
        messages=[
            {
                "role": "system",
                "content": "Your job is to extract the first page of a geological research paper and extract its metadata. Return the metadata in JSON with the given format.\n "
                + f" The JSON object must use the schema: {json.dumps(Metadata.model_json_schema(), indent=2)}",
            },
            {
                "role": "user",
                "content": first_page,
            },
        ],
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
    )

    event = completion.choices[0]
    data = json.loads(event.message.content)
    return data
