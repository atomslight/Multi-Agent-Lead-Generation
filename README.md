# Lead-Apify 🕵️‍♂️
> AI-Powered B2B Lead Generation and Web Automation Research Agents

## 📖 Overview
Lead-Apify is an intelligent automation platform that takes an Ideal Customer Profile (ICP) and automatically researches the best lead sources on the web. By combining autonomous AI agents with powerful web scraping tools (Apify and Playwright), it transforms vague search concepts into actionable, structured B2B lead reports without manual intervention.

## ✨ Features
* **Automated Lead Research:** AI agents analyze your Ideal Customer Profile and recommend the best databases and websites for prospecting.
* **Apify Integration:** Automatically searches the public Apify Store for the best web-scraping actors and executes them to extract lead data via REST API.
* **Robust Browser Automation:** Utilizes Playwright via the Model Context Protocol (MCP) to safely navigate, read, and summarize webpages.
* **Privacy-First Web Search:** Integrates with a local SearXNG instance for reliable, bot-detection-resistant web searches.
* **Intelligent Guardrails:** Self-correcting AI tasks ensure that outputs meet strict formatting requirements before moving to the next pipeline step.

## 🛠 Tech Stack
* **[Python 3.13+](https://www.python.org/):** The core programming language powering the application logic.
* **[CrewAI](https://www.crewai.com/):** Orchestrates our role-playing AI agents, assigning them specific tasks like web research and data analysis.
* **[Apify](https://apify.com/):** The web scraping and automation platform used to extract structured data from targeted lead sources.
* **[Playwright MCP](https://github.com/playwright-community/playwright-mcp):** Provides a standardized interface (Model Context Protocol) for our AI agents to control a real web browser.
* **[SearXNG](https://docs.searxng.org/):** A self-hosted metasearch engine used to fetch clean, JSON-formatted search results without hitting CAPTCHAs.
* **Local/Cloud LLMs (Ollama):** Powers the decision-making capabilities of our agents (defaulting to `gemma4:31b-cloud`).

## 📋 Prerequisites
Before you start, ensure you have the following installed on your machine:
* **Python v3.13 or higher**
* **Node.js v18 or higher** (required to run the Playwright MCP server via `npx`)
* **uv** (recommended) or **pip** for Python package management.
* **Docker** (optional, but highly recommended if you want to run the local SearXNG search engine).
* **Apify API Token**: Sign up at [Apify](https://apify.com/) and generate a personal API token.
* **Ollama (or compatible LLM API)**: Ensure you have a local or accessible LLM endpoint (default expects `http://localhost:11434/v1`).

## 🚀 Local Development (Step-by-Step)

### 1. Clone the Repository
Open your terminal and run:
```bash
git clone https://github.com/yourusername/lead-apify.git
cd lead-apify
```

### 2. Install Dependencies
This project uses `uv` for lightning-fast dependency management (as indicated by the `uv.lock` file).
```bash
# Install Python dependencies using uv
uv sync

# Alternatively, if you are using standard pip:
pip install .
```

### 3. Environment Variables
You need to provide API keys for the services to work. We store these securely in a `.env` file.
```bash
# Copy the example environment file
cp .env.example .env
```
Open the `.env` file in your favorite text editor and add your keys:
```env
# Required for Apify integration
APIFY_API_TOKEN=your_apify_api_token_here

# Optional: If running a custom SearXNG instance
SEARXNG_BASE_URL=http://localhost:8080
```
*Note: To get your Apify token, log into your Apify Console, go to Settings -> Integrations, and copy your Personal API token.*

### 4. Run the Application
The project includes two primary agentic workflows.

**To run the B2B Lead Generator (Apify Agent):**
```bash
python apify.py
```

**To run the Browser Research Automation (Playwright/SearXNG Agent):**
Ensure your LLM is running locally, then execute:
```bash
python playwright_automation.py
```

*(Note: There is no build step for production as this is a suite of Python scripts designed to be executed directly or scheduled via cron/CI).*

## 🧠 How It Works (Architecture)
1. **The Request:** You provide a prompt describing your Ideal Customer Profile (e.g., "B2B SAAS leads in healthcare").
2. **The Planner:** The AI "Researcher" agent analyzes this request and queries the Apify Store (via REST API) to find the perfect web scraping tool for the job.
3. **Execution:** The agent selects the best tool, formats the necessary input, and triggers the Apify run in the cloud.
4. **Alternative Path (Browser Agent):** If running the browser automation script, the agent uses a self-hosted SearXNG search engine to find 3 relevant URLs, then commands a headless Playwright browser to visit each page, read the text, and extract summaries.
5. **The Output:** Finally, the agents synthesize the raw scraped data or web summaries into a clean, structured intelligence report.

## 📁 Folder Structure
```text
lead-apify/
├── apify.py                    # Main CrewAI agent logic for Apify store search & execution
├── playwright_automation.py    # Alternative AI automation using Playwright MCP & SearXNG
├── main.py                     # Entry point for basic testing
├── pyproject.toml              # Python project metadata and dependency declarations
├── uv.lock                     # Locked dependency tree for reproducible builds
├── mcp_output/                 # Auto-generated directory where browser snapshots are saved
└── README.md                   # This documentation file!
```