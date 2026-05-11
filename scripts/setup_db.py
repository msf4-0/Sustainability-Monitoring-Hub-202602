"""
Database Setup Script
Creates all tables for GHG Calculator
Run this ONCE to initialize your database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from mysql.connector import Error
from config.settings import config

class DatabaseSetup:
    def __init__(self):
        self.connection = None
        self.db_config = config.database_config.copy()
        # Remove database from config for initial connection
        self.db_name = self.db_config.pop('database')
    
    def connect(self):
        """Connect to MySQL server (without database)"""
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            print("✅ Connected to MySQL server")
            return True
        except Error as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("✅ Disconnected from MySQL server")
    
    def execute_query(self, query, params=None):
        """Execute a query"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            cursor.close()
            return True
        except Error as e:
            print(f"❌ Query failed: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def create_database(self):
        """Create database if not exists"""
        print(f"\n📁 Creating database: {self.db_name}")
        query = f"CREATE DATABASE IF NOT EXISTS {self.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        if self.execute_query(query):
            print(f"✅ Database '{self.db_name}' ready")
            # Switch to the database
            self.execute_query(f"USE {self.db_name}")
            return True
        return False
    
    def create_tables(self):
        """Create all tables"""
        print("\n📋 Creating tables...")
        
        tables = {
            'companies': """
                CREATE TABLE IF NOT EXISTS companies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_name VARCHAR(255) UNIQUE NOT NULL,
                    company_code VARCHAR(50) UNIQUE NOT NULL,
                    industry_sector VARCHAR(100) NULL,
                    address TEXT NULL,
                    latitude DECIMAL(10, 8) NULL COMMENT 'Latitude coordinate for company location',
                    longitude DECIMAL(11, 8) NULL COMMENT 'Longitude coordinate for company location',
                    contact_email VARCHAR(255) NULL,
                    contact_phone VARCHAR(50) NULL,
                    verification_status ENUM('pending', 'verified', 'rejected') DEFAULT 'pending',
                    verification_date DATETIME NULL,
                    verified_by INT NULL,
                    baseline_year INT DEFAULT NULL COMMENT 'The year designated as the reference point for emissions comparisons',
                    baseline_notes TEXT DEFAULT NULL COMMENT 'Notes about why this baseline year was chosen',
                    baseline_set_date DATE DEFAULT NULL COMMENT 'When the baseline year was designated',
                    baseline_set_by INT DEFAULT NULL COMMENT 'User ID who set the baseline year',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_companies_status (verification_status),
                    INDEX idx_companies_code (company_code),
                    INDEX idx_companies_location (latitude, longitude),
                    INDEX idx_companies_baseline_year (baseline_year)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'manager', 'normal_user') DEFAULT 'normal_user',
                    company_id INT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_login DATETIME NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_users_company (company_id),
                    INDEX idx_users_email (email),
                    CONSTRAINT fk_users_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ghg_scopes': """
                CREATE TABLE IF NOT EXISTS ghg_scopes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    scope_number INT UNIQUE NOT NULL,
                    scope_name VARCHAR(100) NOT NULL,
                    description TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ghg_categories': """
                CREATE TABLE IF NOT EXISTS ghg_categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    scope_id INT NOT NULL,
                    category_code VARCHAR(50) UNIQUE NULL,
                    category_name VARCHAR(200) NOT NULL,
                    description TEXT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (scope_id) REFERENCES ghg_scopes(id) ON DELETE RESTRICT,
                    INDEX idx_categories_scope (scope_id),
                    INDEX idx_categories_code (category_code)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ghg_emission_sources': """
                CREATE TABLE IF NOT EXISTS ghg_emission_sources (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    category_id INT NOT NULL,
                    source_code VARCHAR(50) UNIQUE NULL,
                    source_name VARCHAR(200) NOT NULL,
                    emission_factor DECIMAL(15,8) NOT NULL,
                    unit VARCHAR(50) NOT NULL,
                    description TEXT NULL,
                    region VARCHAR(50) DEFAULT 'UK',
                    source_reference VARCHAR(255) NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    source_type ENUM('system', 'custom') DEFAULT 'system',
                    company_id INT NULL,
                    is_visible_in_ui BOOLEAN DEFAULT TRUE,
                    data_source_reference VARCHAR(500) NULL,
                    version INT DEFAULT 1,
                    superseded_by INT NULL,
                    reference_year INT NULL COMMENT 'Year of the emission factor reference/publication',
                    FOREIGN KEY (category_id) REFERENCES ghg_categories(id) ON DELETE RESTRICT,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (superseded_by) REFERENCES ghg_emission_sources(id) ON DELETE SET NULL,
                    INDEX idx_sources_category (category_id),
                    INDEX idx_sources_code (source_code),
                    INDEX idx_sources_active (is_active),
                    INDEX idx_reference_year (reference_year)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'emissions_data': """
                CREATE TABLE IF NOT EXISTS emissions_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    user_id INT NOT NULL,
                    emission_source_id INT NOT NULL,
                    reporting_period VARCHAR(20) NOT NULL,
                    activity_data DECIMAL(15,4) NOT NULL,
                    emission_factor DECIMAL(15,8) NOT NULL,
                    co2_equivalent DECIMAL(15,4) NOT NULL,
                    data_source VARCHAR(255) NULL,
                    calculation_method VARCHAR(100) NULL,
                    verification_status ENUM('unverified', 'verified', 'rejected') NOT NULL DEFAULT 'unverified',
                    verified_by INT NULL,
                    verified_at DATETIME NULL,
                    notes TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
                    FOREIGN KEY (emission_source_id) REFERENCES ghg_emission_sources(id) ON DELETE RESTRICT,
                    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_emissions_company (company_id),
                    INDEX idx_emissions_period (reporting_period),
                    INDEX idx_emissions_source (emission_source_id),
                    INDEX idx_emissions_status (verification_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'cosiri_documents': """
                CREATE TABLE IF NOT EXISTS cosiri_documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    uploaded_by INT NOT NULL,
                    document_type ENUM('report', 'certificate') NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    file_size INT NULL,
                    mime_type VARCHAR(100) NULL,
                    reporting_period VARCHAR(20) NULL,
                    notes TEXT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT,
                    INDEX uploaded_by (uploaded_by),
                    INDEX idx_cosiri_company (company_id),
                    INDEX idx_cosiri_type (document_type),
                    INDEX idx_cosiri_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,

            'document_requests': """
                CREATE TABLE IF NOT EXISTS document_requests (
                    request_id INT AUTO_INCREMENT PRIMARY KEY,
                    from_company_id INT NOT NULL,
                    to_company_id INT NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    request_note TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    pdf_filename VARCHAR(255),
                    pdf_data MEDIUMBLOB,
                    rejection_reason TEXT,
                    request_date DATETIME NOT NULL,
                    completed_date DATETIME,
                    FOREIGN KEY (from_company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    INDEX idx_from_company (from_company_id),
                    INDEX idx_to_company (to_company_id),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,

            'ghg_source_history': """
                CREATE TABLE IF NOT EXISTS ghg_source_history (
                    history_id INT AUTO_INCREMENT PRIMARY KEY,
                    source_id INT NOT NULL,
                    emission_factor DECIMAL(15,8) NOT NULL,
                    changed_by INT NOT NULL,
                    changed_at DATETIME NOT NULL,
                    change_reason TEXT,
                    FOREIGN KEY (source_id) REFERENCES ghg_emission_sources(id) ON DELETE CASCADE,
                    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE RESTRICT,
                    INDEX idx_source (source_id),
                    INDEX idx_changed_at (changed_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'reduction_goals': """
                CREATE TABLE IF NOT EXISTS reduction_goals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    baseline_year INT NOT NULL,
                    baseline_emissions DECIMAL(15,2) NOT NULL COMMENT 'Baseline emissions in tonnes CO2e',
                    target_year INT NOT NULL,
                    target_reduction_percentage DECIMAL(5,2) NOT NULL COMMENT 'Target reduction percentage',
                    framework VARCHAR(100) NULL COMMENT 'e.g., SBTi, Net Zero, Paris Agreement',
                    description TEXT COMMENT 'Additional details about the goal',
                    status ENUM('active', 'inactive', 'achieved') DEFAULT 'active',
                    created_by INT NULL COMMENT 'User ID who created this goal',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_company_status (company_id, status),
                    INDEX idx_target_year (target_year)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Company emission reduction goals'
            """,
            #) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Company emission reduction goals'
            
            'reduction_initiatives': """
                CREATE TABLE IF NOT EXISTS reduction_initiatives (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    initiative_name VARCHAR(255) NOT NULL,
                    description TEXT COMMENT 'Detailed description and implementation plan',
                    target_goal TEXT,
                    target_scopes VARCHAR(100) NULL COMMENT 'Comma-separated scopes (e.g., Scope 1,Scope 2)',
                    expected_reduction DECIMAL(15,2) NULL COMMENT 'Expected annual CO2e reduction in tonnes',
                    actual_reduction DECIMAL(15,2) NULL COMMENT 'Actual achieved reduction in tonnes',
                    estimated_cost DECIMAL(15,2) NULL COMMENT 'Estimated implementation cost',
                    actual_cost DECIMAL(15,2) NULL COMMENT 'Actual cost incurred',
                    status ENUM('Planned', 'In Progress', 'Completed', 'On Hold', 'Cancelled') DEFAULT 'Planned',
                    start_date DATE NULL COMMENT 'Initiative start date',
                    target_completion_date DATE NULL COMMENT 'Target completion date',
                    actual_completion_date DATE NULL COMMENT 'Actual completion date',
                    responsible_person VARCHAR(255) NULL COMMENT 'Person or department responsible',
                    created_by INT NULL COMMENT 'User ID who created this initiative',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    progress_type VARCHAR(50) DEFAULT 'percentage' COMMENT 'Type of progress tracking: percentage, checklist, or numeric',
                    target_value DECIMAL(10,2) NULL COMMENT 'Target value for numeric or checklist progress (e.g., 100 for percentage, 10 for checklist items)',
                    current_progress DECIMAL(10,2) DEFAULT 0.00 COMMENT 'Current progress value (percentage, items completed, or custom metric)',
                    progress_notes TEXT COMMENT 'Notes about recent progress updates',
                    last_progress_update TIMESTAMP NULL COMMENT 'Timestamp of last progress update',
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_company_status (company_id, status),
                    INDEX idx_dates (start_date, target_completion_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Emission reduction initiatives and action plans'
            """,
            #) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Emission reduction initiatives and action plans'
            
            'initiative_progress': """
                CREATE TABLE IF NOT EXISTS initiative_progress (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    initiative_id INT NOT NULL,
                    progress_date DATE NOT NULL,
                    progress_percentage INT NULL COMMENT 'Completion percentage (0-100)',
                    notes TEXT COMMENT 'Progress update notes',
                    actual_reduction_to_date DECIMAL(15,2) NULL COMMENT 'Cumulative reduction achieved',
                    cost_to_date DECIMAL(15,2) NULL COMMENT 'Cumulative cost incurred',
                    created_by INT NULL COMMENT 'User ID who logged this update',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (initiative_id) REFERENCES reduction_initiatives(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX created_by (created_by),
                    INDEX idx_initiative_date (initiative_id, progress_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Progress tracking for reduction initiatives'
            """,
            #) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Progress tracking for reduction initiatives'
            
            'initiative_documents': """
                CREATE TABLE IF NOT EXISTS initiative_documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    initiative_id INT NOT NULL,
                    document_name VARCHAR(255) NOT NULL,
                    document_type VARCHAR(50) NULL COMMENT 'e.g., Invoice, Certificate, Report',
                    file_path VARCHAR(500) NULL COMMENT 'Path to stored file',
                    file_url VARCHAR(500) NULL COMMENT 'URL if stored externally',
                    description TEXT,
                    uploaded_by INT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (initiative_id) REFERENCES reduction_initiatives(id) ON DELETE CASCADE,
                    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX uploaded_by (uploaded_by),
                    INDEX idx_initiative (initiative_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Supporting documents for initiatives'
            """,
            #) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Supporting documents for initiatives'
            
            'emissions_coverage': """
                CREATE TABLE IF NOT EXISTS emissions_coverage (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    year INT NOT NULL,
                    scope_number INT NOT NULL COMMENT 'Scope 1, 2, or 3',
                    coverage_percentage DECIMAL(5,2) DEFAULT NULL COMMENT 'Estimated percentage of emissions covered (0-100)',
                    total_expected_sources INT DEFAULT NULL COMMENT 'Total number of emission sources expected',
                    tracked_sources INT DEFAULT NULL COMMENT 'Number of sources actually tracked',
                    notes TEXT COMMENT 'Additional context about coverage for this scope/year',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_company_year_scope (company_id, year, scope_number),
                    INDEX idx_company_year (company_id, year),
                    INDEX idx_scope (scope_number),
                    CONSTRAINT chk_scope_number CHECK (scope_number IN (1, 2, 3))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tracks data coverage evolution over time'
            """,
            
            'sedg_disclosures': """
                CREATE TABLE IF NOT EXISTS sedg_disclosures (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    disclosure_period VARCHAR(20) NOT NULL COMMENT 'e.g., 2024, 2023-2024',
                    reporting_year INT NOT NULL COMMENT 'Year of reporting',
                    status ENUM('draft', 'in_progress', 'completed', 'submitted') DEFAULT 'draft' COMMENT 'Disclosure status',
                    sedg_data JSON COMMENT 'All SEDG disclosure fields stored as JSON (~100 fields)',
                    submission_date DATETIME NULL COMMENT 'When disclosure was officially submitted',
                    last_modified_by INT NULL COMMENT 'User ID who last edited this disclosure',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (last_modified_by) REFERENCES users(id) ON DELETE SET NULL,
                    UNIQUE KEY unique_company_period (company_id, disclosure_period),
                    INDEX idx_company_status (company_id, status),
                    INDEX idx_updated (updated_at),
                    INDEX idx_year (reporting_year)
                ) ENGINE=InnoDB ROW_FORMAT=COMPRESSED DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SEDG v2 disclosure forms with multi-session edit support'
            """,
            
            'iesg_responses': """
                CREATE TABLE IF NOT EXISTS iesg_responses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_id INT NOT NULL,
                    assessment_period VARCHAR(20) NOT NULL COMMENT 'e.g., 2024, 2023-2024',
                    status ENUM('draft', 'in_progress', 'completed', 'submitted') DEFAULT 'draft' COMMENT 'Response status',
                    response_data JSON COMMENT 'All ESG questionnaire response fields stored as JSON (~50 fields)',
                    completion_score INT NULL COMMENT 'Completion percentage (0-100)',
                    esg_readiness_score INT NULL COMMENT 'ESG readiness score calculated from responses',
                    submission_date DATETIME NULL COMMENT 'When responses were officially submitted',
                    last_modified_by INT NULL COMMENT 'User ID who last edited these responses',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (last_modified_by) REFERENCES users(id) ON DELETE SET NULL,
                    UNIQUE KEY unique_company_assessment (company_id, assessment_period),
                    INDEX idx_company_status (company_id, status),
                    INDEX idx_updated (updated_at),
                    INDEX idx_score (esg_readiness_score)
                ) ENGINE=InnoDB ROW_FORMAT=COMPRESSED DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ESG Ready questionnaire responses with multi-session edit support'
            """
        }
        
        # Create tables in dependency order
        for table_name, table_query in tables.items():
            print(f"  Creating table: {table_name}...", end=" ")
            if self.execute_query(table_query):
                print("✅")
            else:
                print("❌")
                return False
        
        return True
    
    def seed_initial_data(self):
        """Insert initial reference data"""
        print("\n🌱 Seeding initial data...")
        
        # Insert GHG Scopes
        print("  Inserting GHG scopes...", end=" ")
        scopes_query = """
            INSERT IGNORE INTO ghg_scopes (scope_number, scope_name, description) VALUES
            (1, 'Scope 1: Direct Emissions', 'Direct GHG emissions from sources owned or controlled by the company'),
            (2, 'Scope 2: Indirect Emissions (Energy)', 'Indirect GHG emissions from purchased electricity, heat, or steam'),
            (3, 'Scope 3: Other Indirect Emissions', 'All other indirect emissions in the value chain')
        """
        if self.execute_query(scopes_query):
            print("✅")
        else:
            print("❌")
            return False
        
        # Insert sample categories for each scope
        print("  Inserting GHG categories...", end=" ")
        categories_query = """
            INSERT IGNORE INTO ghg_categories (scope_id, category_code, category_name, description) VALUES
            -- Scope 1 categories
            (1, 'S1-01', 'Stationary Combustion', 'Emissions from stationary fuel combustion sources'),
            (1, 'S1-02', 'Mobile Combustion', 'Emissions from mobile fuel combustion sources'),
            (1, 'S1-03', 'Process Emissions', 'Emissions from industrial processes'),
            (1, 'S1-04', 'Fugitive Emissions', 'Intentional and unintentional releases'),
            -- Scope 2 categories
            (2, 'S2-01', 'Purchased Electricity', 'Electricity purchased from the grid'),
            (2, 'S2-02', 'Purchased Heat/Steam/Cooling', 'Purchased thermal energy'),
            -- Scope 3 categories (examples)
            (3, 'S3-01', 'Purchased Goods and Services', 'Upstream emissions from purchased goods'),
            (3, 'S3-06', 'Business Travel', 'Employee business travel'),
            (3, 'S3-07', 'Employee Commuting', 'Employee commuting to work')
        """
        if self.execute_query(categories_query):
            print("✅")
        else:
            print("❌")
            return False
        
        # Insert sample emission sources
        print("  Inserting emission sources...", end=" ")
        sources_query = """
            INSERT IGNORE INTO ghg_emission_sources 
            (category_id, source_code, source_name, emission_factor, unit, description, region, reference_year) VALUES
            -- Stationary Combustion (S1-01)
            ((SELECT id FROM ghg_categories WHERE category_code = 'S1-01'), 'S1-01-01', 'Natural Gas', 0.18385000, 'kg CO2e/kWh', 'Natural gas combustion in boilers and furnaces', 'UK', 2024),
            ((SELECT id FROM ghg_categories WHERE category_code = 'S1-01'), 'S1-01-02', 'Coal', 0.34224000, 'kg CO2e/kWh', 'Coal combustion in power generation', 'UK', 2024),
            ((SELECT id FROM ghg_categories WHERE category_code = 'S1-01'), 'S1-01-03', 'LPG', 0.21449000, 'kg CO2e/litre', 'LPG combustion', 'UK', 2024),
            -- Mobile Combustion (S1-02)
            ((SELECT id FROM ghg_categories WHERE category_code = 'S1-02'), 'S1-02-01', 'Petrol Cars', 0.16743000, 'kg CO2e/litre', 'Petrol vehicles', 'UK', 2024),
            ((SELECT id FROM ghg_categories WHERE category_code = 'S1-02'), 'S1-02-02', 'Diesel Cars', 0.16901000, 'kg CO2e/litre', 'Diesel vehicles', 'UK', 2024),
            -- Purchased Electricity (S2-01)
            ((SELECT id FROM ghg_categories WHERE category_code = 'S2-01'), 'S2-01-01', 'Grid Electricity (UK)', 0.19338000, 'kg CO2e/kWh', 'UK national grid electricity', 'UK', 2024),
            ((SELECT id FROM ghg_categories WHERE category_code = 'S2-01'), 'S2-01-02', 'Renewable Electricity', 0.00000000, 'kg CO2e/kWh', 'Certified renewable electricity', 'UK', 2024)
        """
        if self.execute_query(sources_query):
            print("✅")
        else:
            print("❌")
            return False
        
        # Create default admin user (password: admin123)
        print("  Creating default admin user...", end=" ")
        import hashlib
        password = "admin123"
        # Simple hash - in production use bcrypt or similar
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        admin_query = """
            INSERT IGNORE INTO users (username, email, password_hash, role, is_active) VALUES
            ('admin', 'admin@ghgcalc.com', %s, 'admin', TRUE)
        """
        if self.execute_query(admin_query, (password_hash,)):
            print("✅")
            print("      Username: admin")
            print("      Password: admin123")
        else:
            print("⏭️  (already exists)")
        
        # Create sample company
        print("  Creating sample company...", end=" ")
        company_query = """
            INSERT INTO companies 
            (company_name, company_code, industry_sector, address, contact_email, verification_status) VALUES
            ('Test Company Ltd', 'TEST001', 'Technology', '456 Test Street, London, UK', 'contact@testcompany.com', 'verified')
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
        """
        if self.execute_query(company_query):
            print("✅")
            print("      Company: Test Company Ltd")
            print("      Code: TEST001")
        else:
            print("⏭️  (already exists)")

        # Ensure admin is always associated with Test Company Ltd
        print("  Linking admin user to company...", end=" ")
        admin_company_query = """
            UPDATE users
            SET company_id = (SELECT id FROM companies WHERE company_code = 'TEST001' LIMIT 1)
            WHERE username = 'admin'
        """
        if self.execute_query(admin_company_query):
            print("✅")
        else:
            print("❌")
            return False
        
        # Create sample user associated with the company
        print("  Creating sample company user...", end=" ")
        sample_password_hash = hashlib.sha256("demo123".encode()).hexdigest()
        
        sample_user_query = """
            INSERT IGNORE INTO users (username, email, password_hash, role, company_id, is_active) VALUES
            ('demouser', 'user@demomfg.com', %s, 'manager', 
               (SELECT id FROM companies WHERE company_code = 'TEST001'), TRUE)
        """
        if self.execute_query(sample_user_query, (sample_password_hash,)):
            print("✅")
            print("      Username: demouser")
            print("      Password: demo123")
            print("      Role: manager")
        else:
            print("⏭️  (already exists)")
        
        return True
    
    def run_setup(self):
        """Run complete database setup"""
        print("=" * 60)
        print("🚀 GHG Calculator - Database Setup")
        print("=" * 60)
        print(f"Database: {self.db_name}")
        print(f"Host: {self.db_config['host']}")
        print("=" * 60)
        
        if not self.connect():
            return False
        
        try:
            # Create database
            if not self.create_database():
                return False
            
            # Create tables
            if not self.create_tables():
                return False
            
            # Seed initial data
            if not self.seed_initial_data():
                return False
            
            print("\n" + "=" * 60)
            print("🎉 Database setup completed successfully!")
            print("=" * 60)
            print("\n📝 Next steps:")
            print("  1. Run: streamlit run app/main.py")
            print("  2. Login with: admin / admin123")
            print("  3. Change admin password immediately!")
            print("\n📊 Database includes:")
            print("  - 16 tables created")
            print("  - SEDG v2 Disclosure form with multi-session persistence")
            print("  - ESG Ready Questionnaire with multi-session persistence")
            print("  - Baseline year tracking for companies")
            print("  - Emissions coverage tracking over time")
            print("  - GHG Scopes (1, 2, 3)")
            print("  - Sample emission categories and sources")
            print("  - Reduction goals and initiatives tracking")
            print("  - Document management system")
            print("\n")
            
            return True
            
        finally:
            self.disconnect()

def main():
    """Main function"""
    setup = DatabaseSetup()
    success = setup.run_setup()
    
    if success:
        print("✅ Setup completed successfully")
        return 0
    else:
        print("❌ Setup failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())