# Jobster 🕵️‍♂️
> The Ultimate Python Scraper for Global Job Board Data

## 📖 Overview
Jobster is a powerful, lightweight Python library designed to scrape job postings from major platforms like Indeed, LinkedIn, ZipRecruiter, and Glassdoor without requiring API keys. Whether you are building an automated job application bot, conducting labor market research, or powering a custom job board, Jobster delivers structured, clean data right into your hands.

## ✨ Features
* **Multi-Platform Support:** Effortlessly extract jobs from LinkedIn, Indeed, ZipRecruiter, Glassdoor, Google Jobs, Bayt, Naukri, and BDJobs.
* **No API Keys Required:** Runs directly on your machine, leveraging web scraping techniques rather than expensive developer APIs.
* **Robust Proxy Integration:** Built-in round-robin proxy support to prevent IP bans and rate limiting, especially crucial for strict platforms like LinkedIn.
* **Extensive Filtering:** Filter by job type, remote status, location, posting recency, and specific search keywords.
* **Structured Output:** Receive data in a clean pandas DataFrame, ready to be exported to CSV, Excel, or integrated into an SQL database.

## 🛠 Tech Stack
* **[Python (>=3.10)](https://www.python.org/):** The core programming language powering the scraper.
* **[Pandas](https://pandas.pydata.org/):** Used to structure the scraped job data into DataFrames for easy manipulation and export.
* **[Requests / HTTP clients]:** Powers the network calls to fetch job board HTML.

## 📋 Prerequisites
Before you start, ensure you have the following installed on your machine:
* **Python v3.10 or higher**
* **Git:** Required to clone the repository if building from source.
* **pip:** The Python package installer.
* *(Optional)* **Proxies:** A list of proxy IP addresses is highly recommended to avoid `429 Too Many Requests` errors from job boards.

## 🚀 Local Development (Step-by-Step)

### 1. Install System Requirements
If you haven't already, install [Python](https://www.python.org/downloads/) and [Git](https://git-scm.com/downloads).

### 2. Install the Library
The easiest way to get started is to install `jobster` via `pip`.
```bash
pip install -U python-jobster
```

### 3. Usage & Execution
Create a file named `scrape.py` and add the following code:
```python
import csv
from jobster import scrape_jobs

jobs = scrape_jobs(
    site_name=["indeed", "linkedin", "zip_recruiter", "google"], # "glassdoor", "bayt", "naukri", "bdjobs"
    search_term="software engineer",
    google_search_term="software engineer jobs near San Francisco, CA since yesterday",
    location="San Francisco, CA",
    results_wanted=20,
    hours_old=72,
    country_indeed='USA',

    # linkedin_fetch_description=True # gets more info such as description, direct job url (slower)
    # proxies=["208.195.175.46:65095", "208.195.175.45:65095", "localhost"],
)
print(f"Found {len(jobs)} jobs")
print(jobs.head())
jobs.to_csv("jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False) # to_excel
```
Run the script to collect your data:
```bash
python scrape.py
```

## 🧠 How It Works (Architecture)
1. **The Request:** When you call `scrape_jobs()`, the library dynamically constructs search URLs based on your parameters (location, search terms, filters) for each selected job board.
2. **Concurrent Scraping:** The scraper fetches the HTML data from these endpoints. If you provide proxies, it distributes the requests across them to prevent your main IP from being blocked.
3. **Data Parsing:** Custom parsers for each job board (Indeed, LinkedIn, etc.) traverse the HTML/JSON responses and extract standard fields (Title, Company, Salary, Location).
4. **The Output:** The raw data is consolidated, normalized, and returned as a single pandas DataFrame, masking the complexity of parsing multiple different website structures.

## 📁 Folder Structure (If cloned from source)
```text
jobster/
├── jobster/                    # Core library logic and platform-specific scrapers
│   ├── scrapers/               # Individual scrapers for Indeed, LinkedIn, etc.
│   └── __init__.py             # Exposes the `scrape_jobs` function
├── tests/                      # Unit and integration tests
├── setup.py                    # Package configuration for PyPI
└── README.md                   # This documentation file!
```

---

## ⚙️ Parameters for `scrape_jobs()`

### Optional
* `site_name` (list|str): linkedin, zip_recruiter, indeed, glassdoor, google, bayt, bdjobs (default is all)
* `search_term` (str)
* `google_search_term` (str): search term for google jobs. This is the only param for filtering google jobs.
* `location` (str)
* `distance` (int): in miles, default 50
* `job_type` (str): fulltime, parttime, internship, contract
* `proxies` (list): in format `['user:pass@host:port', 'localhost']`. Each job board scraper will round robin through the proxies
* `is_remote` (bool)
* `results_wanted` (int): number of job results to retrieve for each site specified in `site_name`
* `easy_apply` (bool): filters for jobs that are hosted on the job board site (LinkedIn easy apply filter no longer works)
* `user_agent` (str): override the default user agent which may be outdated
* `description_format` (str): markdown, html (Format type of the job descriptions. Default is markdown.)
* `offset` (int): starts the search from an offset (e.g. 25 will start the search from the 25th result)
* `hours_old` (int): filters jobs by the number of hours since the job was posted (ZipRecruiter and Glassdoor round up to next day.)
* `verbose` (int) `{0, 1, 2}`: Controls the verbosity of the runtime printouts (0 prints only errors, 1 is errors+warnings, 2 is all logs. Default is 2.)
* `linkedin_fetch_description` (bool): fetches full description and direct job url for LinkedIn (Increases requests by O(n))
* `linkedin_company_ids` (list[int]): searches for linkedin jobs with specific company ids
* `country_indeed` (str): filters the country on Indeed & Glassdoor (see below for correct spelling)
* `enforce_annual_salary` (bool): converts wages to annual salary
* `ca_cert` (str): path to CA Certificate file for proxies

### Limitations
* **Indeed limitations:**
  Only one from this list can be used in a search:
  * `hours_old`
  * `job_type` & `is_remote`
  * `easy_apply`
* **LinkedIn limitations:**
  Only one from this list can be used in a search:
  * `hours_old`
  * `easy_apply`

## 🌍 Supported Countries for Job Searching

* **LinkedIn**: Searches globally & uses only the `location` parameter.
* **ZipRecruiter**: Searches for jobs in US/Canada & uses only the `location` parameter.
* **Indeed / Glassdoor**: Supports most countries, but the `country_indeed` parameter is required. Additionally, use the `location` parameter to narrow down the location, e.g. city & state if necessary.

You can specify the following countries when searching on Indeed (use the exact name, `*` indicates support for Glassdoor):

| | | | |
|---|---|---|---|
| Argentina | Australia* | Austria* | Bahrain |
| Belgium* | Brazil* | Canada* | Chile |
| China | Colombia | Costa Rica | Czech Republic |
| Denmark | Ecuador | Egypt | Finland |
| France* | Germany* | Greece | Hong Kong* |
| Hungary | India* | Indonesia | Ireland* |
| Israel | Italy* | Japan | Kuwait |
| Luxembourg | Malaysia | Mexico* | Morocco |
| Netherlands* | New Zealand* | Nigeria | Norway |
| Oman | Pakistan | Panama | Peru |
| Philippines | Poland | Portugal | Qatar |
| Romania | Saudi Arabia | Singapore* | South Africa |
| South Korea | Spain* | Sweden | Switzerland* |
| Taiwan | Thailand | Turkey | Ukraine |
| United Arab Emirates | UK* | USA* | Uruguay |
| Venezuela | Vietnam* | | |

* **Bayt**: Only uses the `search_term` parameter currently and searches internationally.

## 📝 Notes
* Indeed is the best scraper currently with no rate limiting.
* All the job board endpoints are capped at around 1000 jobs on a given search.
* LinkedIn is the most restrictive and usually rate limits around the 10th page with one ip. Proxies are a must basically.

## ❓ Frequently Asked Questions

**Q: Why is Indeed giving unrelated roles?**
A: Indeed searches the description too.
* use `-` to remove words
* `""` for exact match

*Example of a good Indeed query:*
```
search_term='"engineering intern" software summer (java OR python OR c++) 2025 -tax -marketing'
```
This searches the description/title and must include software, summer, 2025, one of the languages, engineering intern exactly, no tax, no marketing.

**Q: No results when using "google"?**
A: You have to use super specific syntax. Search for google jobs on your browser and then whatever pops up in the google jobs search box after applying some filters is what you need to copy & paste into the `google_search_term`.

**Q: Received a response code 429?**
A: This indicates that you have been blocked by the job board site for sending too many requests. All of the job board sites are aggressive with blocking. We recommend:
* Wait some time between scrapes (site-dependent).
* Try using the `proxies` param to change your IP address.

## 📊 JobPost Schema

```text
JobPost
├── title
├── company
├── company_url
├── job_url
├── location
│   ├── country
│   ├── city
│   ├── state
├── is_remote
├── description
├── job_type: fulltime, parttime, internship, contract
├── job_function
│   ├── interval: yearly, monthly, weekly, daily, hourly
│   ├── min_amount
│   ├── max_amount
│   ├── currency
│   └── salary_source: direct_data, description (parsed from posting)
├── date_posted
└── emails

Linkedin specific
└── job_level

Linkedin & Indeed specific
└── company_industry

Indeed specific
├── company_country
├── company_addresses
├── company_employees_label
├── company_revenue_label
├── company_description
└── company_logo

Naukri specific
├── skills
├── experience_range
├── company_rating
├── company_reviews_count
├── vacancy_count
└── work_from_home_type
```