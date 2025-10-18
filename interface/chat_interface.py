import gradio as gr
import sqlite3
import pandas as pd
import sys, os
from pathlib import Path
from datetime import datetime
import tempfile

# Ensure we can import core.crew_executor
CURR_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURR_DIR.parent
sys.path.append(str(ROOT_DIR))

# --- ensure ffmpeg is on PATH before whisper is imported ---
import os.path, shutil, imageio_ffmpeg

ffmpeg_src = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_src)
ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")

if not os.path.exists(ffmpeg_exe):
    try:
        shutil.copyfile(ffmpeg_src, ffmpeg_exe)
    except Exception:
        with open(os.path.join(ffmpeg_dir, "ffmpeg.cmd"), "w", encoding="utf-8") as f:
            f.write(f'"{ffmpeg_src}" %*')

os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
print("Using ffmpeg:", shutil.which("ffmpeg"))

import whisper
from core.crew_executor import process_user_question

model = whisper.load_model("base")

def transcribe_audio(audio_input):
    audio_path = audio_input if isinstance(audio_input, str) else (
        audio_input.get("name") if isinstance(audio_input, dict) else None
    )
    if not audio_path or not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path!r}")
    result = model.transcribe(audio_path)
    return result["text"]

def get_table_names(db_file_path: str):
    try:
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Table fetch error: {e}")
        return []

# Add missing helper functions
def export_to_csv(df, question):
    """Export DataFrame to CSV"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"query_results_{timestamp}.csv"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        df.to_csv(filepath, index=False)
        return filepath
    except Exception as e:
        print(f"CSV export error: {e}")
        return None

def export_to_excel(df, question, sql):
    """Export DataFrame to Excel with query info"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"query_results_{timestamp}.xlsx"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Results', index=False)
            
            # Add query info sheet
            query_info = pd.DataFrame({
                'Question': [question],
                'SQL Query': [sql],
                'Timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                'Rows Returned': [len(df)]
            })
            query_info.to_excel(writer, sheet_name='Query Info', index=False)
        
        return filepath
    except Exception as e:
        print(f"Excel export error: {e}")
        return None


def pipeline(audio, text_input, db_file, table_name, db_engine):
    if db_file is None:
        return "No database connected", "", pd.DataFrame()

    if db_engine == "sqlite" and not table_name:
        return "No table selected", "", pd.DataFrame()

    question = text_input
    if not question and audio:
        try:
            question = transcribe_audio(audio)
        except Exception as e:
            return f"Voice error: {e}", "", pd.DataFrame()

    if not question:
        return "Please ask a question", "", pd.DataFrame()

    db_path = db_file.name if hasattr(db_file, "name") else db_file
    sql, result = process_user_question(db_path, table_name, question, db_engine)

    # Debug: Print the result structure to understand the format
    print(f"Result type: {type(result)}")
    print(f"Result content: {result}")

    if isinstance(result, dict) and 'error' in result:
        return question, sql, pd.DataFrame([{"Error": result['error']}])
    elif not result:
        return question, sql, pd.DataFrame([{"Message": "No results found."}])
    else:
        # Handle different result formats
        if isinstance(result, dict):
            # Single dictionary result with 'data' key containing the actual results
            if 'data' in result and isinstance(result['data'], list):
                # This is the main fix: use result['data'] directly, don't wrap it in another list
                if result['data']:
                    return question, sql, pd.DataFrame(result['data'])
                else:
                    return question, sql, pd.DataFrame([{"Message": "No data found."}])
            else:
                # If no 'data' key, use the entire dict
                return question, sql, pd.DataFrame([result])
        elif isinstance(result, list):
            # If result is a list of dictionaries with metadata
            if result and isinstance(result[0], dict) and 'data' in result[0]:
                # Extract just the data from each row
                data_rows = []
                for row in result:
                    if 'data' in row and isinstance(row['data'], dict):
                        data_rows.append(row['data'])
                
                if data_rows:
                    return question, sql, pd.DataFrame(data_rows)
                else:
                    return question, sql, pd.DataFrame([{"Message": "No data found in results."}])
            else:
                # Regular list of dictionaries
                return question, sql, pd.DataFrame(result)
        else:
            # Fallback for other types
            return question, sql, pd.DataFrame([{"Result": str(result)}])


# Enhanced CSS with better visibility
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Base theme fixes for dark mode */
.gradio-container {
    font-family: 'Inter', sans-serif !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
    background: #0f172a !important;
}

/* Header Section - Enhanced gradient */
.voice-sql-header {
    background: linear-gradient(135deg, #3b82f6 0%, #10b981 100%);
    padding: 3rem 2rem;
    border-radius: 16px;
    margin: 2rem 0;
    color: white;
    text-align: center;
    box-shadow: 0 20px 25px -5px rgba(59, 130, 246, 0.3);
}

.voice-sql-title {
    font-weight: 700 !important;
    font-size: 2.75rem !important;
    margin: 0 0 1rem 0 !important;
    color: white !important;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.voice-sql-subtitle {
    font-weight: 400 !important;
    font-size: 1.25rem !important;
    margin: 0 !important;
    color: rgba(255, 255, 255, 0.95) !important;
}

/* Feature Grid - Better contrast */
.feature-grid-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0 3rem 0;
}

.feature-card {
    text-align: center;
    padding: 2rem 1.5rem;
    background: linear-gradient(145deg, #1e293b 0%, #334155 100%);
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.2);
    transition: all 0.3s ease;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}

.feature-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 20px 25px -5px rgba(59, 130, 246, 0.4);
    border-color: rgba(59, 130, 246, 0.5);
}

.feature-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    display: block;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}

.feature-card h3 {
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 0.5rem;
    font-size: 1.2rem;
}

.feature-card p {
    color: #cbd5e1;
    margin: 0;
    line-height: 1.6;
    font-size: 0.95rem;
}

/* Section cards with better visibility */
.section-card {
    background: linear-gradient(145deg, #1e293b 0%, #334155 100%) !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    border-radius: 16px !important;
    padding: 2rem !important;
    margin: 1.5rem 0 !important;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4) !important;
}

.section-title {
    font-weight: 600 !important;
    font-size: 1.35rem !important;
    color: #f1f5f9 !important;
    margin-bottom: 1.5rem !important;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    border-bottom: 2px solid rgba(59, 130, 246, 0.4) !important;
    padding-bottom: 0.75rem !important;
}

/* Status indicator - Much more visible */
.status-indicator {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    background: rgba(239, 68, 68, 0.15);
    border-radius: 12px;
    border: 2px solid rgba(239, 68, 68, 0.4);
    margin-top: 1rem;
    color: #fca5a5;
    font-weight: 600;
    font-size: 0.95rem;
}

.status-indicator.connected {
    border-color: rgba(16, 185, 129, 0.5);
    background: rgba(16, 185, 129, 0.15);
    color: #6ee7b7;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #ef4444;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
    animation: pulse 2s infinite;
}

.status-indicator.connected .status-dot {
    background: #10b981;
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Button styling - More prominent */
.primary-action-button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    color: white !important;
    padding: 1.25rem 2.5rem !important;
    font-size: 1.15rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4) !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
}

.primary-action-button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 20px 25px -5px rgba(59, 130, 246, 0.5) !important;
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
}

/* Input fields - Better contrast */
label {
    color: #e2e8f0 !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    margin-bottom: 0.5rem !important;
}

input, textarea, select {
    background: rgba(30, 41, 59, 0.8) !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    color: #f1f5f9 !important;
    border-radius: 8px !important;
}

input:focus, textarea:focus, select:focus {
    border-color: rgba(59, 130, 246, 0.6) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
}

/* SQL output - Enhanced readability */
.sql-output-box {
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace !important;
    background: #0f172a !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    border-radius: 8px !important;
    padding: 1rem !important;
    border-left: 4px solid #3b82f6 !important;
    color: #e2e8f0 !important;
}

/* Accordion styling */
.accordion {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: 8px !important;
    margin: 0.5rem 0 !important;
}

/* Dataframe table */
.dataframe {
    background: #1e293b !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    border-radius: 8px !important;
}

.dataframe th {
    background: #334155 !important;
    color: #f1f5f9 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid rgba(59, 130, 246, 0.4) !important;
}

.dataframe td {
    color: #e2e8f0 !important;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2) !important;
}

/* File upload area */
.file-upload-area {
    border: 2px dashed rgba(148, 163, 184, 0.4) !important;
    border-radius: 12px !important;
    background: rgba(30, 41, 59, 0.6) !important;
    padding: 1.5rem !important;
    transition: all 0.3s ease !important;
}

.file-upload-area:hover {
    border-color: rgba(59, 130, 246, 0.6) !important;
    background: rgba(30, 41, 59, 0.8) !important;
}

/* Audio recorder */
.audio-recorder {
    background: rgba(30, 41, 59, 0.8) !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}

/* Helper text */
.helper-text {
    text-align: center;
    color: #94a3b8 !important;
    margin-top: 0.75rem;
    font-size: 0.9rem;
    font-style: italic;
}

/* Footer */
.voice-sql-footer {
    text-align: center;
    margin-top: 4rem;
    padding: 2.5rem;
    color: #94a3b8;
    border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.voice-sql-footer p {
    color: #cbd5e1 !important;
}

/* Performance display */
.performance-badge {
    display: inline-block;
    padding: 0.5rem 1rem;
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 8px;
    color: #6ee7b7;
    font-weight: 600;
    margin: 0.5rem 0;
}

/* Export buttons */
button[data-testid*="export"] {
    background: rgba(59, 130, 246, 0.15) !important;
    border: 1px solid rgba(59, 130, 246, 0.3) !important;
    color: #60a5fa !important;
}

button[data-testid*="export"]:hover {
    background: rgba(59, 130, 246, 0.25) !important;
    border-color: rgba(59, 130, 246, 0.5) !important;
}

/* Dropdown menu items */
.dropdown-menu {
    background: #1e293b !important;
    border: 1px solid rgba(148, 163, 184, 0.3) !important;
}

.dropdown-item {
    color: #e2e8f0 !important;
}

.dropdown-item:hover {
    background: rgba(59, 130, 246, 0.2) !important;
}
"""

def launch():
    with gr.Blocks(
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="green",
            neutral_hue="slate"
        ),
        css=custom_css,
        title="QueryMate - Your Intelligent Database Companion"
    ) as demo:
        
        # Header Section
        gr.HTML("""
        <div class="voice-sql-header">
            <h1 class="voice-sql-title">QueryMate</h1>
            <p class="voice-sql-subtitle">Transform Natural Language Questions into SQL Queries Instantly</p>
        </div>
        """)
        
        # Feature Highlights
        gr.HTML("""
        <div class="feature-grid-container">
            <div class="feature-card">
                <span class="feature-icon">🎤</span>
                <h3>Voice Input</h3>
                <p>Ask questions naturally using voice commands</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">⚡</span>
                <h3>Instant SQL</h3>
                <p>AI-powered SQL query generation in seconds</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🔍</span>
                <h3>Live Results</h3>
                <p>See query results immediately in real-time</p>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🛠️</span>
                <h3>Multi-Engine</h3>
                <p>Supports SQLite, PostgreSQL, and MySQL</p>
            </div>
        </div>
        """)

        # Database Configuration Section
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('<div class="section-card">')
                gr.HTML('<div class="section-title">🗃️ Database Configuration</div>')
                
                db_file = gr.File(
                    label="📂 Upload Database File",
                    file_types=[".sqlite3", ".db", ".sqlite"],
                    type="filepath",
                    elem_classes=["file-upload-area"]
                )
                
                with gr.Row():
                    db_engine_dropdown = gr.Dropdown(
                        choices=["sqlite", "postgresql", "mysql"],
                        label="🔧 Database Engine",
                        value="sqlite"
                    )
                
                table_dropdown = gr.Dropdown(
                    label="📊 Select Table (SQLite only)",
                    choices=[],
                    interactive=True
                )
                
                # Database Status
                db_status = gr.HTML("""
                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span>No database connected</span>
                </div>
                """)
                
                # Schema Preview Section
                with gr.Accordion("🔍 Database Schema Preview", open=False):
                    schema_display = gr.Markdown(
                        value="Select a table to see the database schema and relationships...",
                        label="Schema Information"
                    )
                
                gr.HTML('</div>')

        # Question Input Section
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('<div class="section-card">')
                gr.HTML('<div class="section-title">💬 Ask Your Question</div>')
                
                with gr.Row():
                    with gr.Column(scale=1):
                        audio_input = gr.Audio(
                            sources=["microphone"], 
                            type="filepath", 
                            label="🎤 Record Question",
                            elem_classes=["audio-recorder"]
                        )
                        gr.HTML("""
                        <div class="helper-text">
                            Click the microphone to record your question
                        </div>
                        """)
                    
                    with gr.Column(scale=1):
                        text_input = gr.Textbox(
                            placeholder=" Type your question here...\nExample: 'Show me all customers from New York'",
                            label="📝 Type Question",
                            lines=4
                        )
                gr.HTML('</div>')

        # Submit Button
        with gr.Row():
            with gr.Column():
                submit_btn = gr.Button(
                    "🚀 Generate SQL & Execute", 
                    size="lg",
                    elem_classes=["primary-action-button"]
                )

        # Results Section
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML('<div class="section-card">')
                gr.HTML('<div class="section-title">📊 Query Results</div>')
                
                with gr.Accordion("📝 Recognized Question", open=True):
                    out_question = gr.Textbox(
                        label="Question",
                        interactive=False
                    )
                
                with gr.Accordion("📄 Generated SQL Query", open=True):
                    out_sql = gr.Textbox(
                        label="SQL Query",
                        lines=4,
                        elem_classes=["sql-output-box"]
                    )
                
                with gr.Accordion("📈 Query Result", open=True):
                    out_result = gr.Dataframe(
                        label="Results",
                        wrap=True
                    )
                
                # Export buttons
                with gr.Row():
                    export_csv_btn = gr.Button(
                        "📥 Export to CSV",
                        size="sm"
                    )
                    export_excel_btn = gr.Button(
                        "📊 Export to Excel",
                        size="sm"
                    )
                
                # Download component
                download_file = gr.File(
                    label="Download Export",
                    visible=False
                )
                
                gr.HTML('</div>')

       
        # Update functions
        def update_table_dropdown(db, engine):
            if db and engine == "sqlite":
                table_choices = get_table_names(db.name)
                status_html = f"""
                <div class="status-indicator connected">
                    <div class="status-dot"></div>
                    <span>✓ Connected: {len(table_choices)} tables found</span>
                </div>
                """
                return (
                    gr.update(choices=table_choices, visible=True, value=None),
                    status_html,
                    gr.update(visible=True)
                )
            status_html = """
            <div class="status-indicator">
                <div class="status-dot"></div>
                <span>⚠ No database connected</span>
            </div>
            """
            return (
                gr.update(choices=[], visible=False, value=None),
                status_html,
                gr.update(visible=False)
            )
        
        def show_schema_preview(db, table, engine):
            """Show comprehensive schema when table is selected."""
            if not db or not table or engine != "sqlite":
                return "Select a table to see relationships..."
            
            try:
                # Try to import the schema function, fallback to basic info if not available
                try:
                    from core.crew_executor import get_comprehensive_schema
                    schema_text = get_comprehensive_schema(db.name, table, engine)
                    
                    # Format for display
                    formatted = schema_text.replace("===", "###")
                    formatted = formatted.replace("---", "**")
                    formatted = formatted.replace("•", "  •")
                    
                    return f"""
{formatted}

---

### 💡 What This Means

The AI can see **all these tables and relationships**!


**You only select one table as the starting point, but the AI sees everything!**
"""
                except ImportError:
                    # Fallback to basic schema info
                    return f"""
### Basic Schema Information for Table: **{table}**

**Note:** Comprehensive schema analysis requires the `get_comprehensive_schema` function.

You can still ask questions about:
- Data in the **{table}** table
- Simple aggregations and filters
- Basic data exploration

**Example questions:**
- "Show all records from {table}"
- "Count the number of rows in {table}"
- "What are the unique values in {table}?"
"""
            except Exception as e:
                return f"Error loading schema: {str(e)}"

        # Event handlers
        db_file.change(
            fn=update_table_dropdown,
            inputs=[db_file, db_engine_dropdown],
            outputs=[table_dropdown, db_status, schema_display]
        )
        
        db_engine_dropdown.change(
            fn=update_table_dropdown,
            inputs=[db_file, db_engine_dropdown],
            outputs=[table_dropdown, db_status, schema_display]
        )
        
        # Show schema when table is selected
        table_dropdown.change(
            fn=show_schema_preview,
            inputs=[db_file, table_dropdown, db_engine_dropdown],
            outputs=[schema_display]
        )
        
        submit_btn.click(
            fn=pipeline,
            inputs=[audio_input, text_input, db_file, table_dropdown, db_engine_dropdown],
            outputs=[out_question, out_sql, out_result]
        )
        
        # Export handlers
        def handle_csv_export(df, question):
            if df.empty or 'Error' in df.columns or 'Message' in df.columns:
                return gr.update(visible=False)
            filepath = export_to_csv(df, question)
            return gr.update(value=filepath, visible=True) if filepath else gr.update(visible=False)
        
        def handle_excel_export(df, question, sql):
            if df.empty or 'Error' in df.columns or 'Message' in df.columns:
                return gr.update(visible=False)
            filepath = export_to_excel(df, question, sql)
            return gr.update(value=filepath, visible=True) if filepath else gr.update(visible=False)
        
        export_csv_btn.click(
            fn=handle_csv_export,
            inputs=[out_result, out_question],
            outputs=[download_file]
        )
        
        export_excel_btn.click(
            fn=handle_excel_export,
            inputs=[out_result, out_question, out_sql],
            outputs=[download_file]
        )
        
       

        # Footer
        gr.HTML("""
        <div class="voice-sql-footer">
            <p style="margin: 0; font-size: 1rem; font-weight: 600;">🚀 Powered by AI |  QueryMate - Your Intelligent Database Companion</p>
            <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">Type or Speak your questions, get instant SQL results</p>
        </div>
        """)

    demo.launch(
        share=False,
        inbrowser=True
    )

if __name__ == "__main__":
    launch()