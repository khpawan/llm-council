# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize the council:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```


### 4. Provider Configuration (OpenRouter or Azure Foundry)

By default the app uses OpenRouter. To use Azure Foundry/Azure OpenAI-compatible chat completions, set:

```bash
LLM_PROVIDER=azure_foundry
AZURE_FOUNDRY_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_FOUNDRY_API_KEY=<key>
AZURE_FOUNDRY_API_VERSION=2024-10-21

# Use deployment names in COUNCIL_MODELS / CHAIRMAN_MODEL, or map aliases:
AZURE_FOUNDRY_DEPLOYMENT_MAP={"council-1":"gpt-4.1","council-2":"gpt-4.1-mini","chairman":"gpt-4.1"}
```

### 5. Algorithm Configuration

Council flow is configurable via `COUNCIL_ALGORITHM`:

- `peer_review` (default): Stage1 + Stage2 + Stage3
- `consensus_only`: Stage1 + Stage3
- `chairman_only`: direct chairman response

Optional ranking aggregation method for metadata:

```bash
RANK_AGGREGATION_METHOD=average_rank   # or borda
```

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript


## CLI Mode (Markdown outputs)

You can run the council from terminal and write markdown reports (great for blog draft review loops):

```bash
uv run llm-council-cli --prompt "Review this draft for argument quality" --output data/council-runs/review.md

# Run on a markdown file and print final synthesis
uv run llm-council-cli --input-file /path/to/draft.md --algorithm peer_review --print-final
```

Example for writing directly into your knowledge repo:

```bash
uv run llm-council-cli \
  --input-file /Users/pawan/Documents/development/pawan-knowledge/blog/drafts/2026-02-agent-identity-crisis-x-article.md \
  --algorithm peer_review \
  --output /Users/pawan/Documents/development/pawan-knowledge/knowledge/ai-agents/council-review-agent-identity.md
```


## Azure Foundry model recommendations + deployment steps

If you want high-quality council outputs, use a **mixed panel** and keep your strongest model as chairman.

### Recommended deployment pattern

- **Chairman (best reasoning):** your strongest Foundry chat model deployment
- **Council member #1 (strong general):** same strong model or next-best model
- **Council member #2 (cost/speed balance):** a smaller/faster model
- **Council member #3 (diversity):** a different model family if available

A practical starter mix:
- `foundry-chair` → strongest reasoning model available in your Foundry tenant
- `foundry-1` → same as chairman (or second strongest)
- `foundry-2` → strong balanced model (mid-tier)
- `foundry-3` → fast model for diversity/latency

> Tip: Do not run all members on the exact same deployment. Diversity improves council value.

### Step-by-step: deploy models in Azure Foundry

1. Open **Azure AI Foundry** for your project/resource.
2. Go to **Models** (or **Model catalog**), select each model you want.
3. Click **Deploy** and create deployments with clear names, for example:
   - `foundry-chair`
   - `foundry-1`
   - `foundry-2`
   - `foundry-3`
4. Ensure deployments are for **chat completions** and are in a region/quota that can handle parallel calls.
5. Copy your endpoint + key from the resource:
   - `AZURE_FOUNDRY_ENDPOINT` (example: `https://<resource>.openai.azure.com`)
   - `AZURE_FOUNDRY_API_KEY`
6. Add these to your `.env` in this repo:

```bash
LLM_PROVIDER=azure_foundry
AZURE_FOUNDRY_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_FOUNDRY_API_KEY=<your-key>
AZURE_FOUNDRY_API_VERSION=2024-10-21

COUNCIL_MODELS=foundry-1,foundry-2,foundry-3
CHAIRMAN_MODEL=foundry-chair
AZURE_FOUNDRY_DEPLOYMENT_MAP={"foundry-1":"foundry-1","foundry-2":"foundry-2","foundry-3":"foundry-3","foundry-chair":"foundry-chair"}

COUNCIL_ALGORITHM=peer_review
RANK_AGGREGATION_METHOD=average_rank
```

7. Start app and test:

```bash
# backend + frontend
./start.sh

# or one-shot CLI test
uv run llm-council-cli --prompt "Sanity check this council setup" --print-final
```

8. Verify panel behavior:
   - Stage 1 contains responses from all 3 council members
   - Stage 2 rankings are present
   - Stage 3 model equals your chairman deployment

### Throughput and cost guidance

- Start with `COUNCIL_MODELS=3` members and `peer_review`.
- If latency/cost is high, switch to:
  - `COUNCIL_ALGORITHM=consensus_only` (skips Stage 2)
  - or use a faster model for one council seat.
- Use `chairman_only` for quick drafts, then `peer_review` for final quality passes.

### Example: run blog draft through council and write markdown

```bash
uv run llm-council-cli   --input-file /Users/pawan/Documents/development/pawan-knowledge/blog/drafts/2026-02-agent-identity-crisis-x-article.md   --algorithm peer_review   --output /Users/pawan/Documents/development/pawan-knowledge/knowledge/ai-agents/council-review-agent-identity.md   --print-final
```

