"""
SEDG Disclousre - Simplified ESG Disclosure Guide Report Generator
Complete implementation matching official SEDG v2 template with ALL fields
Multi-session persistence with debounced auto-save
"""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.permissions import check_page_permission, show_permission_badge
from core.cache import get_company_info, get_emissions_summary, get_sedg_ghg_data
from core.sedg_pdf import generate_sedg_pdf
from components.company_verification import enforce_company_verification
from core.sedg_management import SEDGAutoSave, initialize_sedg_form_session, show_sedg_unsaved_warning

# Check permissions
check_page_permission('07_📋_SEDG_Disclosure.py')

st.set_page_config(page_title="SEDG Report", page_icon="📋", layout="wide")

# Enforce company verification
status = enforce_company_verification(st.session_state.get('company_id'))
if status == 'no_company':
    st.error("❌ No company assigned.")
    st.stop()

# Sidebar
with st.sidebar:
    show_permission_badge()
    st.write(f"**User:** {st.session_state.username}")
    
    if st.button("🚪 Logout", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("main.py")

st.title("📋 SEDG Report Generator")
st.markdown("**Simplified ESG Disclosure Guide (SEDG) Version 2**")
st.divider()

# Check company
if not st.session_state.company_id:
    st.error("❌ No company assigned.")
    st.stop()

# Process explicit refresh request BEFORE widgets initialize
if st.session_state.pop('sedg_force_refresh', False):
    selected_period = st.session_state.get('sedg_period', str(datetime.now().year))
    keys_to_clear = [k for k in list(st.session_state.keys()) if k.startswith('sedg_')]
    for key in keys_to_clear:
        del st.session_state[key]
    st.session_state['sedg_period'] = selected_period
    st.session_state.pop('sedg_initialized', None)
    st.session_state.pop('sedg_form_loaded', None)
    st.session_state.pop('sedg_loaded_context', None)
    st.session_state.pop('sedg_last_snapshot', None)
    st.session_state['sedg_has_changes'] = False
    st.cache_data.clear()

# Initialize session state with complete SEDG fields FIRST (before any widgets)
def init_sedg():
    prefix = 'sedg_'
    defaults = {
        # General Information
        f'{prefix}period': str(datetime.now().year),
        f'{prefix}entities_included': '',
        f'{prefix}locations_included': '',
        
        # E1.1-E1.2 - GHG (auto-filled from system)
        # E1.3-E1.4 - GHG Reduction
        f'{prefix}e13_scope1_reduction': 0.0,
        f'{prefix}e14_scope2_reduction': 0.0,
        # E1.5 - Scope 3 Total
        f'{prefix}e15_scope3_total': 0.0,
        # E1.6 - Scope 3 Reduction
        f'{prefix}e16_scope3_reduction': 0.0,
        # E1.7 - GHG Intensity
        f'{prefix}e17_intensity': 0.0,
        
        # E2.1 - Energy Consumption (Basic)
        f'{prefix}e21_renewable': 0.0,
        f'{prefix}e21_nonrenewable': 0.0,
        f'{prefix}e21_electricity': 0.0,
        f'{prefix}e21_heating': 0.0,
        f'{prefix}e21_cooling': 0.0,
        f'{prefix}e21_steam': 0.0,
        
        # E2.2 - Energy Consumption Reduction (Intermediate)
        f'{prefix}e22_renewable_reduction': 0.0,
        f'{prefix}e22_nonrenewable_reduction': 0.0,
        f'{prefix}e22_electricity_reduction': 0.0,
        f'{prefix}e22_heating_reduction': 0.0,
        f'{prefix}e22_cooling_reduction': 0.0,
        f'{prefix}e22_steam_reduction': 0.0,
        
        # E3.1 - Total Water Withdrawn (Basic)
        f'{prefix}e31_purchased': 0.0,
        f'{prefix}e31_surface': 0.0,
        f'{prefix}e31_ground': 0.0,
        f'{prefix}e31_sea': 0.0,
        f'{prefix}e31_produced': 0.0,
        
        # E3.2 - Water Reduction (Intermediate)
        f'{prefix}e32_reduction': 0.0,
        
        # E4.1 - Total Waste (Basic)
        f'{prefix}e41_generated': 0.0,
        f'{prefix}e41_diverted': 0.0,
        f'{prefix}e41_disposed': 0.0,
        
        # E4.2 - Waste Breakdown (Intermediate)
        f'{prefix}e42_haz_gen': 0.0,
        f'{prefix}e42_haz_div': 0.0,
        f'{prefix}e42_haz_disp': 0.0,
        f'{prefix}e42_nonhaz_gen': 0.0,
        f'{prefix}e42_nonhaz_div': 0.0,
        f'{prefix}e42_nonhaz_disp': 0.0,
        f'{prefix}e42_sector_gen': 0.0,
        f'{prefix}e42_sector_div': 0.0,
        f'{prefix}e42_sector_disp': 0.0,
        f'{prefix}e42_material_gen': 0.0,
        f'{prefix}e42_material_div': 0.0,
        f'{prefix}e42_material_disp': 0.0,
        
        # E4.3 - Waste Diversion Methods (Advanced)
        f'{prefix}e43_haz_reuse': 0.0,
        f'{prefix}e43_haz_recycle': 0.0,
        f'{prefix}e43_haz_recovery': 0.0,
        f'{prefix}e43_nonhaz_reuse': 0.0,
        f'{prefix}e43_nonhaz_recycle': 0.0,
        f'{prefix}e43_nonhaz_recovery': 0.0,
        
        # E4.4 - Waste Disposal Methods (Advanced)
        f'{prefix}e44_haz_incin_recovery': 0.0,
        f'{prefix}e44_haz_incin_no_recovery': 0.0,
        f'{prefix}e44_haz_landfill': 0.0,
        f'{prefix}e44_haz_other': 0.0,
        f'{prefix}e44_nonhaz_incin_recovery': 0.0,
        f'{prefix}e44_nonhaz_incin_no_recovery': 0.0,
        f'{prefix}e44_nonhaz_landfill': 0.0,
        f'{prefix}e44_nonhaz_other': 0.0,
        
        # E5.1 - Materials (Basic)
        f'{prefix}e51_materials': '',
        # E5.2 - Recycled Materials (Advanced)
        f'{prefix}e52_recycled_pct': 0.0,
        
        # S1.1 - Child & Forced Labour Incidents (Basic)
        f'{prefix}s11_child_incidents': 0,
        f'{prefix}s11_child_nature': '',
        f'{prefix}s11_forced_incidents': 0,
        f'{prefix}s11_forced_nature': '',
        
        # S1.2 - Risk of Child & Forced Labour (Intermediate)
        f'{prefix}s12_child_risk_ops': '',
        f'{prefix}s12_forced_risk_ops': '',
        
        # S2.1 - Training (Basic)
        f'{prefix}s21_training_hours': 0.0,
        
        # S2.2 - Employee Data (Intermediate)
        f'{prefix}s22_num_employees': 0,
        f'{prefix}s22_turnover': 0.0,
        
        # S2.3 - Minimum Wage (Basic)
        f'{prefix}s23_min_wage_pct': 0.0,
        
        # S3.1 - Diversity - Employees (Basic)
        f'{prefix}s31_emp_female': 0.0,
        f'{prefix}s31_emp_age': '',
        
        # S3.2 - Diversity - Directors (Intermediate)
        f'{prefix}s32_dir_female': 0.0,
        f'{prefix}s32_dir_age': '',
        
        # S4.1 - Health & Safety Incidents (Basic)
        f'{prefix}s41_fatalities': 0,
        f'{prefix}s41_injuries': 0,
        
        # S4.2 - H&S Training (Intermediate)
        f'{prefix}s42_hs_trained_num': 0,
        f'{prefix}s42_hs_trained_pct': 0.0,
        
        # S5.1 - Community Investment (Basic)
        f'{prefix}s51_community_invest': 0.0,
        
        # S5.2 - Community Impact (Advanced)
        f'{prefix}s52_negative_impact': '',
        
        # G1.1 - Board Composition (Basic)
        f'{prefix}g11_num_directors': 0,
        
        # G1.2 - Governance Structure (Intermediate)
        f'{prefix}g12_structure': '',
        
        # G2.1 - Policies (Basic)
        f'{prefix}g21_policies': '',
        
        # G3.1 - Audit (Basic)
        f'{prefix}g31_audit_year': datetime.now().year,
        
        # G3.2 - Operations Risks (Intermediate)
        f'{prefix}g32_ops_risks': '',
        
        # G3.3 - Sustainability Risks (Advanced)
        f'{prefix}g33_sustain_risks': '',
        
        # G4.1 - Corruption Incidents (Basic)
        f'{prefix}g41_corrupt_incidents': 0,
        f'{prefix}g41_corrupt_nature': '',
        
        # G4.2 - Anti-corruption Training (Intermediate)
        f'{prefix}g42_anticorrupt_num': 0,
        f'{prefix}g42_anticorrupt_pct': 0.0,
        
        # G4.3 - Corruption Risks (Advanced)
        f'{prefix}g43_corrupt_risks': '',
        
        # G5.1 - Privacy (Intermediate)
        f'{prefix}g51_privacy_complaints': 0,
        f'{prefix}g51_privacy_nature': '',
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
 
init_sedg()

company = get_company_info(st.session_state.company_id)
if not company:
    st.error("❌ Unable to load company information.")
    st.stop()

# Load from database only when context changes (company + period)
current_context = f"{st.session_state.company_id}:{st.session_state.get('sedg_period', str(datetime.now().year))}"
if st.session_state.get('sedg_loaded_context') != current_context:
    st.session_state.pop('sedg_initialized', None)
    initialize_sedg_form_session()
    st.session_state['sedg_loaded_context'] = current_context
    st.session_state.pop('sedg_last_snapshot', None)

# Callback for period change to reload form
def on_period_change():
    """Reload form when user changes disclosure period"""
    # Clear all SEDG keys except period to force fresh load for new period
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith('sedg_') and k != 'sedg_period']
    for key in keys_to_clear:
        del st.session_state[key]
    st.session_state.pop('sedg_initialized', None)
    st.session_state.pop('sedg_loaded_context', None)
    st.session_state.pop('sedg_last_snapshot', None)
    st.session_state['sedg_has_changes'] = False

# General Info
st.header("📊 General Information")
st.info("ℹ️ Auto-filled from your company profile")

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    **Name of Organisation:** {company['company_name']}  
    **Location of Headquarters:** {company.get('address', 'Not specified')}  
    **Industry:** {company['industry_sector']}
    """)

with col2:
    st.selectbox("Disclosure Period", 
                options=[str(y) for y in range(datetime.now().year, datetime.now().year-5, -1)],
                key='sedg_period',
                on_change=on_period_change)
    disclosure_date = st.date_input("Date of Disclosure", datetime.now())

# Show form status after loading
if st.session_state.get('sedg_form_loaded', False):
    st.info(
        "📂 **Form loaded from previous session** - Your progress has been restored. "
        "Continue editing and click **💾 Save** when done.",
        icon="ℹ️"
    )
else:
    st.info(
        "**New form** - This is a fresh SEDG disclosure form. "
        "Your progress will be saved automatically.",
        icon="📝"
    )
    
col3, col4 = st.columns(2)
with col3:
    st.text_area("Entities Included", key='sedg_entities_included',
                placeholder="List all entities/subsidiaries included in this report", height=80)
with col4:
    st.text_area("Locations Included", key='sedg_locations_included',
                placeholder="List all locations/countries included in this report", height=80)

st.divider()

# Get GHG data
reporting_period = st.session_state.sedg_period

# Primary: same helper as dashboard (exact period match)
ghg_data = get_emissions_summary(st.session_state.company_id, reporting_period)

# Tabs
tab1, tab2, tab3 = st.tabs(["🌍 Environmental", "👥 Social", "⚖️ Governance"])

# ENVIRONMENTAL
with tab1:
    st.subheader("🌍 Environmental Disclosures")
    
    # E1.1-E1.2 - GHG Emissions
    st.markdown("### SEDG-E1.1 & E1.2: GHG Emissions (Basic)")
    st.info("Auto-filled from your emissions data")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Scope 1*", f"{ghg_data['scope_1']:.2f} tonnes")
    with col2:
        st.metric("Scope 2*", f"{ghg_data['scope_2']:.2f} tonnes")
    with col3:
        st.metric("Scope 3*", f"{ghg_data['scope_3']:.2f} tonnes")
    
    st.divider()
    
    # E1.3-E1.4 - GHG Reduction
    st.markdown("### SEDG-E1.3 & E1.4: GHG Emissions Reduction (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Scope 1 reduction (tonnes)", min_value=0.0, key='sedg_e13_scope1_reduction')
    with col2:
        st.number_input("Scope 2 reduction (tonnes)", min_value=0.0, key='sedg_e14_scope2_reduction')
    
    st.divider()
    
    # E1.5 - Scope 3 Total
    st.markdown("### SEDG-E1.5: Total Scope 3 GHG Emissions (Advanced)")
    st.number_input("Total Scope 3 emissions (tonnes)", min_value=0.0, key='sedg_e15_scope3_total',
                   help="Total Scope 3 GHG emissions")
    
    st.divider()
    
    # E1.6 - Scope 3 Reduction
    st.markdown("### SEDG-E1.6: Scope 3 Reduction (Advanced)")
    st.number_input("Scope 3 reduction (tonnes)", min_value=0.0, key='sedg_e16_scope3_reduction')
    
    st.divider()
    
    # E1.7 - GHG Intensity
    st.markdown("### SEDG-E1.7: Total Scope 1 and 2 GHG Intensity (Advanced)")
    st.number_input("GHG intensity (tonnes CO2e per unit)", min_value=0.0, key='sedg_e17_intensity',
                   help="Total Scope 1+2 emissions per revenue/production unit")
    
    st.divider()
    
    # E2.1 - Energy Consumption
    st.markdown("### SEDG-E2.1: Energy Consumption (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Renewable fuel sources (J/Wh)", min_value=0.0, key='sedg_e21_renewable')
        st.number_input("Non-renewable fuel sources (J/Wh)", min_value=0.0, key='sedg_e21_nonrenewable')
        st.number_input("Electricity (J/Wh)", min_value=0.0, key='sedg_e21_electricity')
    with col2:
        st.number_input("Heating (J/Wh)", min_value=0.0, key='sedg_e21_heating')
        st.number_input("Cooling (J/Wh)", min_value=0.0, key='sedg_e21_cooling')
        st.number_input("Steam (J/Wh)", min_value=0.0, key='sedg_e21_steam')
    
    st.divider()
    
    # E2.2 - Energy Consumption Reduction
    st.markdown("### SEDG-E2.2: Energy Consumption Reduction (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Renewable fuel reduction (J/Wh)", min_value=0.0, key='sedg_e22_renewable_reduction')
        st.number_input("Non-renewable fuel reduction (J/Wh)", min_value=0.0, key='sedg_e22_nonrenewable_reduction')
        st.number_input("Electricity reduction (J/Wh)", min_value=0.0, key='sedg_e22_electricity_reduction')
    with col2:
        st.number_input("Heating reduction (J/Wh)", min_value=0.0, key='sedg_e22_heating_reduction')
        st.number_input("Cooling reduction (J/Wh)", min_value=0.0, key='sedg_e22_cooling_reduction')
        st.number_input("Steam reduction (J/Wh)", min_value=0.0, key='sedg_e22_steam_reduction')
    
    st.divider()
    
    # E3.1 - Water
    st.markdown("### SEDG-E3.1: Total Water Withdrawn (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Purchased water (litres)", min_value=0.0, key='sedg_e31_purchased')
        st.number_input("Surface water (litres)", min_value=0.0, key='sedg_e31_surface')
        st.number_input("Groundwater (litres)", min_value=0.0, key='sedg_e31_ground')
    with col2:
        st.number_input("Seawater (litres)", min_value=0.0, key='sedg_e31_sea')
        st.number_input("Produced water (litres)", min_value=0.0, key='sedg_e31_produced')
    
    st.divider()
    
    # E3.2 - Water Reduction
    st.markdown("### SEDG-E3.2: Water Withdrawn Reduction (Intermediate)")
    st.number_input("Water reduction (litres)", min_value=0.0, key='sedg_e32_reduction')
    
    st.divider()
    
    # E4.1 - Total Waste
    st.markdown("### SEDG-E4.1: Total Waste (Basic)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Generated (tonnes)", min_value=0.0, key='sedg_e41_generated')
    with col2:
        st.number_input("Diverted from disposal (tonnes)", min_value=0.0, key='sedg_e41_diverted')
    with col3:
        st.number_input("Directed to disposal (tonnes)", min_value=0.0, key='sedg_e41_disposed')
    
    st.divider()
    
    # E4.2 - Waste Breakdown
    st.markdown("### SEDG-E4.2: Waste Breakdown (Intermediate)")
    
    st.markdown("**Hazardous Waste**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Haz Generated (tonnes)", min_value=0.0, key='sedg_e42_haz_gen')
    with col2:
        st.number_input("Haz Diverted (tonnes)", min_value=0.0, key='sedg_e42_haz_div')
    with col3:
        st.number_input("Haz Disposed (tonnes)", min_value=0.0, key='sedg_e42_haz_disp')
    
    st.markdown("**Non-hazardous Waste**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Non-haz Generated (tonnes)", min_value=0.0, key='sedg_e42_nonhaz_gen')
    with col2:
        st.number_input("Non-haz Diverted (tonnes)", min_value=0.0, key='sedg_e42_nonhaz_div')
    with col3:
        st.number_input("Non-haz Disposed (tonnes)", min_value=0.0, key='sedg_e42_nonhaz_disp')
    
    st.markdown("**Sector-specific Waste Streams**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Sector Generated (tonnes)", min_value=0.0, key='sedg_e42_sector_gen')
    with col2:
        st.number_input("Sector Diverted (tonnes)", min_value=0.0, key='sedg_e42_sector_div')
    with col3:
        st.number_input("Sector Disposed (tonnes)", min_value=0.0, key='sedg_e42_sector_disp')
    
    st.markdown("**Material Composition**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Material Generated (tonnes)", min_value=0.0, key='sedg_e42_material_gen')
    with col2:
        st.number_input("Material Diverted (tonnes)", min_value=0.0, key='sedg_e42_material_div')
    with col3:
        st.number_input("Material Disposed (tonnes)", min_value=0.0, key='sedg_e42_material_disp')
    
    st.divider()
    
    # E4.3 - Waste Diversion Methods
    st.markdown("### SEDG-E4.3: Waste Diversion Methods (Advanced)")
    
    st.markdown("**Hazardous - Diverted from Disposal**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Preparation for reuse (tonnes)", min_value=0.0, key='sedg_e43_haz_reuse')
    with col2:
        st.number_input("Recycling (tonnes)", min_value=0.0, key='sedg_e43_haz_recycle')
    with col3:
        st.number_input("Other recovery options (tonnes)", min_value=0.0, key='sedg_e43_haz_recovery')
    
    st.markdown("**Non-hazardous - Diverted from Disposal**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Prep for reuse (tonnes)", min_value=0.0, key='sedg_e43_nonhaz_reuse')
    with col2:
        st.number_input("Recycle (tonnes)", min_value=0.0, key='sedg_e43_nonhaz_recycle')
    with col3:
        st.number_input("Other recovery options (tonnes)", min_value=0.0, key='sedg_e43_nonhaz_recovery')
    
    st.divider()
    
    # E4.4 - Waste Disposal Methods
    st.markdown("### SEDG-E4.4: Waste Disposal Methods (Advanced)")
    
    st.markdown("**Hazardous - Directed to Disposal**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.number_input("Incineration w/ recovery", min_value=0.0, key='sedg_e44_haz_incin_recovery')
    with col2:
        st.number_input("Incineration w/o recovery", min_value=0.0, key='sedg_e44_haz_incin_no_recovery')
    with col3:
        st.number_input("Landfilling", min_value=0.0, key='sedg_e44_haz_landfill')
    with col4:
        st.number_input("Other disposal", min_value=0.0, key='sedg_e44_haz_other')
    
    st.markdown("**Non-hazardous - Directed to Disposal**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.number_input("Incineration w/ recovery", min_value=0.0, key='sedg_e44_nonhaz_incin_recovery')
    with col2:
        st.number_input("Incineration w/o recovery", min_value=0.0, key='sedg_e44_nonhaz_incin_no_recovery')
    with col3:
        st.number_input("Landfilling", min_value=0.0, key='sedg_e44_nonhaz_landfill')
    with col4:
        st.number_input("Other disposal", min_value=0.0, key='sedg_e44_nonhaz_other')
    
    st.divider()
    
    # E5.1 - Materials
    st.markdown("### SEDG-E5.1: Key Materials (Basic)")
    st.text_area("List of materials for primary products and services", key='sedg_e51_materials', height=80,
                placeholder="e.g., Steel, Plastic, Paper...",
                help="Include total weights in metric tonnes, if applicable")
    
    st.divider()
    
    # E5.2 - Recycled Materials
    st.markdown("### SEDG-E5.2: Recycled Input Materials (Advanced)")
    st.number_input("Recycled input materials used (%)", min_value=0.0, max_value=100.0, key='sedg_e52_recycled_pct')

# SOCIAL
with tab2:
    st.subheader("👥 Social Disclosures")
    
    # S1.1 - Child & Forced Labour Incidents
    st.markdown("### SEDG-S1.1: Child Labour and Forced Labour Incidents (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Child labour incidents", min_value=0, key='sedg_s11_child_incidents')
        st.text_area("Nature of child labour incidents", key='sedg_s11_child_nature', 
                    placeholder="None or describe", height=80)
    with col2:
        st.number_input("Forced labour incidents", min_value=0, key='sedg_s11_forced_incidents')
        st.text_area("Nature of forced labour incidents", key='sedg_s11_forced_nature', 
                    placeholder="None or describe", height=80)
    
    st.divider()
    
    # S1.2 - Risk of Child & Forced Labour
    st.markdown("### SEDG-S1.2: Risk of Child Labour and Forced Labour (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.text_area("List of operations and suppliers with significant risk of child labour", key='sedg_s12_child_risk_ops', 
                    placeholder="List operations and suppliers...", height=100)
    with col2:
        st.text_area("List of operations and suppliers with significant risk of forced labour", key='sedg_s12_forced_risk_ops',
                    placeholder="List operations and suppliers...", height=100)
    
    st.divider()
    
    # S2.1 - Training
    st.markdown("### SEDG-S2.1: Employee Training (Basic)")
    st.number_input("Average training hours per employee", min_value=0.0, key='sedg_s21_training_hours')
    
    st.divider()
    
    # S2.2 - Employee Data
    st.markdown("### SEDG-S2.2: Employee Information (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Number of employees", min_value=0, key='sedg_s22_num_employees')
    with col2:
        st.number_input("Turnover rate (%)", min_value=0.0, max_value=100.0, key='sedg_s22_turnover')
    
    st.divider()
    
    # S2.3 - Minimum Wage
    st.markdown("### SEDG-S2.3: Percentage of Employees Meeting or Above Applicable Minimum Wage Laws (Basic)")
    st.number_input("% meeting or above applicable minimum wage laws, if any", min_value=0.0, max_value=100.0, key='sedg_s23_min_wage_pct')
    
    st.divider()
    
    # S3.1 - Diversity - Employees
    st.markdown("### SEDG-S3.1: Diversity - Company's Employees (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Employees - Female (%)", min_value=0.0, max_value=100.0, key='sedg_s31_emp_female')
    with col2:
        st.text_input("Employees by age (%)", key='sedg_s31_emp_age', 
                     placeholder="e.g., <30: 40%, 30-50: 50%, >50: 10%")
    
    st.divider()
    
    # S3.2 - Diversity - Directors
    st.markdown("### SEDG-S3.2: Diversity - Company's Directors (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Directors - Female (%)", min_value=0.0, max_value=100.0, key='sedg_s32_dir_female')
    with col2:
        st.text_input("Directors by age (%)", key='sedg_s32_dir_age',
                     placeholder="e.g., <30: 0%, 30-50: 60%, >50: 40%")
    
    st.divider()
    
    # S4.1 - Health & Safety Incidents
    st.markdown("### SEDG-S4.1: Occupational Health & Safety Incidents (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Number of fatalities", min_value=0, key='sedg_s41_fatalities')
    with col2:
        st.number_input("Number of injuries", min_value=0, key='sedg_s41_injuries')
    
    st.divider()
    
    # S4.2 - H&S Training
    st.markdown("### SEDG-S4.2: Health & Safety Training (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Employees trained in H&S (number)", min_value=0, key='sedg_s42_hs_trained_num')
    with col2:
        st.number_input("Employees trained in H&S (%)", min_value=0.0, max_value=100.0, key='sedg_s42_hs_trained_pct')
    
    st.divider()
    
    # S5.1 - Community Investment
    st.markdown("### SEDG-S5.1: Community Investment (Basic)")
    st.number_input("Total community investment and donations (MYR)", min_value=0.0, key='sedg_s51_community_invest')
    
    st.divider()
    
    # S5.2 - Community Impact
    st.markdown("### SEDG-S5.2: Community Impact (Advanced)")
    st.text_area("Operations with negative impact on local communities", key='sedg_s52_negative_impact',
                placeholder="List operations or enter 'None'", height=80)

# GOVERNANCE
with tab3:
    st.subheader("⚖️ Governance Disclosures")
    
    # G1.1 - Board Composition
    st.markdown("### SEDG-G1.1: Board Composition (Basic)")
    st.number_input("Number of directors", min_value=0, key='sedg_g11_num_directors')
    
    st.divider()
    
    # G1.2 - Governance Structure
    st.markdown("### SEDG-G1.2: Governance Structure (Intermediate)")
    st.text_area("List the governance structure of the board, including committees of the board and management, if applicable", key='sedg_g12_structure', height=120,
                placeholder="e.g., Board of Directors, Audit Committee, Risk Committee, Executive Management...")
    
    st.divider()
    
    # G2.1 - Policies
    st.markdown("### SEDG-G2.1: Company Policies (Basic)")
    st.text_area("List the company's policies (including but not limited to: Code of Conduct, Anti-Corruption Policy, Whistleblowing Policy, Health and Safety Policy)", 
                key='sedg_g21_policies', height=120,
                placeholder="e.g., Code of Conduct, Anti-Corruption Policy, Whistleblowing Policy, Health and Safety Policy...")
    
    st.divider()
    
    # G3.1 - Audit
    st.markdown("### SEDG-G3.1: Financial Audit (Basic)")
    st.number_input("Year of last submitted audited financial report", min_value=2000, max_value=datetime.now().year,
                   key='sedg_g31_audit_year')
    
    st.divider()
    
    # G3.2 - Operations Risks
    st.markdown("### SEDG-G3.2: Operations & Activities Risks (Intermediate)")
    st.text_area("List the risks of company operations and activities (including but not limited to: Regulatory compliance risk, Business continuity risk)", 
                key='sedg_g32_ops_risks', height=120,
                placeholder="e.g., Regulatory compliance risk, Business continuity risk...")
    
    st.divider()
    
    # G3.3 - Sustainability Risks
    st.markdown("### SEDG-G3.3: Sustainability Risks (Advanced)")
    st.text_area("List the sustainability risks of company, if applicable (including but not limited to: Climate-related physical risk, Climate-related transition risk)", 
                key='sedg_g33_sustain_risks', height=120,
                placeholder="e.g., Climate-related physical risk, Climate-related transition risk...")
    
    st.divider()
    
    # G4.1 - Corruption Incidents
    st.markdown("### SEDG-G4.1: Anti-Corruption Incidents (Basic)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Confirmed corruption incidents", min_value=0, key='sedg_g41_corrupt_incidents')
    with col2:
        st.text_area("Nature of corruption incidents", key='sedg_g41_corrupt_nature',
                    placeholder="Describe or enter 'None'", height=80)
    
    st.divider()
    
    # G4.2 - Anti-corruption Training
    st.markdown("### SEDG-G4.2: Anti-Corruption Training (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Employees trained in anti-bribery and anti-corruption", min_value=0, key='sedg_g42_anticorrupt_num')
    with col2:
        st.number_input("Employees trained in anti-bribery and anti-corruption (%)", min_value=0.0, max_value=100.0, 
                       key='sedg_g42_anticorrupt_pct')
    
    st.divider()
    
    # G4.3 - Corruption Risks
    st.markdown("### SEDG-G4.3: Corruption Risks (Advanced)")
    st.text_area("List of corruption risks", key='sedg_g43_corrupt_risks', height=100,
                placeholder="List risks...")
    
    st.divider()
    
    # G5.1 - Privacy
    st.markdown("### SEDG-G5.1: Customer Data Privacy (Intermediate)")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Substantiated complaints on customer privacy breaches and data loss, if any", 
                       min_value=0, key='sedg_g51_privacy_complaints')
    with col2:
        st.text_area("Nature of substantiated privacy and data loss complaints, if any", 
                    key='sedg_g51_privacy_nature',
                    placeholder="Describe or enter 'None'", height=80)

# ACTIONS
st.divider()
st.header("💾 Save & Generate Report")

# Initialize save helper (manual save only, no auto-save)
auto_save = SEDGAutoSave()
auto_save.init_session_state()

# Real-time change tracking (without forcing DB reload)
# Exclude control/UI keys so state bookkeeping never masquerades as a form edit.
SEDG_METADATA_KEYS = {
    'sedg_last_snapshot', 'sedg_has_changes', 'sedg_last_save_time',
    'sedg_save_status', 'sedg_initialized', 'sedg_form_loaded',
    'sedg_loaded_context', 'sedg_force_refresh', 'sedg_period',
}
current_sedg_responses = {
    k.replace('sedg_', ''): v for k, v in st.session_state.items()
    if k.startswith('sedg_') and k not in SEDG_METADATA_KEYS
}
current_sedg_snapshot = json.dumps(current_sedg_responses, sort_keys=True, default=str)
previous_sedg_snapshot = st.session_state.get('sedg_last_snapshot')

if previous_sedg_snapshot is None:
    st.session_state['sedg_last_snapshot'] = current_sedg_snapshot
elif current_sedg_snapshot != previous_sedg_snapshot:
    st.session_state['sedg_has_changes'] = True
    st.session_state['sedg_last_snapshot'] = current_sedg_snapshot

# Show unsaved warning if needed
show_sedg_unsaved_warning()

# Save & Submit & Download buttons
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("💾 Save SEDG Form", type="primary", use_container_width=True):
        with st.spinner("Saving..."):
            success = auto_save.manual_save(
                company_id=st.session_state.company_id,
                disclosure_period=st.session_state.sedg_period,
                reporting_year=int(st.session_state.sedg_period.split('-')[0]),
                user_id=st.session_state.user_id
            )
            if success:
                st.session_state['sedg_last_snapshot'] = json.dumps(
                    {k.replace('sedg_', ''): v for k, v in st.session_state.items()
                     if k.startswith('sedg_') and k not in SEDG_METADATA_KEYS},
                    sort_keys=True,
                    default=str
                )
                st.success("✅ SEDG form saved successfully!")
            else:
                st.error("❌ Failed to save SEDG form")

with col2:
    if st.button("📤 Submit Disclosure", type="secondary", use_container_width=True):
        if not st.session_state.get('sedg_has_changes', False):
            with st.spinner("Submitting..."):
                from core.sedg_management import SEDGManager
                manager = SEDGManager()
                success = manager.submit_sedg_disclosure(
                    company_id=st.session_state.company_id,
                    disclosure_period=st.session_state.sedg_period,
                    user_id=st.session_state.user_id
                )
                if success:
                    st.session_state['sedg_has_changes'] = False
                    st.session_state['sedg_last_snapshot'] = json.dumps(
                        {k.replace('sedg_', ''): v for k, v in st.session_state.items()
                         if k.startswith('sedg_') and k not in SEDG_METADATA_KEYS},
                        sort_keys=True,
                        default=str
                    )
                    st.success("✅ SEDG disclosure submitted!")
                else:
                    st.error("❌ Failed to submit disclosure")
        else:
            st.warning("⚠️ Please save your changes before submitting")

with col3:
    if st.button("📥 Download PDF Report", type="secondary", use_container_width=True):
        try:
            # Collect all data from session state
            sedg_data = {k.replace('sedg_', ''): v for k, v in st.session_state.items() if k.startswith('sedg_')}
            
            with st.spinner("Generating PDF..."):
                pdf_buffer = generate_sedg_pdf(company, sedg_data, ghg_data, disclosure_date)
            
            filename = f"SEDG_Disclosure_{company['company_name'].replace(' ', '_')}_{reporting_period}.pdf"
            
            st.download_button("📥 Download PDF", pdf_buffer, filename, "application/pdf", use_container_width=True)
            st.success("✅ PDF ready for download!")
            
        except ImportError:
            st.error("❌ Install ReportLab: `pip install reportlab`")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

with col4:
    if st.button("🔄 Refresh from DB", type="secondary", use_container_width=True,
                 help="Reload latest saved SEDG data for selected period"):
        st.session_state['sedg_force_refresh'] = True
        st.rerun()

st.divider()
st.info(
    "💡 **Form Tips:**\n"
    "- Click **💾 Save SEDG Form** to save your progress to the database\n"
    "- Use **📤 Submit** when your disclosure is complete\n"
    "- Your data persists across sessions after saving\n"
    "- Always save before leaving the page!",
    icon="ℹ️"
)