Sustainability Monitoring Hub
=============================

Sustainability Monitoring Hub is a Streamlit-based platform for company-level sustainability operations. It combines GHG emissions tracking with verification workflows, ESG reporting/disclosure modules, document exchange, and reduction roadmap planning.

[Live Demo](https://manage-ghg-emissions.streamlit.app/)

<img width="2537" height="1330" alt="image" src="https://github.com/user-attachments/assets/2eed6eec-7d2c-41a9-b332-f9bbc3167fa3" />
<img width="2525" height="1337" alt="image" src="https://github.com/user-attachments/assets/c89b5642-a167-4199-a9d0-5cb6b04e1f07" />
<img width="2527" height="1335" alt="image" src="https://github.com/user-attachments/assets/f2b8322f-6aff-4c76-8aed-788819de6231" />
<img width="2524" height="1326" alt="image" src="https://github.com/user-attachments/assets/d5f8a386-ca5b-4387-b338-2cdec026692a" />


## Current Capabilities
- **Authentication + role access control**: Login/registration with page-level permissions (admin, manager, normal user).
- **GHG activity entry**: Add single emissions entries by scope/category/source with reporting period, data source, and calculation notes.
- **Bulk emissions upload**: Upload emissions in bulk with validation and integrated processing.
- **Emissions dashboard**: Baseline-year setup, baseline metrics, single-year analysis, and multi-year comparisons.
- **Data review and verification**:
  - View/filter emissions records and detailed calculation breakdowns.
  - Verify/reject entries with audit trail and bulk-verify support.
- **Emission factor management**:
  - Activate/deactivate visibility of sources by company.
  - Add/edit/delete custom emission sources.
  - Reference year support, search/filter tools, and source history.
  - Bulk custom source upload.
- **Roadmap Tracker**:
  - Define reduction goals.
  - Create and manage initiatives/action plans.
  - Track progress and year-over-year performance.
- **SEDG Report Generator**: Structured SEDG v2 disclosure workflow with PDF generation.
- **ESG Ready Questionnaire**: Multi-section ESG readiness assessment with persistence and downloadable report.
- **Document Requests**: Inter-company document request workflow (request, approve/upload, reject/cancel).
- **COSIRI Documents**: Upload, browse, filter, download, and manage company documents.
- **Administration**:
  - Admin panel with system statistics and recent activity.
  - Pending company verification review/approval.
  - User management and company management modules.

## Tech Stack
- **Frontend/App**: Streamlit
- **Data and charts**: pandas, Plotly
- **Database**: MySQL (`mysql-connector-python`)
- **Reporting**: reportlab (PDF generation)
- **Utilities**: python-dotenv, geopy

## Emission Sources & Methodology
- **Primary default source**: The baseline system emission factors are seeded by `scripts/setup_ghg_factors.py`, which documents and loads values based on **UK Government Greenhouse Gas Reporting: Conversion Factors 2025**.
- **Schema alignment**: Factors are organized into Scope 1, Scope 2, and Scope 3 categories aligned with GHG Protocol in `docs/7_GHG_Protocol_Schema.md`.
- **Coverage examples**: Fuel combustion, refrigerants/fugitive emissions, purchased electricity/heat, business travel, transport, waste, and other value-chain activities.
- **Custom company factors**: Managers/admins can create company-specific custom sources in `app/pages/06_⚙️_Manage_Emission_Factors.py`.
- **Traceability fields**: The emission source model supports `data_source_reference`, `reference_year`, versioning, and history (`scripts/migrate_emission_factors.py`) to track where a factor came from and when it changed.
- **Practical note**: You should periodically review and update factors for your jurisdiction and reporting year if local/national factors are preferred over UK defaults.

## Quickstart
The commands below are for Windows PowerShell and assume you are inside the project folder (`Sustainability-Monitoring-Hub-202602`).

1. **Prerequisites**
	- git
	- Python 3.10+ (tested with 3.13)
	- MySQL 8.x, installed and running
2. **Create a virtual environment and install dependencies**
	```powershell
	python -m venv venv
	.\venv\Scripts\Activate.ps1
	pip install -r requirements.txt
	```
	- Your prompt should now start with `(venv)`.
	- If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.
	- In Command Prompt (cmd), activate with `venv\Scripts\activate.bat` instead.
3. **Create `.env` in the project root**
	```powershell
	copy .env.example .env
	```
	Open `.env` and set `DB_USER` and `DB_PASSWORD` to your MySQL credentials. `DB_NAME` can be any name; `setup_db.py` creates the database if it does not exist.
	```bash
	ENVIRONMENT=development
	SECRET_KEY=change-me

	DB_HOST=127.0.0.1
	DB_PORT=3306
	DB_NAME=ghg_emissions_calculator_db
	DB_USER=root
	DB_PASSWORD=your-password
	DB_SSL_DISABLED=true

	# optional
	DEBUG=False
	SESSION_TIMEOUT=3600
	```
4. **Initialize the database (first time only)**
	```powershell
	python scripts\setup_db.py              # creates the database, all 16 tables and default logins
	python scripts\setup_ghg_factors.py     # loads 150+ UK Gov 2025 emission factors
	python scripts\test_db_connection.py    # optional: verify the connection
	python scripts\setup_test_users.py      # optional: one test user per role
	```
	- Both setup scripts are safe to re-run: they only add missing data. On a re-run, `setup_ghg_factors.py` prints `Duplicate entry` errors for factors that already exist; these are expected and the script reports them as skipped.
	- Do **not** pass `--clear` to `setup_ghg_factors.py` unless you intend to delete all emission factors **and all emissions data**.
	- `scripts/create_reduction_tables.py` is not needed; `setup_db.py` already creates the Roadmap Tracker tables.
5. **Run the app**
	```powershell
	python -m streamlit run app/main.py
	```
	Open http://localhost:8501 and log in with one of the default accounts below.

### Default logins
| Username | Password | Role | Created by |
|---|---|---|---|
| `admin` | `admin123` | admin | `setup_db.py` |
| `demouser` | `demo123` | manager | `setup_db.py` |
| `testadmin` | `admin123` | admin | `setup_test_users.py` |
| `testmanager` | `manager123` | manager | `setup_test_users.py` |
| `testuser` | `user123` | normal_user | `setup_test_users.py` |

All default accounts belong to **Test Company Ltd** (`TEST001`). Change or remove them before deploying anywhere public.

### Running it again later
After the first-time setup, you only need to activate the environment and start the app:
```powershell
cd C:\path\to\Sustainability-Monitoring-Hub-202602
.\venv\Scripts\Activate.ps1
python -m streamlit run app/main.py
```

### Upgrading an existing database
`setup_db.py` only creates tables that don't exist yet; it never adds new columns to existing tables. If your database was created with an older version of the project, run these migrations (both are safe to run more than once):
```powershell
python verify_and_migrate_baseline.py             # adds companies.baseline_year (+ notes, set date, set by)
python scripts\migrate_cosiri_file_content.py      # adds cosiri_documents.file_content for COSIRI uploads
```

### Troubleshooting
- **`Access denied for user 'root'@'localhost'`**: the MySQL credentials don't match. Make sure `.env` is saved, then check the password with `mysql -u root -p`. Also check that `DB_PASSWORD` isn't already set in your terminal (`$env:DB_PASSWORD` in PowerShell): values already in the environment take priority over `.env`. If it is set, open a new terminal.
- **`ModuleNotFoundError`**: the virtual environment isn't active. Activate it (step 2) and try again.
- **Port 8501 already in use**: another Streamlit instance is running. Stop it, or run with `--server.port 8502`.
- **`Unknown column ... in 'field list'`** in the terminal: your database is older than the code. See [Upgrading an existing database](#upgrading-an-existing-database).
- **`Please replace use_container_width with width`**: a harmless deprecation warning from Streamlit; the app works normally.

## Main Streamlit Pages
- `app/main.py` (entry/auth routing)
- `app/pages/01_🏠_Dashboard.py`
- `app/pages/02_➕_Add_Activity.py`
- `app/pages/03_📊_View_Data.py`
- `app/pages/04_✅_Verify_Data.py`
- `app/pages/05_🎯_Roadmap_Tracker.py`
- `app/pages/06_⚙️_Manage_Emission_Factors.py`
- `app/pages/07_📋_SEDG_Disclosure.py`
- `app/pages/08_📝_ESG_Ready_Questionnaire.py`
- `app/pages/09_📄_COSIRI.py`
- `app/pages/10_📤_Document_Requests.py`
- `app/pages/11_⚙️_Admin_Panel.py`
- `app/pages/12_👥_User_Management.py`
- `app/pages/13_🏢_Company_Management.py`

## Notes
- The app title is **Sustainability Monitoring Hub** (`app/main.py`).
- Most pages enforce company assignment/verification and role-based access before usage.
- Reporting and verification workflows are integrated with cache-backed data access for performance.
- Default factor dataset is bootstrapped via `python scripts/setup_ghg_factors.py`; you can then refine with custom factors per company.
- `setup_db.py` also seeds a few sample categories (e.g. `S1-01`, `S2-01`) that overlap with the fuller set from `setup_ghg_factors.py` (e.g. `S1-FUEL`, `S2-ELECTRICITY`), so some category names such as "Business Travel" appear twice in dropdowns.
- Passwords are stored as unsalted SHA-256 hashes. This is fine for local development; switch to bcrypt/argon2 before production use.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.