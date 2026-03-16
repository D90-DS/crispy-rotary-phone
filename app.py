import streamlit as st
import json
import boto3
import vertexai
from sqlalchemy import create_engine
from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    FunctionDeclaration,
    Part,
)

from edgar_service import EdgarService
from press_release_service import PressReleaseService
from property_service import PropertyService # <-- IMPORTING YOUR NEW SERVICE

# ==========================================
# 1. MULTI-CLOUD: AWS Bedrock Integration
# ==========================================
def summarize_with_bedrock(text: str) -> str:
    """Uses AWS Bedrock to summarize text, fulfilling the multi-cloud requirement."""
    try:
        bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
        payload = {
            "inputText": f"Provide a concise 2-sentence summary of this press release: {text}",
            "textGenerationConfig": {"maxTokenCount": 200, "temperature": 0.2}
        }
        response = bedrock.invoke_model(
            modelId='amazon.titan-text-express-v1',
            contentType='application/json',
            accept='application/json',
            body=json.dumps(payload)
        )
        response_body = json.loads(response.get('body').read())
        return response_body.get('results')[0].get('outputText')
    except Exception as e:
        return f"[AWS Bedrock Fallback/Error - Ensure AWS credentials are set]: {str(e)}"

# ==========================================
# 2. GCP VERTEX AI ADK: Tool Definitions
# ==========================================
get_sec_financials_func = FunctionDeclaration(
    name="get_sec_financials",
    description="Get recent SEC financial metrics (revenue, net income) for the company.",
    parameters={
        "type": "object",
        "properties": {
            "max_items": {"type": "integer", "description": "Maximum number of recent financial records to retrieve."}
        }
    }
)

search_press_releases_func = FunctionDeclaration(
    name="search_press_releases",
    description="Search company press releases for SPECIFIC news, acquisitions, or business updates using a keyword.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for press releases."}
        },
        "required": ["query"]
    }
)

get_recent_press_releases_func = FunctionDeclaration(
    name="get_recent_press_releases",
    description="Get the most recent press releases. Use this when the user asks for the latest news without specifying a keyword.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of recent press releases to retrieve."}
        }
    }
)

# UPDATED: We no longer ask the LLM to write SQL! 
# We just ask it to pass the user's natural language question to our PropertyService.
query_property_db_func = FunctionDeclaration(
    name="query_property_db",
    description=(
        "Search the property and financials database. Pass the user's question directly to this tool. "
        "The tool will automatically filter by metro area, property type (industrial, office, retail, multifamily, mixed-use), "
        "and revenue, and will return the matching records along with total aggregate financials."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The user's original question about properties."}
        },
        "required": ["question"]
    }
)

agent_tools = Tool(
    function_declarations=[
        get_sec_financials_func,
        search_press_releases_func,
        get_recent_press_releases_func,
        query_property_db_func,
    ]
)

# ==========================================
# 3. INITIALIZE SERVICES
# ==========================================
@st.cache_resource
def init_agent_system():
    vertexai.init() 
    model = GenerativeModel(
        "gemini-2.5-flash",
        tools=[agent_tools],
        system_instruction=(
            "You are a Financial Assistant for a Real Estate Corp. "
            "You MUST use the provided tools to fetch SEC data, property data, or press releases. "
            "For property value questions, calculate it by dividing the 'revenue' by 'sq_footage' from the records returned by the tool."
        )
    )
    chat = model.start_chat()
    
    # Initialize local services
    edgar = EdgarService(cik="1045609", user_agent="Orson Terrill orson.terrill@greatcomplexiy.com")
    press_releases = PressReleaseService("press_releases.json")
    
    # Initialize the new Property Service with a SQLAlchemy engine
    engine = create_engine("sqlite:///realestate.db")
    property_service = PropertyService(engine)
    
    return chat, edgar, press_releases, property_service

chat_session, edgar, press_releases, property_service = init_agent_system()

# ==========================================
# 4. STREAMLIT UI & AGENTIC ROUTING LOOP
# ==========================================
st.set_page_config(page_title="Real Estate AI Agent", layout="wide")
st.title("🏢 Real Estate Agentic Assistant")
st.markdown("*Powered by Vertex AI Agent Builder & AWS Bedrock*")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("E.g., What is the average property in the upper west side valued at per square foot?"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Agent is reasoning and routing query..."):
            response = chat_session.send_message(prompt)
            
            while response.candidates[0].function_calls:
                function_call = response.candidates[0].function_calls[0]
                func_name = function_call.name
                args = {key: value for key, value in function_call.args.items()}
                st.info(f"🛠️ Agent routed to tool: `{func_name}`")
                
                api_response = {}
                
                if func_name == "get_sec_financials":
                    raw_response = edgar.get_recent_financial_metrics(max_items_each=args.get("max_items", 3))
                    api_response = {"text_dump": str(raw_response)}
                    
                elif func_name == "search_press_releases":
                    raw_prs = press_releases.search(args.get("query", ""))
                    if raw_prs:
                        st.info("☁️ Multi-Cloud: Triggering AWS Bedrock to summarize press release...")
                        bedrock_summary = summarize_with_bedrock(raw_prs[0].get('summary', ''))
                        api_response = {"results": raw_prs, "aws_bedrock_executive_summary": bedrock_summary}
                    else:
                        api_response = {"message": "No press releases found for that query."}
                        
                elif func_name == "get_recent_press_releases":
                    raw_prs = press_releases.list_recent(limit=args.get("limit", 1))
                    if raw_prs:
                        st.info("☁️ Multi-Cloud: Triggering AWS Bedrock to summarize recent press release...")
                        bedrock_summary = summarize_with_bedrock(raw_prs[0].get('summary', ''))
                        api_response = {"results": raw_prs, "aws_bedrock_executive_summary": bedrock_summary}
                    else:
                        api_response = {"message": "No recent press releases available."}
                        
                # NEW ROUTE: Property Database via PropertyService
                elif func_name == "query_property_db":
                    try:
                        # We pass the question directly to your pre-built service
                        service_response = property_service.run_question(args.get("question", ""))
                        
                        # Convert the Pandas DataFrame to a dictionary so the LLM can read it
                        records_dict = service_response["records"].to_dict(orient="records")
                        
                        api_response = {
                            "filters_applied": service_response["filters"],
                            "totals": service_response["totals"],
                            "records": records_dict
                        }
                    except Exception as e:
                        api_response = {"error": str(e)}

                # Pass the data back to Vertex AI
                response = chat_session.send_message(
                    Part.from_function_response(name=func_name, response={"content": str(api_response)})
                )

            # Final Output
            final_answer = response.text
            st.markdown(final_answer)
            st.session_state.messages.append({"role": "assistant", "content": final_answer})