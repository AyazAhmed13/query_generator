'''import gradio as gr
from core.crew_executor import process_user_question
print('working...')
def chat(user_input):
    sql, result = process_user_question(user_input)
    if isinstance(result, dict) and 'error' in result:
        return f"❌ Error: {result['error']}\nSQL: {sql}"
    elif not result:
        return f"No results found.\nSQL: {sql}"
    else:
        output = f"✅ SQL:\n{sql}\n\n📊 Result:\n"
        for row in result:
            output += f"{row}\n"
        return output

def launch():
    gr.Interface(fn=chat, inputs="text", outputs="text", title="SQL Chatbot with YAML Agents").launch()'''
'''
import gradio as gr
from core.crew_executor import process_user_question

def chat(user_input):
    sql, result = process_user_question(user_input)
    if isinstance(result, dict) and 'error' in result:
        return f"❌ Error: {result['error']}\nSQL: {sql}"
    elif not result:
        return f"No results found.\nSQL: {sql}"
    else:
        output = f"✅ SQL:\n{sql}\n\n📊 Result:\n"
        for row in result:
            output += f"{row}\n"
        return output

def launch():
    print("Launching Gradio interface...")  # Debug confirmation
    interface = gr.Interface(
        fn=chat,
        inputs="text",
        outputs="text",
        title="SQL Chatbot with YAML Agents"
    )
    interface.launch()

if __name__ == "__main__":
    print("working...")  # This will show first
    launch()  # <-- THIS WAS MISSING IN YOUR ORIGINAL CODE'''


import gradio as gr
from core.crew_executor import process_user_question

def chat(user_input):
    try:
        sql, result = process_user_question(user_input)
        if isinstance(result, dict) and 'error' in result:
            return f"❌ Error: {result['error']}\nSQL: {sql}"
        elif not result:
            return f"No results found.\nSQL: {sql}"
        else:
            output = f"✅ SQL:\n{sql}\n\n📊 Result:\n"
            for row in result:
                output += f"{row}\n"
            return output
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"

def launch():
    interface = gr.Interface(
        fn=chat,
        inputs="text",
        outputs="text",
        title="SQL Chatbot ",
        description="Ask natural language questions about your database"
    )
    interface.launch()

if __name__ == "__main__":
    print("Starting SQL Chatbot...")
    launch()