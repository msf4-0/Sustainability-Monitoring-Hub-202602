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
- **Custom company factors**: Managers/admins can create company-specific custom sources in `app/pages/11_⚙️_Manage_Emission_Factors.py`.
- **Traceability fields**: The emission source model supports `data_source_reference`, `reference_year`, versioning, and history (`scripts/migrate_emission_factors.py`) to track where a factor came from and when it changed.
- **Practical note**: You should periodically review and update factors for your jurisdiction and reporting year if local/national factors are preferred over UK defaults.

## Quickstart
1. **Prerequisites**
	- git
	- Python 3.12 (recommended; 3.14 is not supported by this dependency set) or 3.10+
	- Docker Desktop (for the bundled database) **or** a native MySQL 8.x / MariaDB 11.x server
2. **Install dependencies**
	```bash
	python -m venv venv
	venv\Scripts\activate
	pip install -r requirements.txt
	```
3. **Create `.env` in project root** (see `.env.example`)
	```bash
	DB_HOST=127.0.0.1
	DB_PORT=3306
	DB_USER=root
	DB_PASSWORD=admin123
	DB_NAME=ghg_emissions_calculator_db
	SECRET_KEY=replace_me
	ENVIRONMENT=development
	DEBUG=True
	SESSION_TIMEOUT=3600
	```
	> With the bundled Docker database, `DB_PASSWORD` is also used as the MariaDB
	> root password, so keep the two in sync.
4. **Start the database** (bundled Docker option)
	```bash
	docker compose up -d
	```
	Skip this step if you already run MySQL/MariaDB natively.
5. **Initialize database and baseline data**
	```bash
	python scripts/bootstrap.py
	```
	`bootstrap.py` waits for the database, then creates the database if it does
	not already exist (`CREATE DATABASE IF NOT EXISTS`), creates the schema
	(`setup_db.py`), seeds GHG factors (`setup_ghg_factors.py`), and repairs any
	polluted JSON rows (`repair_json_persistence.py`).
	Optional: `python scripts/setup_test_users.py`

	> **Note:** step 4 (or a native server) must already be running. The scripts
	> create the *database* automatically, but they cannot start a *server*. With
	> the bundled Docker option, Compose creates both the server and the database
	> (via `MARIADB_DATABASE`) on first boot.
6. **Run app**
	```bash
	python -m streamlit run app/main.py
	```

### Running the steps individually
```bash
python scripts/setup_db.py                 # create schema + seed base data
python scripts/setup_ghg_factors.py        # seed GHG scopes/categories/sources
python scripts/repair_json_persistence.py  # clean polluted SEDG/ESG JSON rows
python scripts/repair_json_persistence.py --dry-run   # preview only
```

### Database maintenance
If the SEDG Disclosure or ESG Ready Questionnaire pages report that data was
not loaded even though responses exist, run the repair script above. Older
versions persisted internal change-tracking keys inside the response JSON,
which bloated rows and corrupted state on load. The repair is idempotent, so
it is safe to run at any time (including on already-clean data).

You do **not** need to reinstall or wipe anything to apply application fixes.
Pull the branch, run the repair script, and restart the app.

### Backup and restore
The database lives in the Docker named volume `smh_mariadb_data`.

```powershell
# Back up (dump inside the container, then copy out to avoid shell encoding issues)
docker exec smh-db sh -c 'mariadb-dump -uroot -padmin123 --databases ghg_emissions_calculator_db > /tmp/backup.sql'
docker cp smh-db:/tmp/backup.sql .\smh_backup.sql

# Restore
docker cp .\smh_backup.sql smh-db:/tmp/backup.sql
docker exec smh-db sh -c 'mariadb -uroot -padmin123 < /tmp/backup.sql'
```

### Resetting / clean reinstall
⚠️ This deletes **all** data. Back up first (see above).

```powershell
# Stop and remove the container; the named volume is kept
docker compose down

# Remove the data volume (the destructive step)
docker volume rm smh_mariadb_data
# or, in one command: docker compose down -v

# Rebuild from scratch
docker compose up -d
$env:PYTHONUTF8=1
.\venv\Scripts\python.exe scripts\bootstrap.py
```

If `docker volume rm` reports the volume is in use, ensure no other container is
attached. If it reports the volume was created outside Compose, that is expected
for a pre-existing volume and the removal still works once the container is down.

## Main Streamlit Pages
- `app/main.py` (entry/auth routing)
- `app/pages/01_🏠_Dashboard.py`
- `app/pages/02_➕_Add_Activity.py`
- `app/pages/03_📊_View_Data.py`
- `app/pages/04_✅_Verify_Data.py`
- `app/pages/05_⚙️_Admin_Panel.py`
- `app/pages/06_👥_User_Management.py`
- `app/pages/07_🏢_Company_Management.py`
- `app/pages/08_📋_SEDG_Disclosure.py`
- `app/pages/09_📝_ESG_Ready_Questionnaire.py`
- `app/pages/10_📤_Document_Requests.py`
- `app/pages/11_⚙️_Manage_Emission_Factors.py`
- `app/pages/12_📄_COSIRI.py`
- `app/pages/13_🎯_Roadmap_Tracker.py`

## Notes
- The app title is now **Sustainability Monitoring Hub** (`app/main.py`).
- Most pages enforce company assignment/verification and role-based access before usage.
- Reporting and verification workflows are integrated with cache-backed data access for performance.
- Default factor dataset is bootstrapped via `python scripts/setup_ghg_factors.py`; you can then refine with custom factors per company.

## Other beginner notes
- When using Command Prompt (cmd) to start the application
- Change directory first
```bash
"cd c:\Users\YOUR_USERNAME\YOUR_FOLDER_PATH\Sustainability-Monitoring-Hub-202602"
```
- Start the virtual environment
```bash
"c:\Users\YOUR_USERNAME\YOUR_FOLDER_PATH\Sustainability-Monitoring-Hub-202602\venv\Scripts\activate.bat"
```
- Then run the app
```bash
python -m streamlit run app/main.py
```