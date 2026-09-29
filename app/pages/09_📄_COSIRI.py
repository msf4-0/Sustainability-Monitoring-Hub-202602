"""
COSIRI - Company Certificates and Reports Management
Upload, view, download, and manage company certificates and reports
"""
import streamlit as st
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.permissions import check_page_permission, show_permission_badge, has_permission
from core.cache import get_database
from components.company_verification import enforce_company_verification
from config.constants import REPORTING_PERIODS


# Check permissions
check_page_permission('09_📄_COSIRI.py')

st.set_page_config(page_title="COSIRI Documents", page_icon="📄", layout="wide")

# Enforce company verification
status = enforce_company_verification(st.session_state.get('company_id'))
if status == 'no_company':
    st.error("❌ No company assigned to your account. Please contact an administrator.")
    st.stop()

# Sidebar
with st.sidebar:
    show_permission_badge()
    st.write(f"**User:** {st.session_state.username}")
    if st.button("🚪 Logout", type="secondary", width='stretch'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("main.py")

st.title("📄 COSIRI Documents")
st.markdown("**Manage your company's certificates and reports**")
st.divider()

# Check user permissions
can_upload = has_permission(st.session_state.role, 'can_upload_cosiri_documents')
can_delete = has_permission(st.session_state.role, 'can_delete_cosiri_documents')
can_view = has_permission(st.session_state.role, 'can_view_cosiri_documents')

# Get database connection
db = get_database()
if not db.connect():
    st.error("❌ Failed to connect to database")
    st.stop()

try:
    # ============================================================================
    # UPLOAD SECTION (Admin & Manager only)
    # ============================================================================
    if can_upload:
        st.subheader("📤 Upload Document")
        
        with st.form("upload_document_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                document_type = st.selectbox(
                    "Document Type *",
                    options=['certificate', 'report'],
                    format_func=lambda x: '📜 Certificate' if x == 'certificate' else '📊 Report',
                    help="Select the type of document you're uploading"
                )
                
                current_year = str(datetime.now().year)
                default_index = REPORTING_PERIODS.index(current_year) if current_year in REPORTING_PERIODS else 0
                
                reporting_period = st.selectbox(
                    "Reporting Period",
                    REPORTING_PERIODS,
                    index=default_index,
                    help="The year this document covers (optional)"
                )
            
            with col2:
                notes = st.text_area(
                    "Notes (optional)",
                    placeholder="Add any relevant notes or comments about this document",
                    help="Additional context about the document"
                )
            
            uploaded_file = st.file_uploader(
                "Choose a file *",
                type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'],
                help="Supported formats: PDF, Word, Excel, Images"
            )
            
            submit_upload = st.form_submit_button("📤 Upload Document", type="primary", width="stretch")
        
        if submit_upload:
            if uploaded_file is None:
                st.error("⚠️ Please select a file to upload")
            else:
                # Read file content into memory
                file_content = uploaded_file.getbuffer().tobytes()
                
                # Save to database with file content as BLOB
                query = """
                    INSERT INTO cosiri_documents 
                    (company_id, uploaded_by, document_type, file_name, file_path,
                     file_content, file_size, mime_type, reporting_period, notes, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                """
                
                try:
                    saved = db.execute_query(
                        query,
                        (
                            st.session_state.company_id,
                            st.session_state.user_id,
                            document_type,
                            uploaded_file.name,
                            '',  # file_path is empty since we're storing in DB
                            file_content,
                            uploaded_file.size,
                            uploaded_file.type,
                            reporting_period,
                            notes if notes else None
                        )
                    )

                    if saved:
                        st.success(f"✅ Document uploaded successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Error uploading file. Please try again.")
                    
                except Exception as e:
                    st.error(f"❌ Error uploading file: {str(e)}")
        
        st.divider()
    
    # ============================================================================
    # VIEW DOCUMENTS SECTION
    # ============================================================================
    st.subheader("📋 Your Documents")
    
    # Fetch documents for the company
    documents_query = """
        SELECT 
            cd.id, cd.company_id, cd.uploaded_by, cd.document_type,
            cd.file_name, cd.file_path, cd.file_size, cd.mime_type,
            cd.reporting_period, cd.notes, cd.is_active, cd.created_at, cd.updated_at,
            cd.file_content,
            u.username as uploaded_by_name
        FROM cosiri_documents cd
        LEFT JOIN users u ON cd.uploaded_by = u.id
        WHERE cd.company_id = %s AND cd.is_active = 1
        ORDER BY cd.created_at DESC
    """
    
    rows = db.fetch_query(documents_query, (st.session_state.company_id,))
    
    # Convert tuples to dictionaries
    documents = [{
        'id': r[0],
        'company_id': r[1],
        'uploaded_by': r[2],
        'document_type': r[3],
        'file_name': r[4],
        'file_path': r[5],
        'file_size': r[6],
        'mime_type': r[7],
        'reporting_period': r[8],
        'notes': r[9],
        'is_active': r[10],
        'created_at': r[11],
        'updated_at': r[12],
        'file_content': r[13],
        'uploaded_by_name': r[14]
    } for r in rows]
    
    if not documents:
        st.info("📭 No documents uploaded yet")
    else:
        # Filter options
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            filter_type = st.selectbox(
                "Filter by Type",
                options=['all', 'certificate', 'report'],
                format_func=lambda x: 'All Documents' if x == 'all' else ('📜 Certificates' if x == 'certificate' else '📊 Reports')
            )
        
        with col_filter2:
            available_periods = sorted(set([doc['reporting_period'] for doc in documents if doc['reporting_period']]), reverse=True)
            filter_period = st.selectbox(
                "Filter by Period",
                options=['all'] + available_periods,
                format_func=lambda x: 'All Periods' if x == 'all' else x
            )
        
        # Apply filters
        filtered_docs = documents
        if filter_type != 'all':
            filtered_docs = [doc for doc in filtered_docs if doc['document_type'] == filter_type]
        if filter_period != 'all':
            filtered_docs = [doc for doc in filtered_docs if doc['reporting_period'] == filter_period]
        
        st.markdown(f"**Showing {len(filtered_docs)} document(s)**")
        
        # Display documents
        for doc in filtered_docs:
            with st.expander(
                f"{'📜' if doc['document_type'] == 'certificate' else '📊'} {doc['file_name']} "
                f"({doc['reporting_period'] if doc['reporting_period'] else 'N/A'})",
                expanded=False
            ):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"**Document Type:** {doc['document_type'].title()}")
                    st.markdown(f"**Reporting Period:** {doc['reporting_period'] if doc['reporting_period'] else 'N/A'}")
                    st.markdown(f"**File Size:** {doc['file_size'] / 1024:.2f} KB")
                    st.markdown(f"**Uploaded By:** {doc['uploaded_by_name']}")
                    st.markdown(f"**Upload Date:** {doc['created_at']}")
                    
                    if doc['notes']:
                        st.markdown(f"**Notes:** {doc['notes']}")
                
                with col_actions:
                    # Download button
                    if doc['file_content']:
                        st.download_button(
                            label="⬇️ Download",
                            data=doc['file_content'],
                            file_name=doc['file_name'],
                            mime=doc['mime_type'],
                            width="stretch",
                            key=f"download_{doc['id']}"
                        )
                    else:
                        st.warning("⚠️ File content not found")
                    
                    # Delete button (Admin & Manager only)
                    if can_delete:
                        if st.button(
                            "🗑️ Delete",
                            type="secondary",
                            width="stretch",
                            key=f"delete_{doc['id']}"
                        ):
                            # Soft delete (set is_active = 0)
                            delete_query = "UPDATE cosiri_documents SET is_active = 0 WHERE id = %s"
                            db.execute_query(delete_query, (doc['id'],))
                            
                            st.success("✅ Document deleted successfully!")
                            st.rerun()
        
        # Summary statistics
        st.divider()
        st.subheader("📊 Document Summary")
        
        col_cert, col_report, col_total = st.columns(3)
        
        with col_cert:
            cert_count = len([d for d in documents if d['document_type'] == 'certificate'])
            st.metric("📜 Certificates", cert_count)
        
        with col_report:
            report_count = len([d for d in documents if d['document_type'] == 'report'])
            st.metric("📊 Reports", report_count)
        
        with col_total:
            total_size = sum([d['file_size'] for d in documents]) / (1024 * 1024)  # Convert to MB
            st.metric("💾 Total Size", f"{total_size:.2f} MB")

finally:
    db.disconnect()