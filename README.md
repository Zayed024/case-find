#  Court-Data Fetcher & Mini-Dashboard

## Project Objective

This project aims to build a small web application that allows a user to search for case metadata and the latest orders/judgments from a specific Indian court. The application fetches data programmatically, displays it in a user-friendly mini-dashboard, and logs all queries.

---

## Court Targeted

This application is specifically developed to fetch data from the **Delhi High Court** website:  
🔗 [https://delhihighcourt.nic.in/](https://delhihighcourt.nic.in/)

---

## Functional Requirements & Features

The application implements the following core functionalities:

- **User Interface (UI)**: A simple Streamlit-based web form with dropdowns/inputs for Case Type, Case Number, and Filing Year.
- **Backend Data Fetching**: Programmatically requests data from the Delhi High Court website.
- **Automated CAPTCHA Bypass**: Intelligently bypasses the website's CAPTCHA by directly extracting its value from the HTML.
- **Data Parsing**: Extracts key case metadata, including:
  - Parties' names  
  - Filing date  
  - Next hearing date  
  - Order/judgment PDF links (from the detailed orders page)
- **Data Storage**: Logs each query and the raw HTML response to a PostgreSQL database for auditing purposes.
- **Data Display**: Renders the parsed details clearly in the Streamlit dashboard.
- **PDF Download**: Allows users to directly download linked order/judgment PDFs.
- **Error Handling**: Provides user-friendly messages for:
  - Invalid case numbers  
  - Site downtime  
  - Unexpected scraping issues (with detailed tracebacks for debugging)

---

## Technologies Used

- **Python 3.9+**
- **Streamlit** – For building the interactive web UI
- **Playwright** – For headless browser automation and web scraping
- **BeautifulSoup4** – For robust HTML parsing
- **Psycopg2** – PostgreSQL adapter for Python
- **python-dotenv** – For managing environment variables securely

---

## Setup Instructions

Follow these steps to get the application up and running on your local machine.

### Prerequisites

- Python 3.9+ installed
- PostgreSQL database server running and accessible

---

### 1. Clone the Repository

```bash
git clone https://github.com/Zayed024/case-find
```
## 2. Create a Virtual Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source ./.venv/bin/activate
```

## 3. Install Python Dependencies

Install all required Python libraries using pip:

```bash
pip install -r requirements.txt
```

## 4. Install Playright 

```bash
playwright install
```

## 5. Configure Environment Variables

Create a file named `.env` in the root directory of your project and add your PostgreSQL database credentials:

```env
# .env
PG_HOST=your_postgresql_host
PG_DB=your_postgresql_database_name
PG_USER=your_postgresql_username
PG_PASSWORD=your_postgresql_password
```

Replace your_postgresql_host, your_postgresql_database_name, your_postgresql_username, and your_postgresql_password with your actual PostgreSQL connection details.

## 6. Run the Application

Once all dependencies are installed and environment variables are set, run the Streamlit application:

```bash
streamlit run app.py
```

The application will open in your default web browser (usually at http://localhost:8501).

---

## CAPTCHA Strategy (Creative Circumvention)

Instead of relying on external, paid CAPTCHA-solving services or requiring manual user intervention, this application employs a direct extraction strategy:

- The CAPTCHA code is present as plain text within a `<span>` HTML element with a predictable ID (`#captcha-code`).
- The Playwright script directly reads the `innerText` of this element.
- The extracted text is then automatically filled into the CAPTCHA input field (`#captchaInput`) before submitting the form.

This approach is efficient, free, and robust as long as the CAPTCHA element’s structure remains consistent.

---

## Usage

1. Open the application in your browser: [http://localhost:8501](http://localhost:8501)  
2. Select the **Case Type** from the dropdown in the sidebar  
3. Enter the **Case Number**  
4. Enter the **Filing Year**  
5. Click the **Search Case** button  

The application will automatically solve the CAPTCHA, navigate to the results, fetch the case details, and retrieve all associated PDF links from the orders page. The results, including clickable PDF links and download buttons, will be displayed on the main dashboard.

---


## Optional Extras & Future Enhancements
- **Deploy**: deploy the app on streamlit community cloud after making a few changes to the code
- **Dockerfile**: Create a Dockerfile for easy containerization and deployment of the application  
- **Pagination for Multiple Orders**: If a case has multiple pages of orders/judgments, extend the `parse_order_links` function to automatically navigate through all pagination links and collect all available PDFs  
- **Simple Unit Tests**: Implement unit tests for key scraping and parsing functions (`get_case_types`, `parse_all_tables`, `parse_order_links`) using `pytest` to ensure data extraction reliability  
- **CI Workflow**: Set up a Continuous Integration (CI) pipeline (e.g., using GitHub Actions) to automatically run tests and potentially build the Docker image on code pushes  
- **Improved Robustness**: Explore more resilient scraping techniques (e.g., using XPath, more generic CSS selectors, or visual checks) to make the scraper less susceptible to minor website layout changes

---



## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.




