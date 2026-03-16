import os
import sqlite3
from genkit import Genkit
from pydantic import BaseModel, Field

# Import your existing Python services
from edgar_service import EdgarService
from press_release_service import PressReleaseService

# Initialize Genkit
# Note: Genkit will automatically pick up your GCP credentials from the gcloud login you did earlier.
ai = Genkit()

# Initialize our backend classes
# Using Prologis CIK and your email from the edgar_service test harness
edgar = EdgarService(cik="1045609", user_agent="Orson Terrill orson.terrill@greatcomplexiy.com")
press_releases = PressReleaseService("press_releases.json")


# ==========================================
# TOOL 1: SEC EDGAR Financials
# ==========================================
class SECInput(BaseModel):
    max_items: int = Field(default=3, description="Maximum number of recent financial records to retrieve.")

@ai.tool(name="get_sec_financials", description="Get recent SEC financial metrics (revenue, net income) for the company.")
def get_sec_financials(input: SECInput):
    return edgar.get_recent_financial_metrics(max_items_each=input.max_items)


# ==========================================
# TOOL 2: Press Releases
# ==========================================
class PRInput(BaseModel):
    query: str = Field(description="Search query for press releases (e.g., 'acquisition', 'earnings', 'expansion').")

@ai.tool(name="search_press_releases", description="Search company press releases for news, expansions, or business updates.")
def search_press_releases(input: PRInput):
    return press_releases.search(input.query)


# ==========================================
# TOOL 3: Property Database
# ==========================================
class DBInput(BaseModel):
    sql_query: str = Field(
        description="A valid SQLite query to execute against the real estate database. "
                    "The table name is 'properties'. Available columns: property_id, boro_block_lot, "
                    "address, metro_area, neighborhood, building_classification, property_type, "
                    "sq_footage, revenue, net_income, expenses, report_year."
    )

@ai.tool(name="query_property_db", description="Execute a SQL query against the local property database to find building stats, revenue, or expenses.")
def query_property_db(input: DBInput):
    try:
        conn = sqlite3.connect('realestate.db')
        cursor = conn.cursor()
        cursor.execute(input.sql_query)
        rows = cursor.fetchall()
        conn.close()
        return {"status": "success", "data": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==========================================
# THE MAIN AI FLOW
# ==========================================
class ChatInput(BaseModel):
    question: str = Field(description="The user's question about financials, news, or properties.")

@ai.flow(name="real_estate_assistant")
def real_estate_assistant(input: ChatInput) -> str:
    """The main entry point for the Financial Assistant."""
    
    # We use Gemini 1.5 Flash as the brain, giving it access to our 3 tools.
    response = ai.generate(
        model="vertexai/gemini-2.5-flash",
        prompt=input.question,
        tools=[get_sec_financials, search_press_releases, query_property_db],
        system_prompt=(
            "You are a Financial Assistant for a Real Estate Corp. "
            "Use the provided tools to answer user questions about SEC financials, company press releases, "
            "and property databases. Always rely on the tools for factual data. If writing SQL, ensure it is valid SQLite."
        )
    )
    return response.text

# This allows the Genkit UI to discover and run the server
if __name__ == "__main__":
    ai.start()