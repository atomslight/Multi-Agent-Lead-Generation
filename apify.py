import os
import time
import requests
from crewai import Agent, Task, Crew, Process,LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()
# ─── TOOL 1: Search Apify Store via REST API ───────────────────────────────

class ApifySearchStoreInput(BaseModel):
    query: str = Field(..., description="Research topic to find relevant Apify actors for")

class ApifySearchStoreTool(BaseTool):
    name: str = "Search Apify Store"
    description: str = (
        "Searches the public Apify Actor Store via REST API and returns "
        "the top actors with their IDs, names, and descriptions."
    )
    args_schema: type[BaseModel] = ApifySearchStoreInput

    def _run(self, query: str) -> str:
        token = os.environ["APIFY_API_TOKEN"]
        resp = requests.get(
            "https://api.apify.com/v2/store",
            params={"search": query, "limit": 20},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])
        if not items:
            return "No actors found for that query."

        lines = []
        for actor in items:
                actor_id = f"{actor['username']}/{actor['name']}"
                title = actor.get("title", actor["name"])
                desc = actor.get("description", "No description")
                runs = actor.get("stats", {}).get("totalRuns", 0)
                rating = actor.get("actorReviewRating")
                review_count = actor.get("actorReviewCount", 0)

                rating_str = f"{rating} ({review_count} reviews)" if rating else "No rating yet"

                lines.append(
                    f"ID: {actor_id}\nTitle: {title}\nDesc: {desc}\n"
                    f"Rating: {rating_str} | Runs: {runs}\n"
                )
        return "\n---\n".join(lines)


# ─── TOOL 2: Run an Apify Actor via REST API ───────────────────────────────

class ApifyRunActorInput(BaseModel):
    actor_id: str = Field(..., description="Apify actor ID, e.g. 'apify/web-scraper'")
    run_input: dict = Field(..., description="JSON input to pass to the actor")

class ApifyRunActorTool(BaseTool):
    name: str = "Run Apify Actor"
    description: str = (
        "Runs a specific Apify actor by ID with the given input, "
        "waits for it to finish, and returns the output results."
    )
    args_schema: type[BaseModel] = ApifyRunActorInput

    def _run(self, actor_id: str, run_input: dict) -> str:
        token = os.environ["APIFY_API_TOKEN"]
        headers = {"Authorization": f"Bearer {token}"}
        # Apify's REST API needs '~' instead of '/' in the actor ID
        api_actor_id = actor_id.replace("/", "~")

        run_resp = requests.post(
            f"https://api.apify.com/v2/acts/{api_actor_id}/runs",
            json=run_input,
            headers=headers,
            timeout=30,
        )
        run_resp.raise_for_status()
        run_id = run_resp.json().get("data", {}).get("id")
        if not run_id:
            return f"Failed to start actor '{actor_id}': {run_resp.text}"

        # ── Poll for completion ────────────────────────────────────────────
        status = None                          # fix: always defined before use
        terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        last_status_resp = None

        for attempt in range(30):
            time.sleep(5)
            try:
                last_status_resp = requests.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    headers=headers,
                    timeout=15,
                )
                last_status_resp.raise_for_status()
                status = last_status_resp.json().get("data", {}).get("status")
            except requests.RequestException as e:
                print(f"[poll attempt {attempt+1}] API error: {e}")
                continue

            if status in terminal:
                break
        else:
            # Loop exhausted without hitting a terminal state
            return (
                f"Actor '{actor_id}' did not finish within 150 s. "
                f"Last known status: {status!r}. Check Apify console for run ID: {run_id}"
            )

        if status != "SUCCEEDED":
            return f"Actor '{actor_id}' ended with status: {status!r}. Run ID: {run_id}"

        # ── Fetch results ──────────────────────────────────────────────────
        dataset_id = last_status_resp.json()["data"]["defaultDatasetId"]
        items_resp = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"limit": 10},
            headers=headers,
            timeout=15,
        )
        items_resp.raise_for_status()
        return str(items_resp.json())


# ─── AGENT ─────────────────────────────────────────────────────────────────

researcher = Agent(
    role="B2B Lead Source Research Specialist",
    goal=(
        "Identify the best online sources for finding companies and decision makers "
        "matching the given ICP. Recommend the most suitable Apify actors for each "
        "source, run the best actor when appropriate, and produce a structured report."
    ),
    backstory=(
        "You are an outbound sales research expert specializing in B2B lead generation. "
        "You understand ideal customer profiles (ICPs), where companies can be found, "
        "and which Apify actors provide the highest quality data. You always recommend "
        "the best lead sources before selecting scraping actors."
    ),
    tools=[ApifySearchStoreTool(), ApifyRunActorTool()],
    llm=LLM(
        model="openai/gemma4:31b-cloud",
        base_url="http://localhost:11434/v1"
    ),
    verbose=True,
)

# ─── TASK ──────────────────────────────────────────────────────────────────

research_task = Task(
    description=(
        "The user wants to find companies matching this ICP:\n\n"
        "{topic}\n\n"

        "Perform the following:\n"

        "1. Analyze the ICP and identify the best websites or databases where these "
        "companies and decision makers can be found.\n"

        "2. Explain why each source is suitable for this ICP.\n"

        "3. Use 'Search Apify Store' to find actors for each recommended source.\n"

        "4. Rank the actors based on:\n"
        "   - Relevance to the ICP\n"
        "   - Popularity (run count)\n"
        "   - Star count\n"
        "   - Maintenance quality\n"
        "   - Data quality\n"

        "5. Select the single best actor for each source.\n"

        "6. Run the most relevant actor using sensible input for the ICP.\n"

        "7. Compile a structured report containing:\n"
        "   - Recommended lead sources\n"
        "   - Why each source was chosen\n"
        "   - Recommended Apify actor\n"
        "   - Why the actor was selected\n"
        "   - Summary of the collected data\n"
        "   - Any limitations or recommendations"
    ),
    expected_output=(
        "A structured lead research report containing:\n"
        "- ICP summary\n"
        "- Recommended lead sources ranked by relevance\n"
        "- Best Apify actor for each source\n"
        "- Selection rationale\n"
        "- Summary of data collected from the executed actor\n"
        "- Limitations and recommendations for future lead generation"
    ),
    agent=researcher,
)

# ─── CREW ──────────────────────────────────────────────────────────────────
crew = Crew(
    agents=[researcher],
    tasks=[research_task],
    process=Process.sequential,
    verbose=True,
)

# Set APIFY_TOKEN in your environment before running:
#   export APIFY_TOKEN=apify_api_xxxxxxxxxxxx
result = crew.kickoff(inputs={"topic": "b2b SAAS leads"})
print(result)
