import streamlit as st
import psycopg2
import re
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import lru_cache
import subprocess
import json
import sys

# Load environment variables from a .env file
load_dotenv()

# --- Database Setup ---
def init_db():
    """
    Initializes a PostgreSQL database connection and creates a table for logging queries.
    Database credentials are loaded from environment variables.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("PG_HOST"),
            database=os.getenv("PG_DB"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD")
        )
        cursor = conn.cursor()
        
        # Create the logs table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                case_type TEXT,
                case_number TEXT,
                filing_year TEXT,
                timestamp TIMESTAMP,
                raw_response TEXT
            )
        """)
        conn.commit()
        cursor.close()
        return conn
    except psycopg2.OperationalError as e:
        st.error(f"Failed to connect to PostgreSQL: {e}")
        st.info("Please ensure your PostgreSQL server is running and the environment variables (PG_HOST, PG_DB, PG_USER, PG_PASSWORD) are set correctly.")
        return None

def log_query(case_type, case_number, filing_year, raw_response):
    """Logs the user query and raw HTML response to the PostgreSQL database."""
    conn = init_db()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO logs (case_type, case_number, filing_year, timestamp, raw_response) VALUES (%s, %s, %s, %s, %s)",
                (case_type, case_number, filing_year, datetime.now(), raw_response)
            )
            conn.commit()
            st.success("Query logged to PostgreSQL successfully.")
        except psycopg2.Error as e:
            st.error(f"Failed to log data to PostgreSQL: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

# --- Scraping Logic via Subprocess ---

@st.cache_data(show_spinner=True)
def get_case_types():
    """
    Calls the scraper.py script as a subprocess to get case types.
    The result is cached to avoid calling the script on every page refresh.
    """
    try:
        result = subprocess.run(
            [sys.executable, "scraper.py", "get_types"],
            capture_output=True,
            text=True,
            check=True
        )
        output = json.loads(result.stdout)
        if "error" in output:
            st.error(output["error"])
            return ["W.P.(C)", "C.R.P.", "C.S.(OS)", "CRL.M.C."]
        
        types = output["result"]
        if isinstance(types, str):
            st.error(types)
            return ["W.P.(C)", "C.R.P.", "C.S.(OS)", "CRL.M.C."]
        
        return types
    except subprocess.CalledProcessError as e:
        st.error(f"Could not get case types. Subprocess failed with error: {e.stderr}")
        return ["W.P.(C)", "C.R.P.", "C.S.(OS)", "CRL.M.C."]
    except Exception as e:
        st.error(f"An unexpected error occurred while getting case types: {e}")
        return ["W.P.(C)", "C.R.P.", "C.S.(OS)", "CRL.M.C."]

def fetch_case_data(case_type, case_number, filing_year):
    """
    Calls the scraper.py script as a subprocess to scrape case data.
    """
    try:
        st.warning("A browser window will open for manual CAPTCHA solving. Please solve it and click the 'Go' button. Then return to your terminal and press Enter.")
        
        result = subprocess.run(
            [sys.executable, "scraper.py", "search", case_type, case_number, filing_year],
            capture_output=True,
            text=True,
            check=True
        )
        
        output = json.loads(result.stdout)
        if "error" in output:
            return {"error": output["error"]}, None
        
        return output["result"], output["raw_response"]
    except subprocess.CalledProcessError as e:
        return {"error": f"Subprocess failed with error: {e.stderr}"}, None
    except Exception as e:
        return {"error": str(e)}, None


# --- Streamlit UI ---
def main():
    st.set_page_config(page_title="Court-Data Fetcher", layout="wide")
    st.title("🏛️ Delhi High Court Case Status")
    st.markdown(
        """
        This application fetches case metadata and the latest orders/judgments from the Delhi High Court website.
        Please provide the case details below.
        
        **Note:** A new browser window will open for you to manually solve the CAPTCHA for each search.
        """
    )
    
    case_types = get_case_types()
    
    st.sidebar.header("Case Search Form")
    with st.sidebar.form(key='case_form'):
        case_type = st.selectbox("Case Type", options=case_types)
        case_number = st.text_input("Case Number")
        filing_year = st.text_input("Filing Year", placeholder="e.g., 2024")
        submit_button = st.form_submit_button("Search Case")
    
    if submit_button and case_number and filing_year:
        with st.spinner("Fetching case data..."):
            parsed_data, raw_response = fetch_case_data(case_type, case_number, filing_year)
            
            if parsed_data and not parsed_data.get("error"):
                log_query(case_type, case_number, filing_year, raw_response)
                
                st.success("Case data fetched successfully!")
                
                data = parsed_data
                st.header("Case Details")
                st.markdown(f"**Parties:** {data['parties_names']}")
                st.markdown(f"**Filing Date:** {data['filing_date']}")
                st.markdown(f"**Next Hearing Date:** {data['next_hearing_date']}")
                
                st.header("Orders & Judgments")
                if data['pdf_links']:
                    for i, link in enumerate(data['pdf_links']):
                        abs_link = f"https://delhihighcourt.nic.in/{link}"
                        st.markdown(f"[{os.path.basename(link)}]({abs_link})")
                else:
                    st.markdown("No order or judgment links found.")
            else:
                st.error(f"Error fetching data: {parsed_data.get('error', 'Unknown error')}")
                
    st.sidebar.markdown("---")
    st.sidebar.info("This application is for demonstration purposes only. The accuracy of the data depends on the court's website structure.")

if __name__ == "__main__":
    main()
