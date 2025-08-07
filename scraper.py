import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

import sys
import asyncio
import json
import traceback

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


BASE_URL            = "https://delhihighcourt.nic.in"
SEARCH_PAGE_URL     = f"{BASE_URL}/app/get-case-type-status"

# Selectors on that page 
CASE_TYPE_SELECT    = "#case_type"
CASE_NO_INPUT       = "#case_number"  
CASE_YEAR_INPUT     = "#case_year"   
SUBMIT_BUTTON       = "#search"       
RESULTS_TABLE       = "table#caseTable" 


CAPTCHA_CODE_SELECTOR = "#captcha-code"
CAPTCHA_INPUT_SELECTOR = "#captchaInput"


def get_case_types():
    """
    Scrape the case-type dropdown and return a list of values,
    like ['W.P.(C)', 'CRL.M.C.', ...].
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(SEARCH_PAGE_URL)
            page.wait_for_selector(CASE_TYPE_SELECT)

            
            values = page.eval_on_selector_all(
                f"{CASE_TYPE_SELECT} option",
                "opts => opts.map(o => o.value).filter(v => v)"
            )
            browser.close()
            return {"result": values}
        except Exception as e:
            tb_str = traceback.format_exc()
            return {"error": str(e), "traceback": tb_str}


def parse_all_tables(html, min_rows=1):
    """
    Returns a list of tables. Each table is:
      {
        "headers": [...],
        "rows": [ [...], [...], ... ]
      }
    Only tables with > `min_rows` data-rows are returned.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    
    for table_el in soup.find_all("table"):
        # 1) Collect all rows
        trs = table_el.find_all("tr")
        if len(trs) <= min_rows:
            continue
        
        # 2) Determine headers
        # Prefer <th>, else use first row's <td>
        ths = table_el.find_all("th")
        if ths:
            headers = [th.get_text(strip=True) for th in ths]
            data_trs = trs
        else:
            first_tds = trs[0].find_all("td")
            headers = [td.get_text(strip=True) for td in first_tds]
            data_trs = trs[1:]
        
        # 3) Extract each row's cells
        rows = []
        for tr in data_trs:
            tds = tr.find_all("td")
            if not tds:
                continue
            row = [td.get_text(separator=" ", strip=True) for td in tds]
            rows.append(row)
        
        if rows:
            tables.append({"headers": headers, "rows": rows})
    
    return tables

def parse_order_links(order_html):
    """
    Parses the HTML of the orders/judgments page to extract PDF links and dates.
    Targets the table specifically by its ID "caseTable".
    """
    soup = BeautifulSoup(order_html, "html.parser")
    # Target the table specifically by its ID
    table = soup.find("table", id="caseTable")
    links = []

    if not table:
        return links # No table found with the specified ID

    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) >= 3: # Ensure there are enough columns
            anchor = tds[1].find("a", href=True) 
            if anchor:
                href = anchor["href"]
                pdf_url = urljoin(BASE_URL, href)
                date = tds[2].get_text(strip=True) 
                links.append({"date": date, "pdf_url": pdf_url})
    return links


def scrape_case_data(case_type: str, case_number: str, filing_year: str):
    """
    Automates CAPTCHA solving and scrapes case data, including PDF links from the orders page.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Set to headless=False for debugging visibility
        context = browser.new_context()
        page = context.new_page()

        try:
            # 1) Load form
            page.goto(SEARCH_PAGE_URL)
            page.wait_for_selector(CASE_TYPE_SELECT)

            # 2) Fill fields
            page.select_option(CASE_TYPE_SELECT, case_type)
            page.fill(CASE_NO_INPUT, case_number)
            page.select_option(CASE_YEAR_INPUT, filing_year) 

            # 3) Extract and solve CAPTCHA
            page.wait_for_selector(CAPTCHA_CODE_SELECTOR)
            captcha_text = page.inner_text(CAPTCHA_CODE_SELECTOR)
            page.fill(CAPTCHA_INPUT_SELECTOR, captcha_text)
            
            print(f"CAPTCHA solved: {captcha_text}", file=sys.stderr)

            # 4) Click submit and wait for initial results table
            page.click(SUBMIT_BUTTON)
            page.wait_for_timeout(timeout=1000) # Give a small timeout for page to process
            page.wait_for_selector(RESULTS_TABLE, timeout=60_000) 
            
            raw_html_initial_results = page.content() # Get content of the initial results page
            soup_initial = BeautifulSoup(raw_html_initial_results, "html.parser")

            # Check if page contains known "no case found" markers
            page_text = soup_initial.get_text(" ", strip=True).lower()
            if "no data available" in page_text or "no such record" in page_text or "case not found" in page_text:
                raise ValueError(f"No case found for {case_type} {case_number}/{filing_year}")


            # Extract main case details from the initial results page 
            
            
            main_table = soup_initial.find("table", id="caseTable")
            parties_names = "Not found"
            filing_date = "Not found"
            next_hearing_date = "Not found"
            
            if main_table:
                
                first_row = main_table.select_one("tbody tr")
                if first_row:
                    tds = first_row.find_all("td")
                    if len(tds) >= 4: # Ensure enough columns for the data
                       
                        parties_names = tds[2].get_text(" ", strip=True)

                        listing_info_text = tds[3].get_text(" ", strip=True)
                        
                        # Regex to find "Last Date: DD/MM/YYYY" for Filing Date
                        filing_date_match = re.search(r"Last Date: (\d{2}/\d{2}/\d{4})", listing_info_text)
                        if filing_date_match:
                            filing_date = filing_date_match.group(1)
                        
                        # Regex to find "NEXT DATE: DD/MM/YYYY" for Next Hearing Date
                        next_date_match = re.search(r"NEXT DATE: (\d{2}/\d{2}/\d{4})", listing_info_text)
                        if next_date_match:
                            next_hearing_date = next_date_match.group(1)
                        elif "NEXT DATE: NA" in listing_info_text:
                            next_hearing_date = "NA" # Explicitly set if not available


            # Iterate through initial results table to find and scrape Orders links for each case 
            results_list = [] 
            if main_table:
                rows = main_table.select("tbody tr")
                for tr in rows:
                    tds = tr.find_all("td")
                    if len(tds) < 4: # Basic check for valid row structure
                        continue # Skip malformed rows

                    case_sno = tds[0].get_text(strip=True)
                    case_num_text = tds[1].get_text(" ", strip=True) # This includes the case number and "Orders" link text
                    case_parties_from_row = tds[2].get_text(" ", strip=True) # Get parties specific to this row
                    case_listing_info = tds[3].get_text(" ", strip=True)

                    orders_link_el = tds[1].find("a", href=True, string=re.compile("Orders", re.I)) # Find the specific "Orders" link in this row
                    
                    pdf_links_for_this_case = []
                    case_detail_url = None 
                    
                    if orders_link_el:
                        href = orders_link_el["href"]
                        case_detail_url = urljoin(BASE_URL, href)

                        # Open a new page/tab for the specific case's orders to avoid losing context
                        case_orders_page = context.new_page()
                        case_orders_page.goto(case_detail_url)
                        # Wait for the specific table on the orders page to load
                        case_orders_page.wait_for_selector("table#caseTable", timeout=10000) 
                        orders_html_for_this_case = case_orders_page.content()
                        
                        # Parse PDF links from the orders page
                        pdf_links_for_this_case = parse_order_links(orders_html_for_this_case)
                        
                        case_orders_page.close() 

                    results_list.append({
                        "sno": case_sno,
                        "case_number": case_num_text,
                        "parties": case_parties_from_row, 
                        "listing_info": case_listing_info,
                        "orders_link": case_detail_url, 
                        "filing_date": filing_date,
                        "next_hearing_date": next_hearing_date, 
                        "pdf_links": pdf_links_for_this_case
                    })
            
            # The 'parsed' dictionary will now contain details from the first result (or overall if only one)
            # and the pdf_links will be from the specific orders page.
            # If there are multiple results, 'results_list' will hold all parsed data.
            # For the main display in app.py, we'll use the overall extracted details and the first case's PDFs.

            parsed_main_display = {
                "parties_names": parties_names,
                "filing_date": filing_date, 
                "next_hearing_date": next_hearing_date, 
                "pdf_links": results_list[0]["pdf_links"] if results_list and results_list[0]["pdf_links"] else []
            }


            tables_from_initial_results = parse_all_tables(raw_html_initial_results, min_rows=1)

            # Return the parsed data for the main display and the full list of results
            return {"result": parsed_main_display, "tables": tables_from_initial_results, "raw_response": raw_html_initial_results, "all_results": results_list}

        except Exception as e:
            tb_str = traceback.format_exc()
            return {"error": str(e), "traceback": tb_str}
        finally:
            browser.close()

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"error": "Usage: <command> [args]"}))
            sys.exit(1)

        command = sys.argv[1]
        
        if command == "get_types":
            if len(sys.argv) != 2:
                print(json.dumps({"error": "Usage: get_types"}))
                sys.exit(1)
            output = get_case_types()
            print(json.dumps(output))

        elif command == "search":
            if len(sys.argv) != 5:
                print(json.dumps({"error": "Usage: search <CASE_TYPE> <CASE_NO> <YEAR>"}))
                sys.exit(1)
            _, _, ct, num, year = sys.argv
            output = scrape_case_data(ct, num, year)
            print(json.dumps(output))
            
        else:
            print(json.dumps({"error": "Unknown command"}))
            sys.exit(1)

    except Exception as e:
        tb_str = traceback.format_exc()
        print(json.dumps({"error": str(e), "traceback": tb_str}))
        sys.exit(1)

