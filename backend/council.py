"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model, set_execution_algorithm, reset_execution_algorithm
from .config import get_config


async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    # Query all models in parallel
    responses = await query_models_parallel(get_config()["council_models"], messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    mode: str = "peer_review",
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    mode = (mode or "peer_review").strip().lower()

    if mode == "red_team":
        ranking_prompt = f"""A user asked the following question and several candidate answers were written. You are the RED TEAM reviewer.

Question: {user_query}

Candidate answers:

{responses_text}

Instructions:
1. For each answer, identify concrete failure modes: factual errors, weak assumptions, security risks, ambiguous claims, or missing caveats.
2. Prioritize exploitability and business impact where relevant.
3. Then provide a final ranking from most robust to most fragile.

Format your final ranking exactly like this:

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Do not add extra text after the ranking."""
    elif mode == "audience_split":
        ranking_prompt = f"""A user asked the following question and several candidate answers were written. Evaluate each answer for three audiences:
- Executive leadership
- Security engineering
- Product/operations

Question: {user_query}

Candidate answers:

{responses_text}

Instructions:
1. For each answer, briefly score fit for each audience (high/medium/low) and note why.
2. Then provide one overall ranking for cross-audience usefulness.

Format your final ranking exactly like this:

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Do not add extra text after the ranking."""
    elif mode == "claim_evidence":
        ranking_prompt = f"""A user asked the following question and several candidate answers were written. Evaluate each answer using a claim-evidence lens.

Question: {user_query}

Candidate answers:

{responses_text}

Instructions:
1. For each answer, label major claims as: well-supported, plausible-but-weak, or unsupported.
2. Note where citations/evidence are needed.
3. Then provide a final ranking from strongest evidentiary quality to weakest.

Format your final ranking exactly like this:

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Do not add extra text after the ranking."""
    else:
        ranking_prompt = f"""A user asked the following question, and several candidate answers were written. Please act as a quality reviewer: read each answer, assess accuracy, completeness, and clarity, then rank them.

Question: {user_query}

Candidate answers:

{responses_text}

Instructions:
1. For each answer, note its strengths and weaknesses regarding accuracy, completeness, and clarity.
2. After your assessment, provide a final ranking from best to worst.

Format your final ranking exactly like this (at the end of your response):

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Replace the letters with the actual labels above. Do not add extra text after the ranking."""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(get_config()["council_models"], messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""Several candidate answers and quality reviews have been collected for the following question. Synthesize them into a single, comprehensive, accurate final answer.

Original Question: {user_query}

Candidate Answers:
{stage1_text}

Quality Reviews:
{stage2_text}

Based on the answers and reviews above, provide a clear, well-reasoned final answer to the original question. Consider accuracy, completeness, and areas of agreement:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    chairman_model = get_config()["chairman_model"]
    response = await query_model(chairman_model, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": chairman_model,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Returns average rank by default, or Borda points if configured.
    """
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking["ranking"]
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []

    if get_config()["rank_aggregation_method"] == "borda":
        max_rank = max((len(v) for v in model_positions.values()), default=0)
        for model, positions in model_positions.items():
            if not positions:
                continue
            points = sum(max(max_rank - p + 1, 1) for p in positions)
            aggregate.append({
                "model": model,
                "borda_points": points,
                "rankings_count": len(positions)
            })
        aggregate.sort(key=lambda x: x["borda_points"], reverse=True)
        return aggregate

    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model(get_config()["chairman_model"], messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str, algorithm: str | None = None) -> Tuple[List, List, Dict, Dict]:
    """Run the council process with configurable algorithm."""
    algo = (algorithm or get_config()["council_algorithm"] or "peer_review").strip().lower()
    token = set_execution_algorithm(algo)

    try:
        if algo in ("chairman_only",):
            stage3_result = await stage3_synthesize_final(user_query, [], [])
            metadata = {"algorithm": algo, "label_to_model": {}, "aggregate_rankings": []}
            return [], [], stage3_result, metadata

        stage1_results = await stage1_collect_responses(user_query)

        if not stage1_results:
            return [], [], {
                "model": "error",
                "response": "All models failed to respond. Please try again."
            }, {"algorithm": algo, "label_to_model": {}, "aggregate_rankings": []}

        if algo in ("consensus_only",):
            stage3_result = await stage3_synthesize_final(user_query, stage1_results, [])
            metadata = {"algorithm": algo, "label_to_model": {}, "aggregate_rankings": []}
            return stage1_results, [], stage3_result, metadata

        stage2_mode = "peer_review"
        if algo in ("red_team", "audience_split", "claim_evidence"):
            stage2_mode = algo

        stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, mode=stage2_mode)
        aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

        stage3_result = await stage3_synthesize_final(
            user_query,
            stage1_results,
            stage2_results,
        )

        metadata = {
            "algorithm": algo,
            "label_to_model": label_to_model,
            "aggregate_rankings": aggregate_rankings,
        }

        return stage1_results, stage2_results, stage3_result, metadata
    finally:
        reset_execution_algorithm(token)
