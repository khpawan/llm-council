"""PDF export functionality for conversations."""

import re
from typing import Dict, Any, List
from weasyprint import HTML, CSS
from io import BytesIO
import markdown as md
from .storage import get_conversation
from .council import calculate_aggregate_rankings, parse_ranking_from_text


async def generate_conversation_pdf(conversation_id: str) -> bytes:
    """
    Generate a PDF export of a conversation.

    Args:
        conversation_id: The conversation ID to export

    Returns:
        PDF file as bytes
    """
    # Load conversation from storage
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    # Process messages and recompute metadata for assistant messages
    messages_with_metadata = []
    for msg in conversation['messages']:
        if msg['role'] == 'assistant':
            # Recompute metadata for this assistant message
            metadata = recompute_metadata_for_message(msg.get('stage1', []), msg.get('stage2', []))
            messages_with_metadata.append({
                **msg,
                'metadata': metadata
            })
        else:
            messages_with_metadata.append(msg)

    # Build HTML content
    html_content = build_html_content(conversation, messages_with_metadata)

    # Convert HTML to PDF
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(pdf_file)

    return pdf_file.getvalue()


def recompute_metadata_for_message(stage1: List[Dict[str, Any]], stage2: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Recompute metadata (label_to_model and aggregate_rankings) for an assistant message.

    Args:
        stage1: Stage 1 results (individual responses)
        stage2: Stage 2 results (rankings)

    Returns:
        Dict with 'label_to_model' and 'aggregate_rankings'
    """
    # Recreate label-to-model mapping using same logic as stage2_collect_rankings
    labels = [chr(65 + i) for i in range(len(stage1))]  # A, B, C, ...
    label_to_model = {f"Response {label}": stage1[i]["model"] for i, label in enumerate(labels)}

    # Ensure stage2 results have parsed_ranking
    stage2_with_parsing = []
    for ranking in stage2:
        if 'parsed_ranking' not in ranking or not ranking['parsed_ranking']:
            # Parse the ranking text
            parsed = parse_ranking_from_text(ranking['ranking'])
            stage2_with_parsing.append({
                **ranking,
                'parsed_ranking': parsed
            })
        else:
            stage2_with_parsing.append(ranking)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_with_parsing, label_to_model)

    return {
        'label_to_model': label_to_model,
        'aggregate_rankings': aggregate_rankings
    }


def markdown_to_html(text: str) -> str:
    """
    Convert markdown text to HTML.

    Args:
        text: Markdown text

    Returns:
        HTML string
    """
    return md.markdown(text, extensions=['fenced_code', 'tables'])


def deanonymize_text(text: str, label_to_model: Dict[str, str]) -> str:
    """
    Replace anonymous labels (Response A, Response B, etc.) with model names in bold.

    Args:
        text: Text containing anonymous labels
        label_to_model: Mapping from labels to model names

    Returns:
        Text with labels replaced by bold model names
    """
    result = text
    for label, model in label_to_model.items():
        # Replace "Response X" with "**ModelName**" (markdown bold)
        result = result.replace(label, f"**{model}**")
    return result


def build_html_content(conversation: Dict[str, Any], messages_with_metadata: List[Dict[str, Any]]) -> str:
    """
    Build complete HTML document for PDF export.

    Args:
        conversation: Conversation data
        messages_with_metadata: Messages with recomputed metadata

    Returns:
        HTML string
    """
    title = conversation.get('title', 'LLM Council Discussion')
    created_at = conversation.get('created_at', '')

    # Start HTML document
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{title}</title>',
        '<style>',
        get_pdf_css(),
        '</style>',
        '</head>',
        '<body>',
        '<div class="header">',
        f'<h1>{title}</h1>',
        f'<p class="timestamp">Created: {created_at}</p>',
        '</div>',
    ]

    # Process messages in pairs (user + assistant)
    for i, msg in enumerate(messages_with_metadata):
        if msg['role'] == 'user':
            html_parts.append('<div class="qa-pair">')
            html_parts.append('<div class="user-question">')
            html_parts.append('<h3>Question:</h3>')
            html_parts.append(f'<div class="user-content">{markdown_to_html(msg["content"])}</div>')
            html_parts.append('</div>')

        elif msg['role'] == 'assistant':
            metadata = msg.get('metadata', {})
            label_to_model = metadata.get('label_to_model', {})
            aggregate_rankings = metadata.get('aggregate_rankings', [])

            # Stage 1: Individual Responses
            if 'stage1' in msg and msg['stage1']:
                html_parts.append('<div class="stage stage1">')
                html_parts.append('<h3>Stage 1: Individual Responses</h3>')
                for response in msg['stage1']:
                    model = response.get('model', 'Unknown')
                    content = response.get('response', '')
                    html_parts.append('<div class="model-response">')
                    html_parts.append(f'<h4>{model}</h4>')
                    html_parts.append(f'<div class="response-content">{markdown_to_html(content)}</div>')
                    html_parts.append('</div>')
                html_parts.append('</div>')

            # Stage 2: Peer Rankings
            if 'stage2' in msg and msg['stage2']:
                html_parts.append('<div class="stage stage2">')
                html_parts.append('<h3>Stage 2: Peer Rankings</h3>')

                # Individual rankings
                for ranking in msg['stage2']:
                    model = ranking.get('model', 'Unknown')
                    ranking_text = ranking.get('ranking', '')
                    parsed_ranking = ranking.get('parsed_ranking', [])

                    # De-anonymize the ranking text
                    deanonymized_text = deanonymize_text(ranking_text, label_to_model)

                    html_parts.append('<div class="ranking">')
                    html_parts.append(f'<h4>{model} Evaluation</h4>')
                    html_parts.append(f'<div class="ranking-content">{markdown_to_html(deanonymized_text)}</div>')

                    # Show extracted ranking
                    if parsed_ranking:
                        html_parts.append('<div class="extracted-ranking">')
                        html_parts.append('<strong>Extracted Ranking:</strong>')
                        html_parts.append('<ol>')
                        for label in parsed_ranking:
                            model_name = label_to_model.get(label, label)
                            html_parts.append(f'<li>{model_name}</li>')
                        html_parts.append('</ol>')
                        html_parts.append('</div>')
                    html_parts.append('</div>')

                # Aggregate rankings table
                if aggregate_rankings:
                    html_parts.append('<div class="aggregate-rankings">')
                    html_parts.append('<h4>Aggregate Rankings</h4>')
                    html_parts.append('<table>')
                    html_parts.append('<tr><th>Rank</th><th>Model</th><th>Avg Score</th><th>Votes</th></tr>')
                    for idx, agg in enumerate(aggregate_rankings, 1):
                        model = agg.get('model', '')
                        avg_rank = agg.get('average_rank', 0)
                        count = agg.get('rankings_count', 0)
                        html_parts.append(f'<tr><td>{idx}</td><td>{model}</td><td>{avg_rank}</td><td>{count}</td></tr>')
                    html_parts.append('</table>')
                    html_parts.append('</div>')

                html_parts.append('</div>')

            # Stage 3: Final Answer
            if 'stage3' in msg and msg['stage3']:
                html_parts.append('<div class="stage stage3">')
                html_parts.append('<h3>Stage 3: Final Council Answer</h3>')
                model = msg['stage3'].get('model', 'Unknown')
                response = msg['stage3'].get('response', '')
                html_parts.append(f'<p class="chairman"><strong>Chairman:</strong> {model}</p>')
                html_parts.append(f'<div class="final-response">{markdown_to_html(response)}</div>')
                html_parts.append('</div>')

            html_parts.append('</div>')  # Close qa-pair

    # Close HTML
    html_parts.append('</body>')
    html_parts.append('</html>')

    return '\n'.join(html_parts)


def get_pdf_css() -> str:
    """
    Return CSS styling for the PDF.

    Returns:
        CSS string
    """
    return '''
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
        }

        .header {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #4a90e2;
        }

        .header h1 {
            font-size: 24pt;
            color: #333;
            margin: 0 0 10px 0;
        }

        .timestamp {
            color: #666;
            font-size: 10pt;
        }

        .qa-pair {
            page-break-inside: avoid;
            margin-bottom: 40px;
        }

        .user-question {
            background: #f0f7ff;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }

        .user-question h3 {
            margin: 0 0 10px 0;
            font-size: 14pt;
            color: #4a90e2;
        }

        .user-content {
            margin: 0;
        }

        .stage {
            margin-bottom: 25px;
        }

        .stage h3 {
            font-size: 16pt;
            color: #333;
            margin: 0 0 15px 0;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }

        .stage1 .model-response {
            margin-bottom: 20px;
            padding: 12px;
            background: #fafafa;
            border-left: 3px solid #4a90e2;
        }

        .stage1 h4 {
            margin: 0 0 10px 0;
            font-size: 12pt;
            color: #4a90e2;
        }

        .response-content {
            margin: 0;
        }

        .stage2 .ranking {
            margin-bottom: 20px;
            padding: 12px;
            background: #fafafa;
            border-left: 3px solid #e9b44c;
        }

        .stage2 h4 {
            margin: 0 0 10px 0;
            font-size: 12pt;
            color: #e9b44c;
        }

        .ranking-content {
            margin: 0 0 10px 0;
        }

        .extracted-ranking {
            margin-top: 10px;
            padding: 8px;
            background: #fff;
            border-radius: 4px;
            font-size: 10pt;
        }

        .extracted-ranking ol {
            margin: 5px 0 0 0;
            padding-left: 20px;
        }

        .aggregate-rankings {
            margin-top: 15px;
            padding: 12px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }

        .aggregate-rankings h4 {
            margin: 0 0 10px 0;
            font-size: 12pt;
        }

        .aggregate-rankings table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10pt;
        }

        .aggregate-rankings th {
            background: #f0f0f0;
            padding: 8px;
            text-align: left;
            border-bottom: 2px solid #ddd;
        }

        .aggregate-rankings td {
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
        }

        .stage3 {
            background: #f0fff0;
            padding: 15px;
            border-radius: 6px;
            border-left: 3px solid #5cb85c;
        }

        .stage3 h3 {
            margin: 0 0 10px 0;
            color: #5cb85c;
        }

        .chairman {
            margin: 0 0 10px 0;
            font-size: 10pt;
            color: #666;
        }

        .final-response {
            margin: 0;
        }

        /* Markdown content styling */
        code {
            background: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
            font-size: 9pt;
        }

        pre {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }

        pre code {
            background: none;
            padding: 0;
        }

        ul, ol {
            margin: 10px 0;
            padding-left: 25px;
        }

        p {
            margin: 10px 0;
        }

        strong {
            font-weight: 600;
        }

        /* Page breaks */
        @page {
            margin: 2cm;
        }
    '''
