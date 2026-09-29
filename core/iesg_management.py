"""
ESG Ready Questionnaire Persistence Management
Handles database operations for multi-session ESG questionnaire responses
"""

import streamlit as st
import json
from datetime import datetime
from core.database import DatabaseManager

# Every questionnaire answer and its default value (session keys are these
# names prefixed with 'iesg_'). Only these fields are ever saved to or loaded
# from the database, so page state such as the change-tracking snapshot can
# never leak into response_data.
IESG_DEFAULTS = {
    # Section A: About The Company
    'company_name': '',
    'email': '',
    'phone': '',
    'location': 'W.P Kuala Lumpur',
    'subsector': 'E&E',
    'subsector_other': '',
    'company_size': None,
    'company_type': None,
    'reporting_standard': [],
    'reporting_standard_other': '',
    'none_reason': [],
    'none_reason_other': '',

    # Section B: General Understanding of ESG
    'q8_maturity': None,
    'q9_stakeholders': [],
    'q10_business_case': None,
    'q11_esg_goals': None,
    'q12_esg_leadership': None,
    'q13_esg_reporting': None,
    'q14_data_understanding': None,
    'q15_esg_elements': None,
    'q16_validation': None,

    # Section C: Environment
    'q17_carbon': None,
    'q18_ghg': None,
    'q19_water': None,
    'q20_waste': None,
    'q21_wastewater': None,
    'q22_energy': None,
    'q23_biodiversity': None,
    'q24_eco_materials': None,
    'q25_reforestation': None,

    # Section D: Social
    'q26_employee_involvement': None,
    'q27_domestic_labour': None,
    'q28_intl_labour': None,
    'q29_equal_employment': None,
    'q30_min_wage': None,
    'q31_health_safety': None,
    'q32_grievance': None,
    'q33_upskilling': None,
    'q34_community': None,

    # Section E: Governance
    'q35_board_leadership': None,
    'q36_board_awareness': None,
    'q37_strategy': None,
    'q38_code_conduct': None,
    'q39_anti_corruption': None,
    'q40_whistleblower': None,
    'q41_accounting': None,
    'q42_data_privacy': None,
}


def default_iesg_value(field: str):
    """Return a fresh default for a questionnaire field (lists are copied)."""
    value = IESG_DEFAULTS[field]
    return list(value) if isinstance(value, list) else value


class IESGManager:
    """
    Manages IESG (iESG Ready Questionnaire) responses with database persistence.
    Supports draft. submission tracking, and auto-save functionality.
    """
    
    _instance = None
    _db = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize IESG Manager"""
        if self._db is None:
            self._db = DatabaseManager()
        self.cache_ttl = 3600  # 1 hour
    
    def load_iesg_responses(self, company_id: int, assessment_period: str = "2024") -> dict:
        """
        Load IESG responses from database.

        Not cached: saves don't invalidate a cache, so a cached result would
        hide newly saved responses from other sessions.

        Args:
            company_id: Company ID
            assessment_period: Assessment period (e.g., "2024")
        
        Returns:
            Dictionary with 'data' and 'metadata' keys or empty dict if not found
        
        Example:
            >>> manager = IESGManager()
            >>> responses = manager.load_iesg_responses(5, "2024")
            >>> if responses:
            ...     st.write(f"Loaded {responses['metadata']['status']} responses")
        """
        try:
            query = """
                SELECT response_data, status, completion_score, esg_readiness_score, 
                       updated_at, last_modified_by
                FROM iesg_responses
                WHERE company_id = %s AND assessment_period = %s
                LIMIT 1
            """
            result = self._db.fetch_one(query, (company_id, assessment_period))
            
            if result:
                response_data = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                return {
                    'data': response_data,
                    'metadata': {
                        'status': result[1],
                        'completion_score': result[2],
                        'esg_readiness_score': result[3],
                        'updated_at': result[4],
                        'last_modified_by': result[5]
                    }
                }
            return {}
        except Exception as e:
            print(f"❌ Error loading IESG responses: {e}")
            return {}
    
    def save_iesg_responses(self, company_id: int, assessment_period: str, 
                           response_data: dict, status: str = 'draft', 
                           completion_score: int = None, user_id: int = None) -> bool:
        """
        Save IESG responses to database (insert or update).
        
        Args:
            company_id: Company ID
            assessment_period: Assessment period
            response_data: Dictionary with all response fields
            status: Response status (draft/in_progress/completed/submitted)
            completion_score: Completion percentage (0-100)
            user_id: User ID making the modification
        
        Returns:
            True if successful, False otherwise
        
        Example:
            >>> manager = IESGManager()
            >>> success = manager.save_iesg_responses(
            ...     company_id=5,
            ...     assessment_period="2024",
            ...     response_data={'iesg_company_name': 'ABC Corp', ...},
            ...     status='draft',
            ...     completion_score=45,
            ...     user_id=1
            ... )
        """
        try:
            # Persist questionnaire answers only, never page/control state
            answers = {k: v for k, v in response_data.items() if k in IESG_DEFAULTS}
            json_data = json.dumps(answers)

            # Check if record exists
            check_query = """
                SELECT id FROM iesg_responses 
                WHERE company_id = %s AND assessment_period = %s
            """
            existing = self._db.fetch_one(check_query, (company_id, assessment_period))
            
            if existing:
                # Update existing record
                update_query = """
                    UPDATE iesg_responses
                    SET response_data = %s, status = %s, completion_score = %s, 
                        last_modified_by = %s, updated_at = NOW()
                    WHERE company_id = %s AND assessment_period = %s
                """
                return self._db.execute_query(
                    update_query, 
                    (json_data, status, completion_score, user_id, company_id, assessment_period)
                )
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO iesg_responses 
                    (company_id, assessment_period, response_data, status, completion_score, 
                     last_modified_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                """
                return self._db.execute_query(
                    insert_query,
                    (company_id, assessment_period, json_data, status, completion_score, user_id)
                )
        except Exception as e:
            print(f"❌ Error saving IESG responses: {e}")
            return False
    
    def submit_iesg_responses(self, company_id: int, assessment_period: str, 
                             esg_readiness_score: int = None, user_id: int = None) -> bool:
        """
        Mark IESG responses as submitted.
        
        Args:
            company_id: Company ID
            assessment_period: Assessment period
            esg_readiness_score: Final ESG readiness score
            user_id: User ID submitting
        
        Returns:
            True if successful
        """
        try:
            query = """
                UPDATE iesg_responses
                SET status = 'submitted', submission_date = NOW(), 
                    esg_readiness_score = %s, last_modified_by = %s, updated_at = NOW()
                WHERE company_id = %s AND assessment_period = %s
            """
            return self._db.execute_query(
                query, (esg_readiness_score, user_id, company_id, assessment_period)
            )
        except Exception as e:
            print(f"❌ Error submitting IESG responses: {e}")
            return False
    
    def check_debounce(self, debounce_key: str = 'iesg_last_save', threshold: int = 5) -> bool:
        """
        Check if debounce threshold has passed (prevents database hammering).
        
        Args:
            debounce_key: Session state key for tracking last save time
            threshold: Seconds to wait between saves
        
        Returns:
            True if enough time has passed since last save
        """
        now = datetime.now()
        last_save = st.session_state.get(debounce_key)
        
        if last_save is None:
            st.session_state[debounce_key] = now
            return True
        
        elapsed = (now - last_save).total_seconds()
        if elapsed >= threshold:
            st.session_state[debounce_key] = now
            return True
        
        return False


class IESGAutoSave:
    """
    Manages auto-save UI and callbacks for IESG responses.
    Provides visual feedback and debounced saving.
    """
    
    def __init__(self, company_id: int, assessment_period: str = "2024"):
        """
        Initialize auto-save system.
        
        Args:
            company_id: Company ID for auto-save context
            assessment_period: Assessment period
        """
        self.company_id = company_id
        self.assessment_period = assessment_period
        self.manager = IESGManager()
        self._init_session_state()
    
    def _init_session_state(self):
        """Initialize session state for auto-save tracking"""
        if 'iesg_unsaved_changes' not in st.session_state:
            st.session_state.iesg_unsaved_changes = False
        if 'iesg_last_save' not in st.session_state:
            st.session_state.iesg_last_save = None
        if 'iesg_auto_save_status' not in st.session_state:
            st.session_state.iesg_auto_save_status = 'idle'
    
    def show_auto_save_indicator(self):
        """Display auto-save status indicator in sidebar"""
        with st.sidebar:
            if st.session_state.get('iesg_unsaved_changes'):
                st.warning("⚠️ Unsaved Changes", icon="⚠️")
            else:
                st.success("✅ Saved", icon="✅")
    
    def auto_save_callback(self, response_data: dict, completion_score: int = None):
        """
        Auto-save callback with debounce protection.
        Saves to database if threshold is met without blocking UI.
        
        Args:
            response_data: Dictionary of response data
            completion_score: Current completion percentage
        """
        st.session_state.iesg_unsaved_changes = True
        
        if self.manager.check_debounce('iesg_last_save', threshold=5):
            st.session_state.iesg_auto_save_status = 'saving'
            
            success = self.manager.save_iesg_responses(
                company_id=self.company_id,
                assessment_period=self.assessment_period,
                response_data=response_data,
                status='in_progress',
                completion_score=completion_score,
                user_id=st.session_state.get('user_id')
            )
            
            if success:
                st.session_state.iesg_unsaved_changes = False
                st.session_state.iesg_auto_save_status = 'saved'
            else:
                st.session_state.iesg_auto_save_status = 'error'
    
    def manual_save(self, response_data: dict, completion_score: int = None) -> bool:
        """
        Manual save triggered by user (no debounce).
        
        Args:
            response_data: Dictionary of response data
            completion_score: Current completion percentage
        
        Returns:
            True if save was successful
        """
        success = self.manager.save_iesg_responses(
            company_id=self.company_id,
            assessment_period=self.assessment_period,
            response_data=response_data,
            status='in_progress',
            completion_score=completion_score,
            user_id=st.session_state.get('user_id')
        )
        
        if success:
            st.session_state.iesg_unsaved_changes = False
            st.session_state.iesg_last_save = datetime.now()
            st.success("✅ Responses saved successfully!")
        else:
            st.error("❌ Failed to save responses. Please try again.")
        
        return success
    
    def submit_responses(self, response_data: dict, completion_score: int = None, 
                        esg_readiness_score: int = None) -> bool:
        """
        Submit IESG responses (mark as completed).
        
        Args:
            response_data: Dictionary of response data
            completion_score: Final completion percentage
            esg_readiness_score: Final ESG readiness score
        
        Returns:
            True if submission successful
        """
        # First save the data
        save_success = self.manager.save_iesg_responses(
            company_id=self.company_id,
            assessment_period=self.assessment_period,
            response_data=response_data,
            status='completed',
            completion_score=completion_score,
            user_id=st.session_state.get('user_id')
        )
        
        if not save_success:
            return False
        
        # Then mark as submitted
        submit_success = self.manager.submit_iesg_responses(
            company_id=self.company_id,
            assessment_period=self.assessment_period,
            esg_readiness_score=esg_readiness_score,
            user_id=st.session_state.get('user_id')
        )
        
        return submit_success


def initialize_iesg_responses_session(company_id: int, assessment_period: str = "2024"):
    """
    Load IESG responses from database or initialize defaults.
    Should be called during page initialization BEFORE widgets are created.
    
    Args:
        company_id: Company ID
        assessment_period: Assessment period
    
    Example:
        >>> from core.iesg_management import initialize_iesg_responses_session
        >>> initialize_iesg_responses_session(company_id=5, assessment_period="2024")
    """
    manager = IESGManager()
    loaded = manager.load_iesg_responses(company_id, assessment_period)
    
    data_loaded = False
    
    if loaded is not None and isinstance(loaded, dict) and 'data' in loaded:
        loaded_data = loaded['data']
        
        # Make sure loaded_data is not None and is a dict
        if loaded_data is not None and isinstance(loaded_data, dict):
            # Set every questionnaire field from the database, falling back to
            # the default for fields the saved data doesn't have. Anything else
            # in the saved data (e.g. page state persisted by older versions)
            # is ignored.
            for key in IESG_DEFAULTS:
                value = loaded_data[key] if key in loaded_data else default_iesg_value(key)
                st.session_state[f'iesg_{key}'] = value
            
            data_loaded = True
            
            # Set metadata
            metadata = loaded.get('metadata', {})
            st.session_state['iesg_responses_loaded'] = True
            st.session_state['iesg_form_status'] = metadata.get('status', 'draft')
            st.session_state['iesg_completion_score'] = metadata.get('completion_score', 0)
    
    # If no data was loaded, initialize with defaults
    if not data_loaded:
        for key in IESG_DEFAULTS:
            session_key = f'iesg_{key}'
            # Only set if not already in session state
            if session_key not in st.session_state:
                st.session_state[session_key] = default_iesg_value(key)
        
        st.session_state['iesg_responses_loaded'] = False
        st.session_state['iesg_form_status'] = 'draft'
        st.session_state['iesg_completion_score'] = 0
    
    return data_loaded


def show_iesg_unsaved_warning():
    """
    Display warning if there are unsaved changes before navigation.
    """
    if st.session_state.get('iesg_unsaved_changes'):
        st.warning(
            "⚠️ You have unsaved changes. Click 'Save Responses' to persist your progress.",
            icon="⚠️"
        )
