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
CACHE_TTL = 3600   # 1 hour - cache loaded SEDG data

class SEDGManager:
    """Manages SEDG disclosure persistence and auto-save"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.unsaved_indicator = "⚠️ Unsaved changes"
        self.saved_indicator = "✅ Saved"
    
    @staticmethod
    @st.cache_data(ttl=CACHE_TTL, show_spinner=False)
    def load_sedg_form(company_id: int, disclosure_period: str):
        """
        Load existing SEDG disclosure from database.
        Cached at (company_id, disclosure_period) level.
        
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
        Extract SEDG data from session state (form fields only).

        Control/UI keys (change-tracking snapshot, save state, load context,
        etc.) are excluded so they are never persisted to ``sedg_data``. Leaking
        the snapshot in particular caused the stored JSON to embed itself on
        every save and grow exponentially.
        
        Returns:
            dict: All form ``sedg_*`` fields from session state
        """
        metadata_keys = {
            'sedg_last_snapshot', 'sedg_has_changes', 'sedg_last_save_time',
            'sedg_save_status', 'sedg_initialized', 'sedg_form_loaded',
            'sedg_loaded_context', 'sedg_force_refresh', 'sedg_period',
        }
        return {
            k.replace('sedg_', ''): v
            for k, v in st.session_state.items()
            if k.startswith('sedg_') and k not in metadata_keys
        }
    
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
                self.db.execute_query(update_query, (
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
                self.db.execute_query(insert_query, (
                    company_id, disclosure_period, reporting_year, sedg_json, user_id
                ))
            
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
    
    def clear_cache(self, company_id: int, disclosure_period: str):
        """Clear cache for a specific SEDG disclosure (after save)"""
        cache_key = f"load_sedg_form[{company_id}][{disclosure_period}]"
        if cache_key in st.session_state:
            del st.session_state[cache_key]
        # Also clear the actual cache if Streamlit exposes it
        st.cache_data.clear()
        logger.info(f"SEDG cache cleared for company {company_id}")


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
            self.manager.clear_cache(company_id, disclosure_period)
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
                # Load saved data, skipping keys bound to widgets or reserved
                # for UI state (older saves may contain leaked control keys).
                blocked = {
                    'period', 'last_snapshot', 'has_changes', 'last_save_time',
                    'save_status', 'initialized', 'form_loaded', 'loaded_context',
                    'force_refresh',
                }
                sedg_data = loaded_data['data']
                for key, value in sedg_data.items():
                    if key not in blocked:
                        st.session_state[f'sedg_{key}'] = value
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
