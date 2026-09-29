"""
SEDG Disclosure Management - Efficient load/save with persistence
Handles multi-session editing with debounced auto-save
"""
import streamlit as st
import json
from datetime import datetime
from core.database import DatabaseManager
import logging

logger = logging.getLogger(__name__)

# Performance tunables
SAVE_INTERVAL = 5  # seconds - save after 5 sec of inactivity

# Every SEDG form field and its default value (session keys are these names
# prefixed with 'sedg_'). Only these fields, plus the disclosure period, are
# ever saved to or loaded from the database, so page state such as the
# change-tracking snapshot can never leak into sedg_data.
SEDG_DEFAULTS = {
    # General Information
    'entities_included': '',
    'locations_included': '',
    
    # E1.1-E1.2 - GHG (auto-filled from system)
    # E1.3-E1.4 - GHG Reduction
    'e13_scope1_reduction': 0.0,
    'e14_scope2_reduction': 0.0,
    # E1.5 - Scope 3 Total
    'e15_scope3_total': 0.0,
    # E1.6 - Scope 3 Reduction
    'e16_scope3_reduction': 0.0,
    # E1.7 - GHG Intensity
    'e17_intensity': 0.0,
    
    # E2.1 - Energy Consumption (Basic)
    'e21_renewable': 0.0,
    'e21_nonrenewable': 0.0,
    'e21_electricity': 0.0,
    'e21_heating': 0.0,
    'e21_cooling': 0.0,
    'e21_steam': 0.0,
    
    # E2.2 - Energy Consumption Reduction (Intermediate)
    'e22_renewable_reduction': 0.0,
    'e22_nonrenewable_reduction': 0.0,
    'e22_electricity_reduction': 0.0,
    'e22_heating_reduction': 0.0,
    'e22_cooling_reduction': 0.0,
    'e22_steam_reduction': 0.0,
    
    # E3.1 - Total Water Withdrawn (Basic)
    'e31_purchased': 0.0,
    'e31_surface': 0.0,
    'e31_ground': 0.0,
    'e31_sea': 0.0,
    'e31_produced': 0.0,
    
    # E3.2 - Water Reduction (Intermediate)
    'e32_reduction': 0.0,
    
    # E4.1 - Total Waste (Basic)
    'e41_generated': 0.0,
    'e41_diverted': 0.0,
    'e41_disposed': 0.0,
    
    # E4.2 - Waste Breakdown (Intermediate)
    'e42_haz_gen': 0.0,
    'e42_haz_div': 0.0,
    'e42_haz_disp': 0.0,
    'e42_nonhaz_gen': 0.0,
    'e42_nonhaz_div': 0.0,
    'e42_nonhaz_disp': 0.0,
    'e42_sector_gen': 0.0,
    'e42_sector_div': 0.0,
    'e42_sector_disp': 0.0,
    'e42_material_gen': 0.0,
    'e42_material_div': 0.0,
    'e42_material_disp': 0.0,
    
    # E4.3 - Waste Diversion Methods (Advanced)
    'e43_haz_reuse': 0.0,
    'e43_haz_recycle': 0.0,
    'e43_haz_recovery': 0.0,
    'e43_nonhaz_reuse': 0.0,
    'e43_nonhaz_recycle': 0.0,
    'e43_nonhaz_recovery': 0.0,
    
    # E4.4 - Waste Disposal Methods (Advanced)
    'e44_haz_incin_recovery': 0.0,
    'e44_haz_incin_no_recovery': 0.0,
    'e44_haz_landfill': 0.0,
    'e44_haz_other': 0.0,
    'e44_nonhaz_incin_recovery': 0.0,
    'e44_nonhaz_incin_no_recovery': 0.0,
    'e44_nonhaz_landfill': 0.0,
    'e44_nonhaz_other': 0.0,
    
    # E5.1 - Materials (Basic)
    'e51_materials': '',
    # E5.2 - Recycled Materials (Advanced)
    'e52_recycled_pct': 0.0,
    
    # S1.1 - Child & Forced Labour Incidents (Basic)
    's11_child_incidents': 0,
    's11_child_nature': '',
    's11_forced_incidents': 0,
    's11_forced_nature': '',
    
    # S1.2 - Risk of Child & Forced Labour (Intermediate)
    's12_child_risk_ops': '',
    's12_forced_risk_ops': '',
    
    # S2.1 - Training (Basic)
    's21_training_hours': 0.0,
    
    # S2.2 - Employee Data (Intermediate)
    's22_num_employees': 0,
    's22_turnover': 0.0,
    
    # S2.3 - Minimum Wage (Basic)
    's23_min_wage_pct': 0.0,
    
    # S3.1 - Diversity - Employees (Basic)
    's31_emp_female': 0.0,
    's31_emp_age': '',
    
    # S3.2 - Diversity - Directors (Intermediate)
    's32_dir_female': 0.0,
    's32_dir_age': '',
    
    # S4.1 - Health & Safety Incidents (Basic)
    's41_fatalities': 0,
    's41_injuries': 0,
    
    # S4.2 - H&S Training (Intermediate)
    's42_hs_trained_num': 0,
    's42_hs_trained_pct': 0.0,
    
    # S5.1 - Community Investment (Basic)
    's51_community_invest': 0.0,
    
    # S5.2 - Community Impact (Advanced)
    's52_negative_impact': '',
    
    # G1.1 - Board Composition (Basic)
    'g11_num_directors': 0,
    
    # G1.2 - Governance Structure (Intermediate)
    'g12_structure': '',
    
    # G2.1 - Policies (Basic)
    'g21_policies': '',
    
    # G3.1 - Audit (Basic)
    'g31_audit_year': datetime.now().year,
    
    # G3.2 - Operations Risks (Intermediate)
    'g32_ops_risks': '',
    
    # G3.3 - Sustainability Risks (Advanced)
    'g33_sustain_risks': '',
    
    # G4.1 - Corruption Incidents (Basic)
    'g41_corrupt_incidents': 0,
    'g41_corrupt_nature': '',
    
    # G4.2 - Anti-corruption Training (Intermediate)
    'g42_anticorrupt_num': 0,
    'g42_anticorrupt_pct': 0.0,
    
    # G4.3 - Corruption Risks (Advanced)
    'g43_corrupt_risks': '',
    
    # G5.1 - Privacy (Intermediate)
    'g51_privacy_complaints': 0,
    'g51_privacy_nature': '',
}


def default_sedg_value(field: str):
    """Return the default value for an SEDG form field."""
    return SEDG_DEFAULTS[field]


class SEDGManager:
    """Manages SEDG disclosure persistence and auto-save"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.unsaved_indicator = "⚠️ Unsaved changes"
        self.saved_indicator = "✅ Saved"
    
    @staticmethod
    def load_sedg_form(company_id: int, disclosure_period: str):
        """
        Load existing SEDG disclosure from database.

        Not cached: a cached result would hide responses saved by other
        sessions until the cache expired.

        Args:
            company_id: Company ID
            disclosure_period: Reporting period (e.g., '2024', '2023-2024')
        
        Returns:
            dict: SEDG data from database, or None if not found
        """
        db = DatabaseManager()
        
        try:
            query = """
                SELECT sedg_data, status, updated_at 
                FROM sedg_disclosures 
                WHERE company_id = %s AND disclosure_period = %s
            """
            result = db.fetch_one(query, (company_id, disclosure_period))
            
            if result:
                sedg_data = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                metadata = {
                    'status': result[1],
                    'last_updated': result[2].isoformat() if result[2] else None
                }
                return {'data': sedg_data, 'metadata': metadata}
            
            logger.info(f"No SEDG disclosure found for company {company_id}, period {disclosure_period}")
            return None
            
        except Exception as e:
            logger.error(f"Error loading SEDG: {e}")
            return None
    
    def should_save(self) -> bool:
        """Check if we have unsaved changes"""
        return st.session_state.get('sedg_has_changes', False)
    
    def mark_changed(self):
        """Mark SEDG form as having unsaved changes"""
        st.session_state['sedg_has_changes'] = True
        # Reset debounce timer
        st.session_state['sedg_last_save_time'] = datetime.now()
    
    def mark_saved(self):
        """Mark SEDG form as saved"""
        st.session_state['sedg_has_changes'] = False
        st.session_state['sedg_last_save_time'] = datetime.now()
    
    def get_sedg_changes(self) -> dict:
        """
        Extract SEDG form data from session state

        Returns:
            dict: The disclosure period and every SEDG form field (without the
            'sedg_' prefix). Page/control state is never included.
        """
        data = {'period': st.session_state.get('sedg_period', str(datetime.now().year))}
        for field in SEDG_DEFAULTS:
            data[field] = st.session_state.get(f'sedg_{field}', default_sedg_value(field))
        return data
    
    def save_sedg_data(self, company_id: int, disclosure_period: int, 
                       reporting_year: int, user_id: int) -> bool:
        """
        Save SEDG disclosure data to database (upsert)
        
        Args:
            company_id: Company ID
            disclosure_period: Reporting period string
            reporting_year: Year of reporting
            user_id: User ID for audit trail
        
        Returns:
            bool: Success status
        """
        try:
            # Get current SEDG data from session
            sedg_data = self.get_sedg_changes()
            
            # Serialize to JSON
            sedg_json = json.dumps(sedg_data, default=str)
            
            # Check if record exists
            check_query = """
                SELECT id FROM sedg_disclosures 
                WHERE company_id = %s AND disclosure_period = %s
            """
            existing = self.db.fetch_one(check_query, (company_id, disclosure_period))
            
            if existing:
                # UPDATE existing record
                update_query = """
                    UPDATE sedg_disclosures 
                    SET sedg_data = %s, 
                        last_modified_by = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = %s AND disclosure_period = %s
                """
                saved = self.db.execute_query(update_query, (
                    sedg_json, user_id, company_id, disclosure_period
                ))
            else:
                # INSERT new record
                insert_query = """
                    INSERT INTO sedg_disclosures 
                    (company_id, disclosure_period, reporting_year, sedg_data, 
                     last_modified_by, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                saved = self.db.execute_query(insert_query, (
                    company_id, disclosure_period, reporting_year, sedg_json, user_id
                ))

            if not saved:
                logger.error(f"SEDG save failed for company {company_id}, period {disclosure_period}")
                return False

            logger.info(f"SEDG saved for company {company_id}, period {disclosure_period}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving SEDG: {e}")
            return False
    
    def submit_sedg_disclosure(self, company_id: int, disclosure_period: str, 
                               user_id: int) -> bool:
        """
        Mark SEDG disclosure as submitted (official submission)
        
        Args:
            company_id: Company ID
            disclosure_period: Reporting period
            user_id: User ID who submitted
        
        Returns:
            bool: Success status
        """
        try:
            # Only a saved disclosure can be submitted (the UPDATE below would
            # otherwise "succeed" without changing any row)
            exists = self.db.fetch_one(
                "SELECT id FROM sedg_disclosures WHERE company_id = %s AND disclosure_period = %s",
                (company_id, disclosure_period)
            )
            if not exists:
                logger.warning(f"No saved SEDG disclosure to submit for company {company_id}, period {disclosure_period}")
                return False

            query = """
                UPDATE sedg_disclosures
                SET status = 'submitted',
                    submission_date = CURRENT_TIMESTAMP,
                    last_modified_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = %s AND disclosure_period = %s
            """
            result = self.db.execute_query(query, (user_id, company_id, disclosure_period))
            if result:
                logger.info(f"SEDG submitted for company {company_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error submitting SEDG: {e}")
            return False
    
    def check_debounce(self) -> bool:
        """
        Check if enough time passed since last save for debounced save.
        Uses SAVE_INTERVAL setting.
        
        Returns:
            bool: True if should save now (debounce interval exceeded)
        """
        last_save = st.session_state.get('sedg_last_save_time', datetime.now())
        elapsed = (datetime.now() - last_save).total_seconds()
        return elapsed >= SAVE_INTERVAL
    


class SEDGAutoSave:
    """Handles auto-save UI and logic"""
    
    def __init__(self):
        self.manager = SEDGManager()
    
    def init_session_state(self):
        """Initialize auto-save session state variables"""
        if 'sedg_has_changes' not in st.session_state:
            st.session_state['sedg_has_changes'] = False
        if 'sedg_last_save_time' not in st.session_state:
            st.session_state['sedg_last_save_time'] = datetime.now()
        if 'sedg_save_status' not in st.session_state:
            st.session_state['sedg_save_status'] = ''
    
    def get_save_badge(self) -> str:
        """Get save status badge"""
        if not st.session_state.get('sedg_has_changes', False):
            return self.manager.saved_indicator
        return self.manager.unsaved_indicator
    
    def auto_save_callback(self, company_id: int, disclosure_period: str, 
                           reporting_year: int, user_id: int, container=None):
        """
        Auto-save callback - call from Streamlit widgets in on_change
        Implements debouncing to avoid excessive saves
        
        Args:
            company_id: Company ID
            disclosure_period: Report period
            reporting_year: Year
            user_id: User ID
            container: Streamlit container for status message (optional)
        """
        self.manager.mark_changed()
        
        # Check if debounce interval passed
        if self.manager.check_debounce():
            success = self.manager.save_sedg_data(
                company_id, disclosure_period, reporting_year, user_id
            )
            
            if success:
                self.manager.mark_saved()
                st.session_state['sedg_save_status'] = self.manager.saved_indicator
                if container:
                    container.success("✅ Auto-saved!", icon="✅")
            else:
                st.session_state['sedg_save_status'] = "❌ Save failed"
                if container:
                    container.error("❌ Save failed", icon="❌")
    
    def manual_save(self, company_id: int, disclosure_period: str, 
                    reporting_year: int, user_id: int) -> bool:
        """
        Manual save button - immediate save without debouncing
        
        Args:
            company_id: Company ID
            disclosure_period: Report period
            reporting_year: Year
            user_id: User ID
        
        Returns:
            bool: Success status
        """
        success = self.manager.save_sedg_data(
            company_id, disclosure_period, reporting_year, user_id
        )
        
        if success:
            self.manager.mark_saved()
            st.session_state['sedg_save_status'] = self.manager.saved_indicator
            return True
        else:
            st.session_state['sedg_save_status'] = "❌ Save failed"
            return False
    
    def show_save_indicator(self, position='sidebar'):
        """
        Display save status indicator
        
        Args:
            position: 'sidebar' or 'main' - where to show the indicator
        """
        container = st.sidebar if position == 'sidebar' else st.container()
        
        with container:
            badge = self.get_save_badge()
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(badge)
            with col2:
                if st.session_state.get('sedg_has_changes', False):
                    if st.button("💾", help="Save now", key="sedg_save_btn", use_container_width=True):
                        return True
        return False


def initialize_sedg_form_session():
    """Initialize SEDG form with cached data or defaults"""
    if 'sedg_initialized' not in st.session_state:
        company_id = st.session_state.get('company_id')
        reporting_period = st.session_state.get('sedg_period', str(datetime.now().year))
        
        if company_id:
            # Try to load from database
            loaded_data = SEDGManager.load_sedg_form(company_id, reporting_period)
            
            if loaded_data:
                # Set every form field from the database, falling back to the
                # default for fields the saved data doesn't have. Anything else
                # (e.g. page state persisted by older versions) is ignored, as is
                # 'period', which is already bound to the selectbox widget.
                sedg_data = loaded_data['data'] or {}
                for field in SEDG_DEFAULTS:
                    value = sedg_data[field] if field in sedg_data else default_sedg_value(field)
                    st.session_state[f'sedg_{field}'] = value
                st.session_state['sedg_form_loaded'] = True
                logger.info(f"Loaded SEDG from database for period {reporting_period}")
            else:
                # No saved data found
                st.session_state['sedg_form_loaded'] = False
        
        st.session_state['sedg_initialized'] = True


def show_sedg_unsaved_warning():
    """Show warning if user tries to leave with unsaved changes"""
    if st.session_state.get('sedg_has_changes', False):
        st.warning(
            "⚠️ You have unsaved changes in the SEDG form. "
            "Click **💾 Save** before closing or refreshing the page.",
            icon="⚠️"
        )
