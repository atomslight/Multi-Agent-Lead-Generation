r"""
Robust version of the browser-research crew.

Key changes vs. the original, and why:

1. FileReadTool added to the agent's toolkit.
   Playwright-MCP writes large results (e.g. a full Google SERP snapshot)
   to disk and returns just a markdown link when the content is too big
   for an inline response. Without a way to open that file, the agent
   gets stuck retrying other tools forever. This fixes that directly.

2. Risky/fragile MCP tools are filtered OUT of the toolkit.
   `browser_run_code_unsafe` is RCE-equivalent (arbitrary JS in the MCP
   server process) and in your log it kept hallucinating filenames.
   `browser_find` has a "text OR regex, not both" schema that small
   models reliably get wrong. Neither is needed for this task.

3. Google is swapped for a self-hosted SearXNG instance for the
   "find 3 URLs" step. Scraping Google's SERP is brittle (consent
   walls, layout drift, huge DOM) and was the source of most of the
   failures. The browser is still used for what it's actually good at:
   opening and reading the 3 resulting pages.
   -> Requires a running SearXNG instance with JSON output enabled
      (disabled by default). SearXNG has no official native-Windows
      support -- Docker Desktop (WSL2 backend) is the supported path.
      Quickest start, cmd.exe-safe (use ${PWD} instead of %cd% if
      you're in PowerShell or a shell instead):
        docker run -d -p 8080:8080 ^
          -v "%cd%\searxng:/etc/searxng" ^
          -e "BASE_URL=http://localhost:8080/" ^
          -e "INSTANCE_NAME=my-instance" ^
          searxng/searxng
      Then edit the generated .\searxng\settings.yml and add "json"
      under search.formats:
        search:
          formats:
            - html
            - json
      Restart the container after saving. Without this the API
      returns 403 even though the web UI works fine.
   -> Even with json enabled, SearXNG's bot detection can 403 the
      default python-requests User-Agent -- the tool below sends a
      browser-like one to avoid that.
   -> Set SEARXNG_BASE_URL if it's not at the localhost:8080 default.
   -> If you'd rather keep Google-via-browser, see the commented
      fallback at the bottom and re-add "google.com" navigation to
      browser_task; just know it'll be less reliable.

4. Guardrails: max_iter / max_execution_time on the agent, max_rpm on
   the crew, and a Task guardrail that checks the browser output
   actually has 3 numbered summaries before letting it flow to the
   analyst -- CrewAI will auto-retry the task if the guardrail fails,
   instead of silently passing garbage downstream.

5. Explicit None-stripping wrapper around MCP tool calls, so a model
   that insists on sending null for unused optional args doesn't get
   rejected by Playwright-MCP's strict schema validation.
"""

import os
import re

import requests
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from crewai_tools import MCPServerAdapter, FileReadTool
from mcp import StdioServerParameters


class SearxSearchTool(BaseTool):
    """Custom tool over a self-hosted SearXNG's JSON API.

    Written by hand instead of using LangChain's SearxSearchWrapper --
    that wrapper has recurring reports of failing against local
    instances, and this is simple enough not to need it.
    """

    name: str = "searxng_search"
    description: str = (
        "Search the web via a local SearXNG instance. Input should be a "
        "plain search query string. Returns up to 8 results as "
        "'title - url' lines, restricted to general web results "
        "(no images/videos/news)."
    )
    base_url: str = os.environ.get("SEARXNG_BASE_URL", "http://localhost:8080")

    def _run(self, query: str) -> str:
        resp = requests.get(
            f"{self.base_url}/search",
            params={
                "q": query,
                "format": "json",
                "categories": "general",  # drop images/videos/news/maps noise
            },
            headers={
                # SearXNG's bot detection blocks the default
                # "python-requests/x.x" User-Agent even when JSON format
                # is enabled -- a browser-like UA avoids that 403.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:8]
        if not results:
            return "No results found."
        lines = [f"{r.get('title', '(no title)')} - {r.get('url', '')}" for r in results]
        return "\n".join(lines)

# --- MCP server ---------------------------------------------------------
# --isolated: fresh profile each run, avoids stale-cookie/consent-dialog
#             selector mismatches from previous sessions.
# --output-dir: pin where large results get written so FileReadTool (and
#             you, debugging) always knows where to look.
OUTPUT_DIR = os.path.abspath("./mcp_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

stdio_params = StdioServerParameters(
    command="npx",
    args=[
        "-y", "@playwright/mcp@latest",
        "--isolated",
        "--output-dir", OUTPUT_DIR,
    ],
    env={**os.environ},
)

# Tool names to exclude: unsafe / schema-fragile for a weaker model.
BLOCKED_TOOLS = {"browser_run_code_unsafe", "browser_find"}


def sanitize_tool(tool):
    """Strip explicit-None kwargs before they hit the MCP server, since
    Playwright-MCP's zod schemas reject an explicit null on optional
    fields (only *omitted* fields are treated as optional)."""
    original_run = tool._run

    def _run(*args, **kwargs):
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return original_run(*args, **clean_kwargs)

    tool._run = _run
    return tool


def constrain_snapshot(tool):
    """Force browser_snapshot to skip box coordinates and cap tree depth,
    regardless of what the model requests. Box coordinates exist for
    click-targeting and are pure token bloat for a read-and-summarize
    task; an unbounded depth on a large page (nav + footer + cookie
    dialog + related-content grid) can dump 15,000+ lines into context
    in one call -- which is what triggered the 'None or empty response
    from LLM call' crash: the local model's context window got blown
    out by a single tool result."""
    original_run = tool._run

    def _run(*args, **kwargs):
        kwargs["boxes"] = False
        kwargs["depth"] = min(kwargs.get("depth") or 8, 8)
        return original_run(*args, **kwargs)

    tool._run = _run
    return tool


with MCPServerAdapter(stdio_params) as mcp_tools:
    browser_tools = []
    for t in mcp_tools:
        if t.name in BLOCKED_TOOLS:
            continue
        t = sanitize_tool(t)
        if t.name == "browser_snapshot":
            t = constrain_snapshot(t)
        browser_tools.append(t)
    browser_tools.append(FileReadTool())  # lets the agent open linked result files

    llm = LLM(model="openai/gemma4:31b-cloud", base_url="http://localhost:11434/v1")
    # NOTE: if you keep seeing malformed tool calls (nulls, invented
    # filenames, wrong args) after these fixes, the model itself is the
    # bottleneck -- confirm it actually supports function/tool calling
    # well and try a stronger one (e.g. qwen2.5:32b, or a hosted model)
    # before debugging further here.
    #
    # NOTE: "Received None or empty response from LLM call" after a big
    # tool result. The "-cloud" suffix means this model runs on Ollama's
    # remote infra, not locally -- so the usual num_ctx/Modelfile fix for
    # local models doesn't apply (no local weights to configure), and
    # cloud-hosted models typically already ship with large (64k+)
    # context windows. The snapshot-trimming fix below (boxes=False,
    # depth cap) should be the main lever here. If empty responses
    # persist after that, this matches several open community reports of
    # CrewAI/LiteLLM silently swallowing a real backend error (timeout,
    # oversized payload, rate limit) from Ollama Cloud and surfacing it
    # as "None or empty" instead of the actual error -- worth checking
    # `ollama.com` account/usage limits, and worth testing the same
    # request directly against the model with plain litellm.completion()
    # to see if a clearer error surfaces outside of CrewAI's wrapper.

    browser_agent = Agent(
        role="Browser Automation Agent",
        goal="Visit 3 given URLs and extract a concise summary of each",
        backstory="Expert at browser automation and reading web content",
        llm=llm,
        tools=browser_tools,
        verbose=True,
        max_iter=20,             # hard stop instead of an infinite retry loop
        max_execution_time=600,  # 10 min ceiling per task
        allow_delegation=False,
    )

    analyst_agent = Agent(
        role="Analyst",
        goal="Analyze the summaries retrieved from the browsed sites",
        backstory="Expert analyst who processes information",
        llm=llm,
        verbose=True,
        max_iter=10,
        allow_delegation=False,
    )

    SENTINEL = "SEARCH_TOOL_UNAVAILABLE"

    def search_urls_guardrail(output):
        """Reject anything that isn't 3 real URLs or the explicit failure
        sentinel. Without this, a tool failure can quietly turn into the
        model reciting plausible-looking URLs from training memory --
        which is exactly what happened in your run, and is worse than a
        crash because it looks like a normal result."""
        text = (output.raw if hasattr(output, "raw") else str(output)).strip()
        if text == SENTINEL:
            return (True, text)
        urls = re.findall(r"https?://\S+", text)
        if len(urls) < 3:
            return (
                False,
                f"Output must be exactly 3 http(s) URLs, one per line, or "
                f"the literal line {SENTINEL} if the tool failed after 3 "
                f"retries. Do not invent URLs from memory.",
            )
        return (True, text)

    search_task = Task(
        description=(
            "Search for 'healthcare problems needing agentic AI' using the "
            "searxng_search tool and return exactly 3 URLs of non-ad, "
            "non-video, article/website results (skip PDFs). Return only "
            "the URLs, one per line. If the tool errors, retry it up to 3 "
            "times. Do NOT invent, guess, or recall URLs from your own "
            f"training data under any circumstances -- if the tool still "
            f"fails after 3 attempts, output exactly the single line "
            f"{SENTINEL} and nothing else."
        ),
        expected_output="3 URLs, one per line, nothing else",
        agent=browser_agent,
        tools=[SearxSearchTool()],  # self-hosted search API instead of scraping Google
        guardrail=search_urls_guardrail,
    )

    def three_summaries_guardrail(output):
        """Reject the task output unless it looks like 3 numbered summaries
        (or the sentinel was correctly propagated), so a malformed result
        gets auto-retried instead of silently passed to the analyst."""
        text = (output.raw if hasattr(output, "raw") else str(output)).strip()
        if text == SENTINEL:
            return (True, text)
        numbered = re.findall(r"(?m)^\s*\d+[.)]", text)
        if len(numbered) < 3:
            return (False, "Output must contain 3 numbered summaries, one per site.")
        return (True, text)

    browser_task = Task(
        description=(
            f"If the search step's output is exactly {SENTINEL}, do not "
            f"attempt any navigation -- output exactly {SENTINEL} yourself "
            "and stop. Otherwise, for each of the 3 URLs from the search "
            "step: navigate to it, then use browser_evaluate with the "
            "function '() => document.body.innerText' to read the page's "
            "visible text (this is much smaller and cleaner than a full "
            "accessibility snapshot -- only fall back to browser_snapshot "
            "if evaluate fails or the page needs interaction first). Then "
            "go back. If a URL isn't a normal readable webpage, use "
            "scrolling/snapshots to get what content you can instead of "
            "giving up on it. Return a concise summary of each site."
        ),
        expected_output="3 numbered summaries, one per website visited",
        agent=browser_agent,
        context=[search_task],
        guardrail=three_summaries_guardrail,
    )

    analysis_task = Task(
        description="Analyze the site summaries produced by the browser task.",
        expected_output="A structured analysis of the response",
        agent=analyst_agent,
        context=[browser_task],
    )

    crew = Crew(
        agents=[browser_agent, analyst_agent],
        tasks=[search_task, browser_task, analysis_task],
        process=Process.sequential,
        verbose=True,
        max_rpm=30,  # throttle so a runaway loop can't hammer the LLM endpoint
    )

    result = crew.kickoff()
    if SENTINEL in str(result):
        print(f"Run aborted: search tool was unavailable ({SENTINEL}). "
              f"Check that SearXNG is running and reachable at "
              f"{os.environ.get('SEARXNG_BASE_URL', 'http://localhost:8080')}.")
    else:
        print(result)

# --- Fallback: if you don't want to run SearXNG ------------------------
# Keep search_task's description as "Navigate to https://google.com,
# search for '...', return the first 3 non-ad organic result URLs"
# and give browser_agent the raw MCP tools (minus BLOCKED_TOOLS) for
# that step too. It'll work, but expect more retries and occasional
# consent-dialog / layout hiccups -- Google scraping just isn't as
# reliable as a search API for this kind of "get me N URLs" step.
