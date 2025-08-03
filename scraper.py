import sys
import json
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL            = "https://delhihighcourt.nic.in"
SEARCH_PAGE_URL     = f"{BASE_URL}/app/get-case-type-status"

# the selectors as they exist on /app/get-case-type-status
CASE_TYPE_SELECT    = "#case_type"
CASE_NO_INPUT       = "#case_no_text"
CASE_YEAR_INPUT     = "#case_year_text"
SUBMIT_BUTTON       = "input[type=submit]"       # the “Submit” button on that form
RESULTS_TABLE       = "table#tblData"
ORDER_LINK_IN_RESULTS = "table#tblData a:has-text('Orders')"


def scrape_case_data(case_type, case_number, filing_year):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            # 1) Load the same page you hit for get_case_types()
            page.goto(SEARCH_PAGE_URL)
            page.wait_for_selector(CASE_TYPE_SELECT)

            # 2) Fill form
            page.select_option(CASE_TYPE_SELECT, case_type)
            page.fill(CASE_NO_INPUT, case_number)
            page.fill(CASE_YEAR_INPUT, filing_year)

            # 3) Click Submit, grab the popup
            with context.expect_page() as new_page_info:
                page.click(SUBMIT_BUTTON)
            result_page = new_page_info.value
            result_page.wait_for_selector(RESULTS_TABLE, timeout=60_000)

            # 4) In the results, find the “Orders” link and build its absolute URL
            link_el = result_page.query_selector(ORDER_LINK_IN_RESULTS)
            if not link_el:
                return {"error": "No ‘Orders’ link found in results"}, None

            relative_href = link_el.get_attribute("href")
            detail_url = urljoin(BASE_URL, relative_href)

            # 5) Navigate to the full detail page
            detail_page = context.new_page()
            detail_page.goto(detail_url)
            detail_page.wait_for_load_state("networkidle")
            raw_html = detail_page.content()

            # 6) Parse the detail page
            parties = re.search(
                r"Parties Name:[\s\S]*?<td[^>]*>([\s\S]*?)</td>",
                raw_html
            )
            dates = re.search(
                r"Filing Date:[\s\S]*?<td[^>]*>([\s\S]*?)</td>.*?"
                r"Next Hearing Date:[\s\S]*?<td[^>]*>([\s\S]*?)</td>",
                raw_html
            )
            pdfs = re.findall(r'href="([^"]+\.pdf)"', raw_html)

            parsed = {
                "parties_names": parties.group(1).strip() if parties else "Not found",
                "filing_date": dates.group(1).strip() if dates else "Not found",
                "next_hearing_date": dates.group(2).strip() if dates else "Not found",
                "pdf_links": [urljoin(BASE_URL, href) for href in pdfs]
            }

            return parsed, raw_html

        except Exception as e:
            return {"error": str(e)}, None

        finally:
            browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(json.dumps({"error": "Usage: search <CASE_TYPE> <CASE_NO> <YEAR>"}))
        sys.exit(1)

    _, cmd, ct, num, year = sys.argv
    if cmd != "search":
        print(json.dumps({"error": "Unknown command"}))
        sys.exit(1)

    result, raw = scrape_case_data(ct, num, year)
    print(json.dumps({"result": result, "raw_response": raw}))
