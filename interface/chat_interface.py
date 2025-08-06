'''import gradio as gr
import whisper
import sqlite3
from core.crew_executor import process_user_question

model = whisper.load_model("base")

def transcribe_audio(audio_path):
    result = model.transcribe(audio_path)
    return result['text']

def get_table_names(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except:
        return []

def pipeline(audio, text_input, db_file, table_name, db_engine):
    if db_file is None:
        return "No database connected", "", ""

    if not table_name:
        return "No table selected", "", ""

    question = text_input or (transcribe_audio(audio) if audio else "")
    if not question:
        return "Please ask a question", "", ""

    sql, result = process_user_question(db_file.name, table_name, question, db_engine)
    if isinstance(result, dict) and 'error' in result:
        return question, sql, f"❌ Error: {result['error']}"
    elif not result:
        return question, sql, "No results found."
    else:
        return question, sql, "\n".join(str(r) for r in result)

def launch():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🎙️🧠 SQL Query Generator (Voice + DB Upload)")
        gr.Markdown("Upload a database, select a table & engine, then ask questions by voice or text.")

        with gr.Row():
            db_file = gr.File(label="📂 Upload DB File", file_types=[".sqlite3", ".db"])
            db_engine_dropdown = gr.Dropdown(
                choices=["sqlite", "postgresql", "mysql"],
                label="🧩 Select Database Engine",
                value="sqlite"
            )

        table_dropdown = gr.Dropdown(label="📊 Select Table", choices=[], interactive=True)

        def update_table_dropdown(db):
            if db:
                table_choices = get_table_names(db.name)
                return gr.update(choices=table_choices, value=None)
            return gr.update(choices=[], value=None)

        db_file.change(fn=update_table_dropdown, inputs=[db_file], outputs=[table_dropdown])

        with gr.Row():
            audio_input = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Record Question")
            text_input = gr.Textbox(placeholder="Or type your question here", label="📝 Type Question")

        submit_btn = gr.Button("🔍 Generate SQL")

        out_question = gr.Textbox(label="📥 Recognized Question")
        out_sql = gr.Textbox(label="📄 Generated SQL Query")
        out_result = gr.Textbox(label="📊 Query Result", lines=10)

        submit_btn.click(
            fn=pipeline,
            inputs=[audio_input, text_input, db_file, table_dropdown, db_engine_dropdown],
            outputs=[out_question, out_sql, out_result]
        )

    demo.launch()

if __name__ == "__main__":
    launch()
'''

import gradio as gr
import whisper
import sqlite3
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.crew_executor import process_user_question

model = whisper.load_model("base")

# Transcribe audio using Whisper
def transcribe_audio(audio_path):
    result = model.transcribe(audio_path)
    return result['text']

# Fetch tables (SQLite only for now)
def get_table_names(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Table fetch error: {e}")
        return []

# Main processing pipeline
def pipeline(audio, text_input, db_file, table_name, db_engine):
    if db_file is None:
        return "No database connected", "", pd.DataFrame()

    if not table_name and db_engine == "sqlite":
        return "No table selected", "", pd.DataFrame()

    question = text_input or (transcribe_audio(audio) if audio else "")
    if not question:
        return "Please ask a question", "", pd.DataFrame()

    sql, result = process_user_question(db_file.name, table_name, question, db_engine)

    if isinstance(result, dict) and 'error' in result:
        return question, sql, pd.DataFrame([{"Error": result['error']}])
    elif not result:
        return question, sql, pd.DataFrame([{"Message": "No results found."}])
    else:
        return question, sql, pd.DataFrame(result)

# Launch Gradio UI
def launch():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("## 🎙️🧠 Voice + SQL Query Generator")
        gr.Markdown("Upload your DB file, choose engine + table (for SQLite), and ask questions via voice or text.")

        with gr.Row():
            db_file = gr.File(label="📂 Upload DB File", file_types=[".sqlite3", ".db"])
            db_engine_dropdown = gr.Dropdown(
                choices=["sqlite", "postgresql", "mysql"],
                label="🧩 Select Database Engine",
                value="sqlite"
            )

        table_dropdown = gr.Dropdown(label="📊 Select Table (SQLite only)", choices=[], interactive=True)

        def update_table_dropdown(db, engine):
            if db and engine == "sqlite":
                table_choices = get_table_names(db.name)
                return gr.update(choices=table_choices, visible=True, value=None)
            return gr.update(choices=[], visible=False, value=None)

        db_file.change(fn=update_table_dropdown, inputs=[db_file, db_engine_dropdown], outputs=[table_dropdown])
        db_engine_dropdown.change(fn=update_table_dropdown, inputs=[db_file, db_engine_dropdown], outputs=[table_dropdown])

        with gr.Row():
            audio_input = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Record Question")
            text_input = gr.Textbox(placeholder="Or type your question here", label="📝 Type Question")

        submit_btn = gr.Button("🔍 Generate SQL")

        out_question = gr.Textbox(label="📥 Recognized Question")
        out_sql = gr.Textbox(label="📄 Generated SQL Query")
        out_result = gr.Dataframe(label="📊 Query Result")

        submit_btn.click(
            fn=pipeline,
            inputs=[audio_input, text_input, db_file, table_dropdown, db_engine_dropdown],
            outputs=[out_question, out_sql, out_result]
        )

    demo.launch()

if __name__ == "__main__":
    launch()
