"""
ESG Ready Questionnaire - ESG Readiness Self Assessment
Complete implementation with all official MITI questions
"""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import datetime
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.permissions import check_page_permission, show_permission_badge
from core.cache import get_company_info
from components.company_verification import enforce_company_verification
from core.iesg_management import (
    IESG_DEFAULTS, IESGAutoSave, default_iesg_value,
    initialize_iesg_responses_session, show_iesg_unsaved_warning,
)

# Check permissions
check_page_permission('08_📝_ESG_Ready_Questionnaire.py')

st.set_page_config(page_title="ESG Ready", page_icon="📝", layout="wide")

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

st.title("📝 ESG Ready Questionnaire")
st.markdown("**ESG Readiness Self-Assessment Programme**")
st.info("ℹ️ Complete this assessment locally. Your data stays private and you can download a PDF of your responses.")
st.divider()

# Process explicit refresh request BEFORE widgets initialize
if st.session_state.pop('iesg_force_refresh', False):
    keys_to_clear = [k for k in list(st.session_state.keys()) if k.startswith('iesg_')]
    for key in keys_to_clear:
        del st.session_state[key]
    st.session_state.pop('iesg_loaded_context', None)

# Copy of the answers kept outside widget state. Streamlit deletes a widget's
# session value on any run where the widget isn't rendered (e.g. while the user
# is on another page), so without this copy the answers would come back blank.
ANSWERS_KEY = 'iesg_answers'

def restore_iesg_answers():
    """Restore any widget values Streamlit cleared, else use defaults"""
    answers = st.session_state.get(ANSWERS_KEY, {})
    for field in IESG_DEFAULTS:
        key = f'iesg_{field}'
        if key not in st.session_state:
            st.session_state[key] = answers[field] if field in answers else default_iesg_value(field)

# Step 1: Restore answers from this session (or defaults) before the database load
restore_iesg_answers()

# Step 2: Load from database ONCE per company/period context
# Avoid reloading on every rerun, which would overwrite in-progress edits.
company_id = st.session_state.get('company_id')
assessment_period = "2024"
if company_id:
    current_context = f"{company_id}:{assessment_period}"
    loaded_context = st.session_state.get('iesg_loaded_context')

    # Only initialize from DB if this is first load or context changed
    if loaded_context != current_context:
        data_loaded = initialize_iesg_responses_session(
            company_id=company_id,
            assessment_period=assessment_period
        )
        st.session_state['iesg_loaded_context'] = current_context

        if data_loaded:
            st.success("✅ **Form loaded from database** - Your previous responses have been restored.")
        else:
            st.info("📋 **New form** - Start filling in your ESG assessment.")

    # Auto-fill company name/email (read-only fields) from the company record
    company = get_company_info(company_id) or {}
    if company:
        st.session_state['iesg_company_name'] = company.get('company_name') or ''
        st.session_state['iesg_email'] = company.get('contact_email') or ''
else:
    st.warning("⚠️ No company ID found in session state")

# Progress tracking
def calculate_progress():
    """Calculate completion percentage"""
    # Define required fields (exclude conditional "other" fields)
    required_fields = [
        'iesg_company_name',
        'iesg_email',
        'iesg_phone',
        'iesg_location',
        'iesg_subsector',
        'iesg_company_size',
        'iesg_company_type',
        'iesg_reporting_standard',
        'iesg_q8_maturity',
        'iesg_q9_stakeholders',
        'iesg_q10_business_case',
        'iesg_q11_esg_goals',
        'iesg_q12_esg_leadership',
        'iesg_q13_esg_reporting',
        'iesg_q14_data_understanding',
        'iesg_q15_esg_elements',
        'iesg_q16_validation',
        'iesg_q17_carbon',
        'iesg_q18_ghg',
        'iesg_q19_water',
        'iesg_q20_waste',
        'iesg_q21_wastewater',
        'iesg_q22_energy',
        'iesg_q23_biodiversity',
        'iesg_q24_eco_materials',
        'iesg_q25_reforestation',
        'iesg_q26_employee_involvement',
        'iesg_q27_domestic_labour',
        'iesg_q28_intl_labour',
        'iesg_q29_equal_employment',
        'iesg_q30_min_wage',
        'iesg_q31_health_safety',
        'iesg_q32_grievance',
        'iesg_q33_upskilling',
        'iesg_q34_community',
        'iesg_q35_board_leadership',
        'iesg_q36_board_awareness',
        'iesg_q37_strategy',
        'iesg_q38_code_conduct',
        'iesg_q39_anti_corruption',
        'iesg_q40_whistleblower',
        'iesg_q41_accounting',
        'iesg_q42_data_privacy',
    ]
    
    # Add conditional fields if applicable
    if st.session_state.get('iesg_subsector') == "Other (please specify)":
        required_fields.append('iesg_subsector_other')
    if "Other (please specify)" in st.session_state.get('iesg_reporting_standard', []):
        required_fields.append('iesg_reporting_standard_other')
    if "None of the above" in st.session_state.get('iesg_reporting_standard', []):
        required_fields.append('iesg_none_reason')
        if "Other (please specify)" in st.session_state.get('iesg_none_reason', []):
            required_fields.append('iesg_none_reason_other')
    
    total_fields = len(required_fields)
    completed_fields = 0
    
    for field in required_fields:
        value = st.session_state.get(field, '')
        # Update this condition to handle None
        if value is not None and value != [] and value != '':
            completed_fields += 1
    
    return int((completed_fields / total_fields * 100)) if total_fields > 0 else 0

progress = calculate_progress()
st.sidebar.metric("📊 Completion", f"{progress}%")
st.sidebar.progress(progress / 100)

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 A. Company Info", 
    "📚 B. ESG Understanding",
    "🌍 C. Environment",
    "👥 D. Social",
    "⚖️ E. Governance"
])

# ============================================================================
# SECTION A: ABOUT THE COMPANY
# ============================================================================
with tab1:
    st.header("📋 Section A: About The Company")
    
    # Q1: Company Information
    st.subheader("1. Company Details")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input(
            "Company Name (auto-filled)",
            key='iesg_company_name',
            placeholder="Enter company name",
            disabled=True
        )
        st.text_input(
            "Email Address (auto-filled)",
            key='iesg_email',
            placeholder="company@example.com",
            disabled=True
        )
    with col2:
        st.text_input(
            "Phone Number *",
            key='iesg_phone',
            placeholder="+60 12-345 6789",
            help="add the phone number you would like to show on the generated pdf"
        )
    
    st.divider()
    
    # Q2: Company Location
    st.subheader("2. Where is your company located? *")
    locations = [
        "W.P Kuala Lumpur", "Selangor", "Negeri Sembilan", "Johor",
        "Penang", "Melaka", "Kedah", "Perak", "Perlis", "Pahang",
        "Kelantan", "Terengganu", "Sabah", "Sarawak"
    ]
    st.selectbox("Select state", options=locations, key='iesg_location')
    
    st.divider()
    
    # Q3: Company Sub-sector
    st.subheader("3. What is your company's sub-sector? *")
    subsectors = [
        "E&E",
        "Chemical & Petrochemical products",
        "Rubber & plastic products",
        "F&B",
        "Textiles and wearing apparel",
        "Wood & paper products",
        "Iron & steel and other basic metal products",
        "Non-metallic mineral products",
        "Pharmaceuticals",
        "Medical devices",
        "Machinery & Equipment",
        "Motor vehicles & Transport equipment",
        "Other (please specify)"
    ]
    st.selectbox("Select sub-sector", options=subsectors, key='iesg_subsector')
    
    if st.session_state.iesg_subsector == "Other (please specify)":
        st.text_input("Please specify", key='iesg_subsector_other')
    
    st.divider()
    
    # Q4: Company Size
    st.subheader("4. What is your company's size? *")
    sizes = [
        "Micro (sales: <RM300,000; employees: <5)",
        "Small (sales: RM300,000 ≤ RM15 mil; employees: 5 to < 30)",
        "Medium (sales: RM15 mil < RM50 mil; employees: 30 to ≤ 75)",
        "Large (sales: >RM50 mil; employees: >75)"
    ]
    st.radio("Company size", options=sizes, key='iesg_company_size', index=None)
    
    st.divider()
    
    # Q5: Types of Company
    st.subheader("5. What is your company's market orientation? *")
    types = [
        "Export-oriented (More than 60% of the products are exported)",
        "Domestic-oriented (Less than 60% of the products are exported)"
    ]
    st.radio("Company type", options=types, key='iesg_company_type', index=None)
    
    st.divider()
    
    # Q6: Sustainability Reporting Standard
    st.subheader("6. Which sustainability reporting standards does your organization use? *")
    standards = [
        "GRI", "TCFD", "CDP", "Bursa", "SASB", 
        "FTSE4Good", "Business Review Report by SSM",
        "Other (please specify)", "None of the above"
    ]
    st.multiselect(
        "Select all that apply",
        options=standards,
        key='iesg_reporting_standard',
        help="You can select multiple standards"
    )
    
    if "Other (please specify)" in st.session_state.iesg_reporting_standard:
        st.text_input("Please specify other standard", key='iesg_reporting_standard_other')
    
    st.divider()
    
    # Q7: Reason for None
    if "None of the above" in st.session_state.iesg_reporting_standard:
        st.subheader("7. If you selected 'None' in Q6, please explain why")
        reasons = [
            "Not sure where to begin",
            "Do not have the skills",
            "Do not have the tools",
            "Too costly",
            "Other (please specify)"
        ]
        st.multiselect(
            "Select all that apply",
            options=reasons,
            key='iesg_none_reason'
        )
        
        if "Other (please specify)" in st.session_state.iesg_none_reason:
            st.text_input("Please specify other reason", key='iesg_none_reason_other')

# ============================================================================
# SECTION B: GENERAL UNDERSTANDING OF ESG
# ============================================================================
with tab2:
    st.header("📚 Section B: General Understanding of ESG")
    
    # Q8: Maturity
    st.subheader("8. How mature is your organization's sustainability strategy? *")
    maturity_options = [
        "We have not started our sustainability journey yet",
        "We have started, but we should be doing more",
        "We are progressing well, but there is room for improvement",
        "We are very advanced"
    ]
    st.radio("Select maturity level", options=maturity_options, key='iesg_q8_maturity', index=None)
    
    st.divider()
    
    # Q9: Stakeholder Engagements
    st.subheader("9. Which stakeholders do you actively engage with? *")
    st.markdown("Organisation constantly engage the following stakeholders to meet their sustainability requirement. (Tick engaged stakeholders only)")
    stakeholders = [
        "Customers",
        "Employees",
        "Board of directors",
        "Investors",
        "Financiers",
        "Community",
        "None of the above"
    ]
    st.multiselect("Select all that apply", options=stakeholders, key='iesg_q9_stakeholders')
    
    st.divider()
    
    # Q10: Business Case Elements
    st.subheader("10. Which statement best describes your ESG business case? *")
    business_case = [
        "The Organization does not understand how ESG can present opportunities to enhance revenue, reduce costs, improve risk management, etc",
        "The Organization follows some regulation that are related to ESG practices to comply with local legal requirements (Minimum wage, Act 446 etc)",
        "The Organization adopts ESG practices at overall level but does not quantify it to revenue generation and cost reduction, etc",
        "The Organization has a clear understanding of ESG practices, with ESG activities clearly contributing to revenue growth, helping to reduce costs and manage risk, beneficial to employee engagement, etc"
    ]
    st.radio("Select one", options=business_case, key='iesg_q10_business_case', index=None)
    
    st.divider()
    
    # Q11: ESG Goals
    st.subheader("11. How would you describe your ESG targets and goals? *")
    goals = [
        "The Organization has no targets and goals in relation to ESG commitments",
        "The Organization has some goals and targets relating to ESG but these are not well organized and are not comprehensive",
        "The Organization has a well-defined set of goals and targets relating to ESG",
        "The Organization has a set of comprehensive targets and goals that it wishes to achieve with deadlines, and communicates such targets and goals publicly and within the Organization, including KPIs"
    ]
    st.radio("Select one", options=goals, key='iesg_q11_esg_goals', index=None)
    
    st.divider()
    
    # Q12: ESG Leadership
    st.subheader("12. Who leads ESG in your organization? *")
    leadership = [
        "There is no clear ESG leader within the Organization",
        "Led by officer who has multiple roles in the Organization such as HR, Admin and Finance",
        "There is a leader within the Organization to ESG matters who has limited authority",
        "Organization has a clear ESG leader (Chief Sustainability Officer) with clear KPIs and targets, who has the role and authority to drive the ESG program, reports to the Board and makes decisions"
    ]
    st.radio("Select one", options=leadership, key='iesg_q12_esg_leadership', index=None)
    
    st.divider()
    
    # Q13: ESG Reporting Standards
    st.subheader("13. How do you report on ESG? *")
    reporting = [
        "The Organization doesn't disclose information on its ESG impact and agenda and doesn't have an ESG rating",
        "The Organization provides limited information on ESG in its non-financial reporting, and does not report against a known framework such as GRI or TCFD",
        "The Organization includes significant information on ESG matters in its non-financial reporting but has limited interaction with rating agencies",
        "The Organization has solicited an ESG rating from a recognised rating agency such as GRI and TCFD and the management communicates regularly with the rating agency"
    ]
    st.radio("Select one", options=reporting, key='iesg_q13_esg_reporting', index=None)
    
    st.divider()
    
    # Q14: Data Understanding
    st.subheader("14. How well do you understand the data required for external ESG reporting? *")
    data_understanding = [
        "The Organization has not assessed what data is required for any sustainability reporting",
        "The Organization has a limited understanding of the data required for sustainability reporting",
        "The Organization has a good understanding of the data required for sustainability reporting and report them externally",
        "The Organization has assessed what data is required for external reporting of ESG matters and has put in place processes to be able to publish external reports in high quality and detail (GRI, TCFD, etc)"
    ]
    st.radio("Select one", options=data_understanding, key='iesg_q14_data_understanding', index=None)
    
    st.divider()
    
    # Q15: ESG Elements
    st.subheader("15. Does your ESG program cover the key E, S, and G elements identified by stakeholders? *")
    elements = [
        "There is no ESG program within the Organization",
        "The Organization has a limited plan in place that deals with only some limited aspects of E, S and G",
        "The Organization has a solid selected ESG programs in place across some elements of E, S and G",
        "The Organization has a comprehensive ESG program in place that covers appropriately and completely all areas of E, S and G that have been determined to the of importance to the Organization and its stakeholders based on the ESG strategy"
    ]
    st.radio("Select one", options=elements, key='iesg_q15_esg_elements', index=None)
    
    st.divider()
    
    # Q16: Validation
    st.subheader("16. How are your ESG disclosures validated? *")
    validation = [
        "There is no independent external validation of the ESG information and data reported publicly by the Organization, or no information is reported",
        "The Organization has internal auditor and considering the use of external auditors to validate the information published in the non-financial disclosures",
        "The Organization has its external ESG reporting verified/audited by an external auditor",
        "The Organization has its public communications and reporting on ESG independently reviewed and verified by an external specialised company"
    ]
    st.radio("Select one", options=validation, key='iesg_q16_validation', index=None)

# ============================================================================
# SECTION C: ENVIRONMENT
# ============================================================================
with tab3:
    st.header("🌍 Section C: Environment")
    
    # Q17: Carbon Footprint
    st.subheader("17. What is your carbon footprint reduction approach and ambition? *")
    carbon = [
        "The Organization has no Carbon Footprint Reduction program due to lack of knowledge on the methodology",
        "The Organization has decided and published modest carbon footprint reduction goals",
        "The Organization has decided and published ambitious carbon footprint reduction goals. A comprehensive programme has been established to attain the goals",
        "The Organization has publicly communicated a Net Zero target and commitments, and has a comprehensive plan and resources in place to achieve them, including reporting the progress on a regular basis"
    ]
    st.radio("Select one", options=carbon, key='iesg_q17_carbon', index=None)
    
    st.divider()
    
    # Q18: GHG Emissions
    st.subheader("18. How do you manage and reduce GHG emissions? *")
    ghg = [
        "The Organization has no GHG Emissions monitoring in place, with no specific targets, and no goals publicly communicated",
        "The Organization has published GHG emissions and decided on the reduction goals",
        "The Organization has decided and published ambitious GHG emissions reduction goals. A comprehensive programme has been established to attain the goals",
        "The Organization has publicly communicated a GHG emissions monitoring, and has a comprehensive plan and resources in place to achieve them, including reporting the progress on a regular basis"
    ]
    st.radio("Select one", options=ghg, key='iesg_q18_ghg', index=None)
    
    st.divider()
    
    # Q19: Water Efficiency
    st.subheader("19. How do you manage water efficiency? *")
    water = [
        "The Organization has no water efficiency management",
        "The Organization has decided and published modest water efficiency management",
        "The Organization monitor and report water use and quality by tracking these metrics, businesses can identify areas for improvement and demonstrate their commitment to water stewardship",
        "The Organization has Implemented water-efficient technologies and practices: This includes measures such as water-efficient irrigation and using recycled water"
    ]
    st.radio("Select one", options=water, key='iesg_q19_water', index=None)
    
    st.divider()
    
    # Q20: Material, Waste and Effluent
    st.subheader("20. How do you manage materials, waste, and effluent impacts? *")
    waste = [
        "The Organization has no sustainable material sourcing management",
        "The Organization has decided and published modest sustainable material sourcing management",
        "The Organization has practised a comprehensive waste-related impact management",
        "The Organization has an extensive action on waste-related impacts management"
    ]
    st.radio("Select one", options=waste, key='iesg_q20_waste', index=None)
    
    st.divider()
    
    # Q21: Waste-Water Management
    st.subheader("21. How do you manage wastewater? *")
    wastewater = [
        "The Organization has no effort to improve the quality of its wastewater and discharged water management",
        "The Organization record and report the amount of water used by the company",
        "The Organization has an extensive effort to improve the quality of its wastewater and discharged water such minimising wastewater",
        "The Organization has communicated about waste-water by engaging with stakeholders, including local communities, water authorities, and NGOs, to understand local water-related risks and opportunities and to develop solutions collaboratively"
    ]
    st.radio("Select one", options=wastewater, key='iesg_q21_wastewater', index=None)
    
    st.divider()
    
    # Q22: Energy Consumption
    st.subheader("22. How do you manage and reduce energy consumption? *")
    energy = [
        "The Organization has no efficient practise on energy consumed – electricity, gas or steam water",
        "The Organization has minimum effort to reduce energy consumption such as swicthing off the light during lunch hour",
        "The Organization record and control the energy consumption, and gradually reduce and optimise energy consumption",
        "The Organization maximize energy efficiency by taking a holistic approach: consider low-cost and high-impact changes such as installing solar panels"
    ]
    st.radio("Select one", options=energy, key='iesg_q22_energy', index=None)
    
    st.divider()
    
    # Q23: Biodiversity
    st.subheader("23. How do you address biodiversity impacts? *")
    biodiversity = [
        "The Organization has no effort to preserve and conserve the survival of biodiversity",
        "The Organization has minimal efforts of in ensuring the survival of biodiversity",
        "The Organization always consider their operation with the respect to its impact on biodiversity",
        "The Organization has implemented prevention and remediation activities with respect to its impact on biodiversity by collaborating with NGOs"
    ]
    st.radio("Select one", options=biodiversity, key='iesg_q23_biodiversity', index=None)
    
    st.divider()
    
    # Q24: Eco-Friendly Materials
    st.subheader("24. Do you use eco‑friendly raw materials? *")
    eco_materials = [
        "The Organization does not use eco-friendly raw material in business operation",
        "The Organization exploring and planning to use eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)",
        "The Organization uses eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)",
        "The Organization only uses eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)"
    ]
    st.radio("Select one", options=eco_materials, key='iesg_q24_eco_materials', index=None)
    
    st.divider()
    
    # Q25: Reforestation
    st.subheader("25. Do you conduct or support reforestation activities? *")
    reforestation = [
        "The Organization does not conduct any reforestation program",
        "Organization planning to implement reforestation program",
        "Organization has initiated a in-house reforestation program to contribute to environmental sustainability",
        "Organization has conducted thorough assessments of deforested areas and collaborate with environmental experts and local communities to implement sustainable reforestation strategies"
    ]
    st.radio("Select one", options=reforestation, key='iesg_q25_reforestation', index=None)

# ============================================================================
# SECTION D: SOCIAL
# ============================================================================
with tab4:
    st.header("👥 Section D: Social")
    
    # Q26: Employee Involvement
    st.subheader("26. How involved are employees in your ESG efforts? *")
    employee_involvement = [
        "The Organization does not address ESG matters with its employees and does not solicit feedback or input from its employees",
        "Employees are involved, but mostly in community actions and social matters",
        "The Board sponsors initiatives in the ESG space and communication on such initiatives internally with employees",
        "The Organization extensively communicates with its employees on the importance of ESG, the Organization's ESG programme and how employees can be involved in and support the ESG aspirations of the Organization"
    ]
    st.radio("Select one", options=employee_involvement, key='iesg_q26_employee_involvement', index=None)
    
    st.divider()
    
    # Q27: Domestic Labour Laws
    st.subheader("27. How do you comply with domestic labour laws and regulations? *")
    domestic_labour = [
        "The Organisation is unaware with the labour laws and regulations in the country",
        "The Organization strives to comply with all basic labour laws and regulations in the country",
        "The Organization is committed in maintaining a comprehensive understanding of labour laws and regulations. The organization actively train employees on their rights and responsibilities, conduct internal audits, and promptly address any compliance gaps that may arise",
        "The Organization goes beyond mere compliance and takes a proactive approach to stay ahead of changes in labour laws and regulations. Dedicated teams were formed to engage with Labour Department and Ministry of Human Resource, and a robust systems in place for interpreting complex labour laws, managing external audits, and continuously improving processes to ensure ongoing compliance"
    ]
    st.radio("Select one", options=domestic_labour, key='iesg_q27_domestic_labour', index=None)
    
    st.divider()
    
    # Q28: International Labour Laws
    st.subheader("28. How do you align with international labour laws and standards? *")
    intl_labour = [
        "The Organization lack of understanding on the international labour laws and regulations",
        "The organization recognizes the importance of complying with basic international labour laws and regulations, and adhere to fundamental principles",
        "The Organization is up to date with a wide range of international labour laws and regulations, actively monitor and comply with standards set by organizations such as the International Labour Organization (ILO)",
        "The Organization proactively engage in continuous improvement initiatives, regularly conduct internal audits, and participate in external certifications to demonstrate high standards commitment of labor practices"
    ]
    st.radio("Select one", options=intl_labour, key='iesg_q28_intl_labour', index=None)
    
    st.divider()
    
    # Q29: Equal Employment
    st.subheader("29. How do you ensure equal employment and promotion opportunities? *")
    equal_employment = [
        "Organization does not set target to achieve equal employment and promotion opportunities",
        "Organization is committed to providing equal employment and promotion opportunities to all employees, and adhere to the basic principles of fairness and non-discrimination",
        "Organization actively promotes diversity and inclusion in the workforce by implementing policies and practices that prevent discrimination based on factors such as race, gender, age, religion, and disability. Training and awareness programs provided to foster an inclusive environment and ensure fair treatment throughout the employment lifecycle",
        "Organization has implemented comprehensive strategies to proactively identify and address any systemic barriers that may hinder equal opportunities through mentorship and sponsorship programs, internal mobility initiatives, and talent development programs to ensure that individuals from all backgrounds have equal access to career advancement and promotional opportunities"
    ]
    st.radio("Select one", options=equal_employment, key='iesg_q29_equal_employment', index=None)
    
    st.divider()
    
    # Q30: Minimum Wage
    st.subheader("30. How do you meet or exceed minimum wage requirements? *")
    min_wage = [
        "Organization pays wages lower than the national minimum wage requirement",
        "Organization ensures that all employees are paid at least the minimum wage mandated by the applicable labour laws and regulations",
        "Organization not only meets the minimum wage requirements but also considers factors such as cost of living and industry standards when determining employee compensation. Periodic reviews is conducted to ensure that wage rates remain competitive and equitable within the industry",
        "Organization proactively assess and adjust the compensation structure to provide a living wage that enables employees to meet their basic needs and maintain a decent standard of living, and adopt progressive wage policies to support the financial well-being to the workforce"
    ]
    st.radio("Select one", options=min_wage, key='iesg_q30_min_wage', index=None)
    
    st.divider()
    
    # Q31: Health & Safety
    st.subheader("31. How do you manage occupational health and safety? *")
    health_safety = [
        "Organization does not meet with the basic safety requirement",
        "Organization provide a safe and healthy work environment by identifying and addressing potential hazards, providing basic safety training to employees, and implementing necessary safety measures",
        "Organization actively maintains compliance with OSHA regulations by regularly conducting comprehensive workplace risk assessments and implementing appropriate control measures. Safety committees is established to provide ongoing safety training programs, and maintain records of incidents and near-misses to continuously improve safety practices",
        "Organization adopting proactive safety measures and promoting a culture of safety throughout the workforce. Conduct regular safety audit, engage employees in safety programs and initiatives, and invest in advanced technologies and equipment to enhance workplace safety according to OSHA"
    ]
    st.radio("Select one", options=health_safety, key='iesg_q31_health_safety', index=None)
    
    st.divider()
    
    # Q32: Grievance Handling
    st.subheader("32. Do you have a formal grievance handling process? *")
    grievance = [
        "Organization does not practice a formal grievance handling procedures",
        "Organization has established a basic formal grievance handling procedure to address employee concerns and complaints",
        "Organization has developed a comprehensive formal grievance handling procedure that includes clear guidelines and steps for reporting, investigating, and resolving grievances. Designated personnel being trained to handle grievances effectively",
        "Organization has established multiple channels for employees to report grievances, including anonymous options, and actively promote a culture of transparency and trust. Regular audits of the grievance handling process conducted to identify areas for improvement and ensure that resolutions are fair and sustainable"
    ]
    st.radio("Select one", options=grievance, key='iesg_q32_grievance', index=None)
    
    st.divider()
    
    # Q33: Upskilling
    st.subheader("33. How do you upskill and develop your workforce? *")
    upskilling = [
        "Organization does not conduct regular training to upskill workers",
        "Organization recognizes the importance of training and conduct basic skills development programs for workers",
        "Organization is committed to the continuous upskilling of workers and conducts regular training programs to improve their technical skills and knowledge",
        "Organization takes a proactive approach to upskilling workers and invests significantly in their professional development. Robust training and development framework is introduced that includes comprehensive skill enhancement programs, leadership development initiatives, and access to advanced learning resources"
    ]
    st.radio("Select one", options=upskilling, key='iesg_q33_upskilling', index=None)
    
    st.divider()
    
    # Q34: Community
    st.subheader("34. How do you contribute to and support the community? *")
    community = [
        "Organization does not provide sponsorships or donations to the community",
        "Organization provides basic sponsorships or donations to local community organizations or events",
        "Organization actively engages in community outreach and support by providing regular sponsorships or donations to various community organizations, nonprofits, and social causes",
        "Organization is deeply committed to corporate social responsibility and actively invest in the betterment of the community. Establish dedicated programs and initiatives to support community development, education, healthcare, and environmental sustainability"
    ]
    st.radio("Select one", options=community, key='iesg_q34_community', index=None)

# ============================================================================
# SECTION E: GOVERNANCE
# ============================================================================
with tab5:
    st.header("⚖️ Section E: Governance")
    
    # Q35: Board Leadership
    st.subheader("35. How involved is the Board in ESG leadership? *")
    board_leadership = [
        "The Board is not involved in ESG matters",
        "Leadership is delegated to one board member",
        "Organization has a dedicated board sub-committee for ESG matters",
        "The Board takes clear active leadership on the ESG agenda and regularly discusses risk and opportunities. The ESG agenda and company plans are communicated internally throughout the Organization"
    ]
    st.radio("Select one", options=board_leadership, key='iesg_q35_board_leadership', index=None)
    
    st.divider()
    
    # Q36: Board Awareness
    st.subheader("36. How aware are the Board and management of ESG risks and regulations? *")
    board_awareness = [
        "The Board or management team have a low understanding of the risk management and regulatory environment affecting their business with regard to ESG topics and are not taking a coordinated approach to ensuring regulatory compliance",
        "The Organization has a limited understanding of the risk and regulatory impacts of ESG and is implementing change based on individual directives rather than having a comprehensive approach",
        "The Board and management are actively dealing with ESG risks and regulatory requirement with a good understanding of the implications of the regulations",
        "The Board and management have strong expertise in the ESG risks management and regulations areas relating to ESG as they impact the business, and have clear and comprehensive programmes in place"
    ]
    st.radio("Select one", options=board_awareness, key='iesg_q36_board_awareness', index=None)
    
    st.divider()
    
    # Q37: Organization Strategy
    st.subheader("37. How would you describe your organization's strategy? *")
    strategy = [
        "Organization does not have a documented vision, mission, values and principles",
        "Organization has a basic strategy in place to guide operations and decision-making",
        "Organization has developed a comprehensive strategy that aligns with long-term mission, vision and principle",
        "Organization has an advanced and dynamic strategy that enables to stay ahead of the competition and drive sustainable growth"
    ]
    st.radio("Select one", options=strategy, key='iesg_q37_strategy', index=None)
    
    st.divider()
    
    # Q38: Code of Conduct
    st.subheader("38. How is your Code of Conduct communicated? *")
    code_conduct = [
        "Organization does not publish code of conduct",
        "Organization has a basic communication process for the Code of Conduct",
        "Organization has implemented a comprehensive communication plan for the Code of Conduct",
        "Organization excels in the communication of the Code of Conduct through robust communication strategy that includes multiple channels and methods to reach all employees effectively"
    ]
    st.radio("Select one", options=code_conduct, key='iesg_q38_code_conduct', index=None)
    
    st.divider()
    
    # Q39: Anti-Corruption
    st.subheader("39. What anti‑corruption management system do you have? *")
    anti_corruption = [
        "Organization does not have any anti-corruption management system",
        "Organization has a basic in-house anti-corruption management system in place.",
        "Organization has implemented a comprehensive anti-corruption management system. Established clear procedures and controls to prevent corruption in all aspects of operations",
        "Organization has a incorporated anti-corruption management system comprehensively and obtained internationally recognized certifications such as ISO 37001: Anti-Bribery Management Systems. The anti-bribery policies and procedures are integrated into our overall governance framework"
    ]
    st.radio("Select one", options=anti_corruption, key='iesg_q39_anti_corruption', index=None)
    
    st.divider()
    
    # Q40: Whistleblower
    st.subheader("40. Do you have an effective whistleblower program? *")
    whistleblower = [
        "Organization does not have any whistleblower program",
        "Organization is planning to have a whistleblower program",
        "Organization has developed a comprehensive whistle blower procedure that includes clear guidelines and steps for reporting, investigating, and resolving. Designated team is formed to handle complaints effectively",
        "Organization has established multiple channels to report any types of corruption and actively promote a culture of transparency and trust. Regular audits of the complaint handling process conducted to identify areas for improvement and ensure that resolutions are fair"
    ]
    st.radio("Select one", options=whistleblower, key='iesg_q40_whistleblower', index=None)
    
    st.divider()
    
    # Q41: Accounting System
    st.subheader("41. How robust and transparent is your accounting system? *")
    accounting = [
        "Organization does not have an accurate and transparent accounting method",
        "Organization has basic accounting system such as P&L, Balance Sheet and Cash Flow",
        "Organization uses a standard accounting method",
        "Organization uses accurate and transparent accounting method that verified by external experties"
    ]
    st.radio("Select one", options=accounting, key='iesg_q41_accounting', index=None)
    
    st.divider()
    
    # Q42: Data Privacy
    st.subheader("42. How do you protect privacy and manage data security? *")
    data_privacy = [
        "Organization does not have a clear data protection, privacy and data protection scheme",
        "Organization is planning to set a clear data protection, privacy and data protection scheme",
        "Organization has a basic data protection, privacy and data protection scheme according to Personal Data Protection Act 2010",
        "Organization has a comprehensive data protection, privacy and data protection scheme according to Personal Data Protection Act 2010, Computer Crime Act 1997 and Consumer Protection Act 1999"
    ]
    st.radio("Select one", options=data_privacy, key='iesg_q42_data_privacy', index=None)

# ============================================================================
# SCORING SYSTEM
# ============================================================================
def calculate_score():
    """Calculate ESG Readiness Score (Q8-Q42)"""
    score = 0
    max_score = 108  # 35 questions x 3 points + Q9 (6 points)
    
    # Score mapping for questions (0-3 points each)
    # First option = 0 points, Last option = 3 points
    score_map = {
        'iesg_q8_maturity': [
            "We have not started our sustainability journey yet",  # 0
            "We have started, but we should be doing more",  # 1
            "We are progressing well, but there is room for improvement",  # 2
            "We are very advanced"  # 3
        ],
        'iesg_q10_business_case': [
            "The Organization does not understand how ESG can present opportunities to enhance revenue, reduce costs, improve risk management, etc",
            "The Organization follows some regulation that are related to ESG practices to comply with local legal requirements (Minimum wage, Act 446 etc)",
            "The Organization adopts ESG practices at overall level but does not quantify it to revenue generation and cost reduction, etc",
            "The Organization has a clear understanding of ESG practices, with ESG activities clearly contributing to revenue growth, helping to reduce costs and manage risk, beneficial to employee engagement, etc"
        ],
        'iesg_q11_esg_goals': [
            "The Organization has no targets and goals in relation to ESG commitments",
            "The Organization has some goals and targets relating to ESG but these are not well organized and are not comprehensive",
            "The Organization has a well-defined set of goals and targets relating to ESG",
            "The Organization has a set of comprehensive targets and goals that it wishes to achieve with deadlines, and communicates such targets and goals publicly and within the Organization, including KPIs"
        ],
        'iesg_q12_esg_leadership': [
            "There is no clear ESG leader within the Organization",
            "Led by officer who has multiple roles in the Organization such as HR, Admin and Finance",
            "There is a leader within the Organization to ESG matters who has limited authority",
            "Organization has a clear ESG leader (Chief Sustainability Officer) with clear KPIs and targets, who has the role and authority to drive the ESG program, reports to the Board and makes decisions"
        ],
        'iesg_q13_esg_reporting': [
            "The Organization doesn't disclose information on its ESG impact and agenda and doesn't have an ESG rating",
            "The Organization provides limited information on ESG in its non-financial reporting, and does not report against a known framework such as GRI or TCFD",
            "The Organization includes significant information on ESG matters in its non-financial reporting but has limited interaction with rating agencies",
            "The Organization has solicited an ESG rating from a recognised rating agency such as GRI and TCFD and the management communicates regularly with the rating agency"
        ],
        'iesg_q14_data_understanding': [
            "The Organization has not assessed what data is required for any sustainability reporting",
            "The Organization has a limited understanding of the data required for sustainability reporting",
            "The Organization has a good understanding of the data required for sustainability reporting and report them externally",
            "The Organization has assessed what data is required for external reporting of ESG matters and has put in place processes to be able to publish external reports in high quality and detail (GRI, TCFD, etc)"
        ],
        'iesg_q15_esg_elements': [
            "There is no ESG program within the Organization",
            "The Organization has a limited plan in place that deals with only some limited aspects of E, S and G",
            "The Organization has a solid selected ESG programs in place across some elements of E, S and G",
            "The Organization has a comprehensive ESG program in place that covers appropriately and completely all areas of E, S and G that have been determined to the of importance to the Organization and its stakeholders based on the ESG strategy"
        ],
        'iesg_q16_validation': [
            "There is no independent external validation of the ESG information and data reported publicly by the Organization, or no information is reported",
            "The Organization has internal auditor and considering the use of external auditors to validate the information published in the non-financial disclosures",
            "The Organization has its external ESG reporting verified/audited by an external auditor",
            "The Organization has its public communications and reporting on ESG independently reviewed and verified by an external specialised company"
        ],
        'iesg_q17_carbon': [
            "The Organization has no Carbon Footprint Reduction program due to lack of knowledge on the methodology",
            "The Organization has decided and published modest carbon footprint reduction goals",
            "The Organization has decided and published ambitious carbon footprint reduction goals. A comprehensive programme has been established to attain the goals",
            "The Organization has publicly communicated a Net Zero target and commitments, and has a comprehensive plan and resources in place to achieve them, including reporting the progress on a regular basis"
        ],
        'iesg_q18_ghg': [
            "The Organization has no GHG Emissions monitoring in place, with no specific targets, and no goals publicly communicated",
            "The Organization has published GHG emissions and decided on the reduction goals",
            "The Organization has decided and published ambitious GHG emissions reduction goals. A comprehensive programme has been established to attain the goals",
            "The Organization has publicly communicated a GHG emissions monitoring, and has a comprehensive plan and resources in place to achieve them, including reporting the progress on a regular basis"
        ],
        'iesg_q19_water': [
            "The Organization has no water efficiency management",
            "The Organization has decided and published modest water efficiency management",
            "The Organization monitor and report water use and quality by tracking these metrics, businesses can identify areas for improvement and demonstrate their commitment to water stewardship",
            "The Organization has Implemented water-efficient technologies and practices: This includes measures such as water-efficient irrigation and using recycled water"
        ],
        'iesg_q20_waste': [
            "The Organization has no sustainable material sourcing management",
            "The Organization has decided and published modest sustainable material sourcing management",
            "The Organization has practised a comprehensive waste-related impact management",
            "The Organization has an extensive action on waste-related impacts management"
        ],
        'iesg_q21_wastewater': [
            "The Organization has no effort to improve the quality of its wastewater and discharged water management",
            "The Organization record and report the amount of water used by the company",
            "The Organization has an extensive effort to improve the quality of its wastewater and discharged water such minimising wastewater",
            "The Organization has communicated about waste-water by engaging with stakeholders, including local communities, water authorities, and NGOs, to understand local water-related risks and opportunities and to develop solutions collaboratively"
        ],
        'iesg_q22_energy': [
            "The Organization has no efficient practise on energy consumed – electricity, gas or steam water",
            "The Organization has minimum effort to reduce energy consumption such as swicthing off the light during lunch hour",
            "The Organization record and control the energy consumption, and gradually reduce and optimise energy consumption",
            "The Organization maximize energy efficiency by taking a holistic approach: consider low-cost and high-impact changes such as installing solar panels"
        ],
        'iesg_q23_biodiversity': [
            "The Organization has no effort to preserve and conserve the survival of biodiversity",
            "The Organization has minimal efforts of in ensuring the survival of biodiversity",
            "The Organization always consider their operation with the respect to its impact on biodiversity",
            "The Organization has implemented prevention and remediation activities with respect to its impact on biodiversity by collaborating with NGOs"
        ],
        'iesg_q24_eco_materials': [
            "The Organization does not use eco-friendly raw material in business operation",
            "The Organization exploring and planning to use eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)",
            "The Organization uses eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)",
            "The Organization only uses eco-friendly raw materials in business operation (e.g. recycled rubber, biodegradable plastics, compostable straws and others)"
        ],
        'iesg_q25_reforestation': [
            "The Organization does not conduct any reforestation program",
            "Organization planning to implement reforestation program",
            "Organization has initiated a in-house reforestation program to contribute to environmental sustainability",
            "Organization has conducted thorough assessments of deforested areas and collaborate with environmental experts and local communities to implement sustainable reforestation strategies"
        ],
        'iesg_q26_employee_involvement': [
            "The Organization does not address ESG matters with its employees and does not solicit feedback or input from its employees",
            "Employees are involved, but mostly in community actions and social matters",
            "The Board sponsors initiatives in the ESG space and communication on such initiatives internally with employees",
            "The Organization extensively communicates with its employees on the importance of ESG, the Organization's ESG programme and how employees can be involved in and support the ESG aspirations of the Organization"
        ],
        'iesg_q27_domestic_labour': [
            "The Organisation is unaware with the labour laws and regulations in the country",
            "The Organization strives to comply with all basic labour laws and regulations in the country",
            "The Organization is committed in maintaining a comprehensive understanding of labour laws and regulations. The organization actively train employees on their rights and responsibilities, conduct internal audits, and promptly address any compliance gaps that may arise",
            "The Organization goes beyond mere compliance and takes a proactive approach to stay ahead of changes in labour laws and regulations. Dedicated teams were formed to engage with Labour Department and Ministry of Human Resource, and a robust systems in place for interpreting complex labour laws, managing external audits, and continuously improving processes to ensure ongoing compliance"
        ],
        'iesg_q28_intl_labour': [
            "The Organization lack of understanding on the international labour laws and regulations",
            "The organization recognizes the importance of complying with basic international labour laws and regulations, and adhere to fundamental principles",
            "The Organization is up to date with a wide range of international labour laws and regulations, actively monitor and comply with standards set by organizations such as the International Labour Organization (ILO)",
            "The Organization proactively engage in continuous improvement initiatives, regularly conduct internal audits, and participate in external certifications to demonstrate high standards commitment of labor practices"
        ],
        'iesg_q29_equal_employment': [
            "Organization does not set target to achieve equal employment and promotion opportunities",
            "Organization is committed to providing equal employment and promotion opportunities to all employees, and adhere to the basic principles of fairness and non-discrimination",
            "Organization actively promotes diversity and inclusion in the workforce by implementing policies and practices that prevent discrimination based on factors such as race, gender, age, religion, and disability. Training and awareness programs provided to foster an inclusive environment and ensure fair treatment throughout the employment lifecycle",
            "Organization has implemented comprehensive strategies to proactively identify and address any systemic barriers that may hinder equal opportunities through mentorship and sponsorship programs, internal mobility initiatives, and talent development programs to ensure that individuals from all backgrounds have equal access to career advancement and promotional opportunities"
        ],
        'iesg_q30_min_wage': [
            "Organization pays wages lower than the national minimum wage requirement",
            "Organization ensures that all employees are paid at least the minimum wage mandated by the applicable labour laws and regulations",
            "Organization not only meets the minimum wage requirements but also considers factors such as cost of living and industry standards when determining employee compensation. Periodic reviews is conducted to ensure that wage rates remain competitive and equitable within the industry",
            "Organization proactively assess and adjust the compensation structure to provide a living wage that enables employees to meet their basic needs and maintain a decent standard of living, and adopt progressive wage policies to support the financial well-being to the workforce"
        ],
        'iesg_q31_health_safety': [
            "Organization does not meet with the basic safety requirement",
            "Organization provide a safe and healthy work environment by identifying and addressing potential hazards, providing basic safety training to employees, and implementing necessary safety measures",
            "Organization actively maintains compliance with OSHA regulations by regularly conducting comprehensive workplace risk assessments and implementing appropriate control measures. Safety committees is established to provide ongoing safety training programs, and maintain records of incidents and near-misses to continuously improve safety practices",
            "Organization adopting proactive safety measures and promoting a culture of safety throughout the workforce. Conduct regular safety audit, engage employees in safety programs and initiatives, and invest in advanced technologies and equipment to enhance workplace safety according to OSHA"
        ],
        'iesg_q32_grievance': [
            "Organization does not practice a formal grievance handling procedures",
            "Organization has established a basic formal grievance handling procedure to address employee concerns and complaints",
            "Organization has developed a comprehensive formal grievance handling procedure that includes clear guidelines and steps for reporting, investigating, and resolving grievances. Designated personnel being trained to handle grievances effectively",
            "Organization has established multiple channels for employees to report grievances, including anonymous options, and actively promote a culture of transparency and trust. Regular audits of the grievance handling process conducted to identify areas for improvement and ensure that resolutions are fair and sustainable"
        ],
        'iesg_q33_upskilling': [
            "Organization does not conduct regular training to upskill workers",
            "Organization recognizes the importance of training and conduct basic skills development programs for workers",
            "Organization is committed to the continuous upskilling of workers and conducts regular training programs to improve their technical skills and knowledge",
            "Organization takes a proactive approach to upskilling workers and invests significantly in their professional development. Robust training and development framework is introduced that includes comprehensive skill enhancement programs, leadership development initiatives, and access to advanced learning resources"
        ],
        'iesg_q34_community': [
            "Organization does not provide sponsorships or donations to the community",
            "Organization provides basic sponsorships or donations to local community organizations or events",
            "Organization actively engages in community outreach and support by providing regular sponsorships or donations to various community organizations, nonprofits, and social causes",
            "Organization is deeply committed to corporate social responsibility and actively invest in the betterment of the community. Establish dedicated programs and initiatives to support community development, education, healthcare, and environmental sustainability"
        ],
        'iesg_q35_board_leadership': [
            "The Board is not involved in ESG matters",
            "Leadership is delegated to one board member",
            "Organization has a dedicated board sub-committee for ESG matters",
            "The Board takes clear active leadership on the ESG agenda and regularly discusses risk and opportunities. The ESG agenda and company plans are communicated internally throughout the Organization"
        ],
        'iesg_q36_board_awareness': [
            "The Board or management team have a low understanding of the risk management and regulatory environment affecting their business with regard to ESG topics and are not taking a coordinated approach to ensuring regulatory compliance",
            "The Organization has a limited understanding of the risk and regulatory impacts of ESG and is implementing change based on individual directives rather than having a comprehensive approach",
            "The Board and management are actively dealing with ESG risks and regulatory requirement with a good understanding of the implications of the regulations",
            "The Board and management have strong expertise in the ESG risks management and regulations areas relating to ESG as they impact the business, and have clear and comprehensive programmes in place"
        ],
        'iesg_q37_strategy': [
            "Organization does not have a documented vision, mission, values and principles",
            "Organization has a basic strategy in place to guide operations and decision-making",
            "Organization has developed a comprehensive strategy that aligns with long-term mission, vision and principle",
            "Organization has an advanced and dynamic strategy that enables to stay ahead of the competition and drive sustainable growth"
        ],
        'iesg_q38_code_conduct': [
            "Organization does not publish code of conduct",
            "Organization has a basic communication process for the Code of Conduct",
            "Organization has implemented a comprehensive communication plan for the Code of Conduct",
            "Organization excels in the communication of the Code of Conduct through robust communication strategy that includes multiple channels and methods to reach all employees effectively"
        ],
        'iesg_q39_anti_corruption': [
            "Organization does not have any anti-corruption management system",
            "Organization has a basic in-house anti-corruption management system in place.",
            "Organization has implemented a comprehensive anti-corruption management system. Established clear procedures and controls to prevent corruption in all aspects of operations",
            "Organization has a incorporated anti-corruption management system comprehensively and obtained internationally recognized certifications such as ISO 37001: Anti-Bribery Management Systems. The anti-bribery policies and procedures are integrated into our overall governance framework"
        ],
        'iesg_q40_whistleblower': [
            "Organization does not have any whistleblower program",
            "Organization is planning to have a whistleblower program",
            "Organization has developed a comprehensive whistle blower procedure that includes clear guidelines and steps for reporting, investigating, and resolving. Designated team is formed to handle complaints effectively",
            "Organization has established multiple channels to report any types of corruption and actively promote a culture of transparency and trust. Regular audits of the complaint handling process conducted to identify areas for improvement and ensure that resolutions are fair"
        ],
        'iesg_q41_accounting': [
            "Organization does not have an accurate and transparent accounting method",
            "Organization has basic accounting system such as P&L, Balance Sheet and Cash Flow",
            "Organization uses a standard accounting method",
            "Organization uses accurate and transparent accounting method that verified by external experties"
        ],
        'iesg_q42_data_privacy': [
            "Organization does not have a clear data protection, privacy and data protection scheme",
            "Organization is planning to set a clear data protection, privacy and data protection scheme",
            "Organization has a basic data protection, privacy and data protection scheme according to Personal Data Protection Act 2010",
            "Organization has a comprehensive data protection, privacy and data protection scheme according to Personal Data Protection Act 2010, Computer Crime Act 1997 and Consumer Protection Act 1999"
        ],
    }
    
    # Calculate score for each question (Q8, Q10-Q42)
    for key, options in score_map.items():
        answer = st.session_state.get(key, None)
        # Only score if answer is not None
        if answer and answer in options:
            score += options.index(answer)
    
    # Q9: Stakeholder engagements (1 point per checkbox, max 6)
    # "None of the above" doesn't count
    stakeholders = st.session_state.get('iesg_q9_stakeholders', [])
    stakeholder_score = len([s for s in stakeholders if s != "None of the above"])
    score += min(stakeholder_score, 6)
    
    percentage = (score / max_score * 100) if max_score > 0 else 0
    
    return score, max_score, percentage

# ============================================================================
# PDF GENERATION & DOWNLOAD
# ============================================================================
st.divider()
st.header("📥 Actions & Download")

# Show unsaved warning if applicable
# Initialize manual save helper (no auto-save, user must click save button)
auto_save = IESGAutoSave(st.session_state.get('company_id'), assessment_period="2024")

# Collect all response data for saving
def get_all_iesg_responses():
    """Collect the questionnaire answers from session state (without the 'iesg_' prefix)"""
    return {
        field: st.session_state.get(f'iesg_{field}', default_iesg_value(field))
        for field in IESG_DEFAULTS
    }

# Real-time change tracking (without forcing DB reload)
current_iesg_responses = get_all_iesg_responses()
st.session_state[ANSWERS_KEY] = current_iesg_responses
current_iesg_snapshot = json.dumps(current_iesg_responses, sort_keys=True, default=str)
previous_iesg_snapshot = st.session_state.get('iesg_last_snapshot')

if previous_iesg_snapshot is None:
    st.session_state['iesg_last_snapshot'] = current_iesg_snapshot
elif current_iesg_snapshot != previous_iesg_snapshot:
    st.session_state.iesg_unsaved_changes = True
    st.session_state['iesg_last_snapshot'] = current_iesg_snapshot

# Show unsaved warning if applicable
show_iesg_unsaved_warning()

# Action buttons row
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    if st.button("💾 Save Responses", type="secondary", use_container_width=True):
        progress_score = calculate_progress()
        responses = get_all_iesg_responses()
        success = auto_save.manual_save(responses, completion_score=progress_score)
        if success:
            st.session_state['iesg_last_snapshot'] = json.dumps(responses, sort_keys=True, default=str)
            st.rerun()

with col2:
    if st.button("📤 Submit Assessment", type="primary", use_container_width=True):
        progress_score = calculate_progress()
        responses = get_all_iesg_responses()
        
        # Calculate final score for submission
        final_score, max_score, percentage = calculate_score()
        
        success = auto_save.submit_responses(
            responses, 
            completion_score=progress_score,
            esg_readiness_score=int(percentage)
        )
        
        if success:
            st.success("✅ Assessment submitted successfully!")
            st.session_state.iesg_form_status = 'submitted'
            st.session_state.iesg_unsaved_changes = False
            st.session_state['iesg_last_snapshot'] = json.dumps(responses, sort_keys=True, default=str)
        else:
            st.error("❌ Failed to submit assessment. Please try again.")

with col3:
    if st.button("🎯 Calculate Score", type="secondary", use_container_width=True):
        score, max_score, percentage = calculate_score()
        st.session_state.iesg_score = score
        st.session_state.iesg_max_score = max_score
        st.session_state.iesg_percentage = percentage

with col4:
    if st.button("🔄 Refresh from DB", type="secondary", use_container_width=True,
                 help="Reload latest saved responses from database"):
        st.session_state['iesg_force_refresh'] = True
        st.rerun()

st.divider()

# Display score if calculated
if 'iesg_score' in st.session_state:
    score_col1, score_col2, score_col3 = st.columns(3)
    with score_col2:
        st.success(f"### 🎯 ESG Readiness Score: {st.session_state.iesg_score}/{st.session_state.iesg_max_score}")
        st.metric("Score Percentage", f"{st.session_state.iesg_percentage:.1f}%")
    
    # Score interpretation
    if st.session_state.iesg_percentage >= 80:
        st.info("🌟 **Excellent!** Your organization demonstrates strong ESG readiness and maturity.")
    elif st.session_state.iesg_percentage >= 60:
        st.info("✅ **Good Progress!** Your organization is on the right track with room for improvement.")
    elif st.session_state.iesg_percentage >= 40:
        st.warning("⚠️ **Developing.** Your organization has started the ESG journey but needs more comprehensive implementation.")
    else:
        st.warning("📍 **Getting Started.** Your organization is in the early stages of ESG implementation.")

st.divider()

# PDF Download section
st.header("📥 Download PDF Report")
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Validation check
    required_fields = [
        'iesg_company_name',
        'iesg_email'
    ]
    
    all_filled = all(st.session_state.get(field, '') != '' for field in required_fields)
    
    if not all_filled:
        st.warning("⚠️ Company Name and Email must be populated (auto-filled).")
    
    if st.button("📥 Generate PDF Report", type="primary", use_container_width=True, disabled=not all_filled):
        try:
            from core.esg_questionnaire_pdf import generate_iesg_pdf
            buffer = generate_iesg_pdf(st.session_state)
            filename = f"iESG_Ready_{st.session_state.iesg_company_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
            st.download_button(
                label="📥 Download PDF",
                data=buffer,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )
            st.success("✅ PDF generated successfully!")
        except ImportError:
            st.error("❌ Install ReportLab: `pip install reportlab`")
        except Exception as e:
            st.error(f"❌ Error generating PDF: {str(e)}")
            st.exception(e)

# Form tips info box
with st.expander("💡 Data Persistence Tips"):
    st.markdown("""
    - **Auto-Load**: Your data automatically loads from the database every time you visit this page
    - **Manual Save**: Click \"💾 Save Responses\" to save your progress to the database
    - **Submit**: Click \"📤 Submit Assessment\" to finalize your submission
    - **Download**: Generate and download a PDF report of your assessment
    - **Multi-Session**: Your data persists across sessions - close and reopen without losing progress (after saving)
    - **Remember**: Always click \"💾 Save Responses\" before leaving the page
    """)

st.divider()

# Footer
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>ESG Ready Questionnaire | Ministry of Investment, Trade and Industry (MITI)</p>
    <p>Your data is stored persistently in the database and never sent to external servers.</p>
</div>
""", unsafe_allow_html=True)
