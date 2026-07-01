"""
Sensitive Data Detection & Compliance Assistant
================================================
Main Streamlit application entry point.

Integrates all modules:
- Document extraction (PDF/TXT/CSV)
- Unified sensitive data detection (Regex + NLP)
- Risk classification
- AI-generated compliance summary
- RAG-powered Q&A
"""

import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from extractors.pdf_extractor import extract_text_from_pdf
from extractors.txt_extractor import extract_text_from_txt
from extractors.csv_extractor import extract_text_from_csv
from detectors.unified_detector import mask_detected_values, run_unified_detection
from classifiers.risk_classifier import classify_risk
from summarizers.llm_client import LLMClient
from summarizers.compliance_summary import generate_compliance_summary
from rag.qa_engine import QAEngine
from utils.audit_logger import log_document_processing

# Load environment variables
load_dotenv()

# Supported file types and their MIME types
SUPPORTED_TYPES = ["pdf", "txt", "csv"]

# Page configuration
st.set_page_config(
    page_title="Data Compliance Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize Streamlit session state variables."""
    defaults = {
        "extraction_result": None,
        "uploaded_filenames": [],
        "detection_result": None,
        "risk_classification": None,
        "compliance_summary": None,
        "qa_engine": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_analysis_state():
    """Reset all analysis state when a new file is uploaded."""
    st.session_state["extraction_result"] = None
    st.session_state["detection_result"] = None
    st.session_state["risk_classification"] = None
    st.session_state["compliance_summary"] = None
    st.session_state["qa_engine"] = None
    st.session_state["chat_history"] = []


def get_file_extension(filename: str) -> str:
    """Extract and validate file extension."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def extract_document(file_bytes: bytes, filename: str, file_type: str):
    """Route document to the appropriate extractor."""
    extractors = {
        "pdf": extract_text_from_pdf,
        "txt": extract_text_from_txt,
        "csv": extract_text_from_csv,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        from extractors.pdf_extractor import ExtractionResult
        return ExtractionResult(success=False, error=f"Unsupported file type: {file_type}")
    return extractor(file_bytes, filename)


def render_sidebar():
    """Render the sidebar with upload controls and settings."""
    with st.sidebar:
        st.header("📁 Document Upload")
        uploaded_files = st.file_uploader(
            "Upload documents",
            accept_multiple_files=True,
            help="Supported formats: PDF, TXT, CSV",
        )
        
        st.divider()
        st.header("⚙️ Settings")
        
        # LLM Settings
        enable_nlp = st.toggle("Enable NLP Detection", value=True, 
                              help="Use spaCy for contextual entities (slower but more comprehensive)")
        
        use_llm = st.toggle("Enable AI Generation", value=True,
                           help="Use LLM for summaries and Q&A. Requires API key.")
                           
        providers = ["gemini", "openai", "groq"]
        default_provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
        default_index = providers.index(default_provider) if default_provider in providers else 0
        llm_provider = st.selectbox("LLM Provider", providers, index=default_index)
        
        api_key = ""
        if use_llm:
            api_key = st.text_input(
                f"{llm_provider.capitalize()} API Key", 
                type="password",
                help=f"Leave empty to use {llm_provider.upper()}_API_KEY from .env"
            )
            
            if api_key:
                os.environ[f"{llm_provider.upper()}_API_KEY"] = api_key
            os.environ["LLM_PROVIDER"] = llm_provider
        
        st.divider()
        st.caption("Built with Streamlit • Python • spaCy • Gemini AI")
        
        return uploaded_files, enable_nlp, use_llm


def run_analysis_pipeline(uploaded_files, enable_nlp, use_llm):
    """Run the complete extraction and analysis pipeline."""
    if not uploaded_files:
        return False
        
    filenames = [f.name for f in uploaded_files]
    
    # Check if this is a new set of files
    if filenames != st.session_state["uploaded_filenames"]:
        reset_analysis_state()
        st.session_state["uploaded_filenames"] = filenames
    
    # 1. Extraction
    if not st.session_state["extraction_result"]:
        with st.spinner("Extracting text from documents..."):
            from extractors.pdf_extractor import ExtractionResult
            combined_result = ExtractionResult(success=True, text="", total_lines=0)
            
            for uploaded_file in uploaded_files:
                file_type = get_file_extension(uploaded_file.name)
                file_bytes = uploaded_file.read()
                
                result = extract_document(file_bytes, uploaded_file.name, file_type)
                if not result.success:
                    st.error(f"❌ **Extraction failed for {uploaded_file.name}:** {result.error}")
                    continue
                
                combined_result.text += f"\n\n--- Document: {uploaded_file.name} ---\n\n" + result.text
                combined_result.total_lines += result.total_lines
                
            st.session_state["extraction_result"] = combined_result
    
    result = st.session_state["extraction_result"]
    text = result.text
    
    # 2. Detection
    if not st.session_state["detection_result"]:
        with st.spinner("Detecting sensitive data (Regex + NLP)..."):
            detection = run_unified_detection(text, enable_nlp=enable_nlp)
            st.session_state["detection_result"] = detection
    
    detection = st.session_state["detection_result"]
    
    # 3. Risk Classification
    if not st.session_state["risk_classification"]:
        with st.spinner("Classifying risk..."):
            classification = classify_risk(detection)
            st.session_state["risk_classification"] = classification
    
    classification = st.session_state["risk_classification"]
    
    # 4. Compliance Summary
    if not st.session_state["compliance_summary"]:
        with st.spinner("Generating compliance summary..."):
            llm_client = None
            if use_llm:
                try:
                    llm_client = LLMClient()
                    if not llm_client.is_available():
                        st.warning("LLM API key missing or invalid. Falling back to template summary.")
                        llm_client = None
                except Exception as e:
                    st.warning(f"LLM init failed: {e}. Falling back to template.")
                    llm_client = None
            
            summary = generate_compliance_summary(detection, classification, llm_client)
            st.session_state["compliance_summary"] = summary
    
    summary = st.session_state["compliance_summary"]
    
    # 5. QA Engine Init
    if not st.session_state["qa_engine"]:
        with st.spinner("Initializing Q&A engine..."):
            llm_client = None
            if use_llm:
                try:
                    llm_client = LLMClient()
                    if not llm_client.is_available():
                        llm_client = None
                except:
                    llm_client = None
            
            qa_engine = QAEngine(
                document_text=mask_detected_values(text, detection.entities),
                detection_result=detection,
                risk_classification=classification,
                compliance_summary=summary,
                llm_client=llm_client,
            )
            st.session_state["qa_engine"] = qa_engine
            
            # Audit logging
            log_document_processing(
                filename=", ".join(st.session_state["uploaded_filenames"]),
                file_type="multiple",
                total_entities=detection.total_entities,
                risk_level=classification.risk_level,
                risk_score=classification.risk_score
            )
            
    return True


def render_dashboard():
    """Render the main dashboard with results."""
    detection = st.session_state["detection_result"]
    classification = st.session_state["risk_classification"]
    summary = st.session_state["compliance_summary"]
    
    # --- Top Metrics Row ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Entities", detection.total_entities)
    
    with col2:
        risk_color = {
            "LOW": "normal",
            "MEDIUM": "off",
            "HIGH": "inverse"
        }.get(classification.risk_level, "normal")
        st.metric("Risk Level", classification.risk_level, delta_color=risk_color)
    
    with col3:
        st.metric("Risk Score", f"{classification.risk_score:.0f}")
        
    with col4:
        st.metric("Detection Methods", ", ".join(detection.detection_methods).upper())
        
    st.divider()
    
    # Export functionality (Bonus Feature)
    with st.sidebar:
        st.divider()
        st.header("📥 Export Report")
        
        if detection.total_entities > 0:
            # Create a simplified CSV for export
            export_data = []
            for e in detection.entities:
                export_data.append({
                    "Entity Type": e.entity_type,
                    "Masked Value": e.masked_value,
                    "Confidence": round(e.confidence, 2),
                    "Method": e.method,
                    "Line Number": e.location.get("line", "")
                })
            export_df = pd.DataFrame(export_data)
            csv = export_df.to_csv(index=False)
            
            st.download_button(
                label="Download Entities (CSV)",
                data=csv,
                file_name="sensitive_entities.csv",
                mime="text/csv",
                help="Download a list of detected sensitive entities (masked for safety)."
            )
            
            # Export redacted document text
            ext_result = st.session_state["extraction_result"]
            masked_text = mask_detected_values(ext_result.text, detection.entities)
            st.download_button(
                label="Download Redacted Text (.txt)",
                data=masked_text,
                file_name="redacted_document.txt",
                mime="text/plain",
                help="Download the full document text with sensitive values masked."
            )
        else:
            st.info("No entities to export.")
    
    # --- Main Content Tabs ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Detected Entities", 
        "📋 Compliance Summary", 
        "💬 Document Q&A",
        "📄 Raw Text Preview"
    ])
    
    # Tab 1: Detected Entities
    with tab1:
        st.subheader("Sensitive Data Entities")
        
        if detection.total_entities == 0:
            st.success("No sensitive data entities detected in this document.")
        else:
            # Create a dataframe for display
            entities_data = []
            for e in detection.entities:
                entities_data.append({
                    "Type": e.entity_type.replace('_', ' ').title(),
                    "Masked Value": e.masked_value,
                    "Line": e.location.get("line", "N/A"),
                    "Method": e.method.upper(),
                    "Confidence": f"{e.confidence:.0%}",
                })
            
            df = pd.DataFrame(entities_data)
            st.dataframe(df, width='stretch', hide_index=True)
            
            # Risk Breakdown
            st.subheader("Top Risk Factors")
            for factor in classification.top_risk_factors:
                etype = factor['entity_type'].replace('_', ' ').title()
                st.markdown(f"- **{etype}** (Found: {factor['count']} | Contribution: {factor['contribution']})")
    
    # Tab 2: Compliance Summary
    with tab2:
        # Use appropriate alert color based on risk
        if classification.risk_level == "HIGH":
            st.error("⚠️ **HIGH RISK DOCUMENT**")
        elif classification.risk_level == "MEDIUM":
            st.warning("⚡ **MEDIUM RISK DOCUMENT**")
        else:
            st.success("✅ **LOW RISK DOCUMENT**")
            
        st.markdown(summary)
    
    # Tab 3: Q&A Chat
    with tab3:
        st.subheader("Ask questions about the document")
        st.caption("Ask 'how many emails are there?', 'what is the risk level?', or ask about the document content.")
        
        # Display chat history
        for message in st.session_state["chat_history"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask a question..."):
            # Add user message
            st.session_state["chat_history"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Generate and add assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    engine = st.session_state["qa_engine"]
                    response = engine.answer(prompt)
                    st.markdown(response)
                    
            st.session_state["chat_history"].append({"role": "assistant", "content": response})

    # Tab 4: Raw Text Preview
    with tab4:
        ext_result = st.session_state["extraction_result"]
        masked_preview = mask_detected_values(ext_result.text, detection.entities)
        st.caption(f"Showing first 5000 characters of masked extracted text ({ext_result.total_lines} lines total).")
        st.text(masked_preview[:5000])


def main():
    """Main application loop."""
    init_session_state()
    
    st.title("🛡️ Sensitive Data Detection & Compliance Assistant")
    
    # Render Sidebar
    uploaded_files, enable_nlp, use_llm = render_sidebar()
    
    # Main Content Area
    if not uploaded_files:
        st.markdown("""
        ### Welcome to the Compliance Assistant
        
        Upload a document (PDF, TXT, or CSV) to automatically:
        1. **Detect** sensitive information (PII, Financial, Secrets, Confidential IP)
        2. **Classify** the overall risk level of the document
        3. **Summarize** compliance obligations and remediation steps
        4. **Chat** securely with the document contents
        
        👈 Get started by uploading a file in the sidebar.
        """)
        return
        
    # Process document
    success = run_analysis_pipeline(uploaded_files, enable_nlp, use_llm)
    
    if success:
        render_dashboard()


if __name__ == "__main__":
    main()
