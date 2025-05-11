import streamlit as st
from openai import OpenAI
import time
import re
from dotenv import load_dotenv
import os

# Import ConversableAgent class
import autogen
from autogen import ConversableAgent, LLMConfig
from autogen import AssistantAgent, UserProxyAgent, LLMConfig
from autogen.code_utils import content_str
from coding.constant import JOB_DEFINITION, RESPONSE_FORMAT

# Load environment variables from .env file
# load_dotenv(override=True)

st.set_page_config(
        page_title='On-boarding Mentor',
        layout='wide',
        initial_sidebar_state='auto',
        menu_items={
            'Get Help': 'https://streamlit.io/',
            'Report a bug': 'https://github.com',
            'About': 'About your application: **Hello world**'
            },
        page_icon="img/favicon.ico"
    )


# https://ai.google.dev/gemini-api/docs/pricing
# URL configurations
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

placeholderstr = "Please input your command"
user_name = "On-boarding Mentor"
user_image = "https://www.w3schools.com/howto/img_avatar.png"

seed = 42

llm_config_gemini = LLMConfig(
    api_type = "google", 
    model="gemini-2.0-flash-lite",                    # The specific model
    api_key=GEMINI_API_KEY,   # Authentication
)

llm_config_openai = LLMConfig(
    api_type = "openai", 
    model="gpt-4o-mini",                    # The specific model
    api_key=OPENAI_API_KEY,   # Authentication
)

if not st.secrets.get("OPENAI_API_KEY"):
    st.error("❌ OPENAI_API_KEY not loaded from secrets.toml or Streamlit Cloud.")
else:
    st.success("✅ OPENAI_API_KEY loaded successfully.")

with llm_config_openai:
    assistant = AssistantAgent(
        name="assistant",
        system_message=(
            "You are a helpful agent coordinator for an onboarding website. "
            "Your role is to guide new employees through the platform and help them understand how to use its features. "
            "When users ask questions like 'How should I start with this website?', respond with an overview of the site's purpose: "
            "'This website helps you get familiar with your company and onboarding process! The website allows you to: "
            "1. Visualize the enterprise culture, "
            "2. Understand organization stakeholders, and "
            "3. Grow with the company using your personal note.' "
            "Direct users to the appropriate subpages as follows: "
            "- For culture, visit 'Culture Visualization' subpage. "
            "- For stakeholder mapping, visit 'Organization Stakeholders' and upload a stakeholder map. "
            "- For note-taking, go to 'Personal Note' and upload daily markdown notes to receive reminders on your content. "
            "Answer all user questions in a concise and helpful way based on this structure."
        ),
        llm_config=llm_config_openai,
        max_consecutive_auto_reply=2
    )

    
user_proxy = UserProxyAgent(
    "user_proxy",
    human_input_mode="NEVER",
    code_execution_config=False,
    is_termination_msg=lambda x: content_str(x.get("content")).find("ALL DONE") >= 0,
)

# Function Declaration 

def stream_data(stream_str):
    for word in stream_str.split(" "):
        yield word + " "
        time.sleep(0.05)

def save_lang():
    st.session_state['lang_setting'] = st.session_state.get("language_select")

def paging():
    st.page_link("streamlit_app.py", label="Home", icon="🏠")
    st.page_link("pages/rag_agents.py", label="RAG Agent Space", icon="🤖")
    st.page_link("pages/documents_upload.py", label="📄 Document Upload", icon="📤")

def main():
    # Show title and description.
    st.title(f"💬 {user_name}")

    with st.sidebar:
        paging()
        selected_lang = st.selectbox("Language", ["English", "繁體中文"], index=0, on_change=save_lang, key="language_select")
        if 'lang_setting' in st.session_state:
            lang_setting = st.session_state['lang_setting']
        else:
            lang_setting = selected_lang
            st.session_state['lang_setting'] = lang_setting

        st_c_1 = st.container(border=True)
        with st_c_1:
            st.image("https://www.w3schools.com/howto/img_avatar.png")

    st_c_chat = st.container(border=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                if user_image:
                    st_c_chat.chat_message(msg["role"],avatar=user_image).markdown((msg["content"]))
                else:
                    st_c_chat.chat_message(msg["role"]).markdown((msg["content"]))
            elif msg["role"] == "assistant":
                st_c_chat.chat_message(msg["role"]).markdown((msg["content"]))
            else:
                try:
                    image_tmp = msg.get("image")
                    if image_tmp:
                        st_c_chat.chat_message(msg["role"],avatar=image_tmp).markdown((msg["content"]))
                except:
                    st_c_chat.chat_message(msg["role"]).markdown((msg["content"]))


    story_template = ("'##PROMPT##'."
                      f"And remeber to mention user's name {user_name} in the end."
                      f"Please express in {lang_setting}")

    classification_template = ("You are a classification agent, your job is to classify what ##PROMPT## is according to the job definition list in <JOB_DEFINITION>"
    "<JOB_DEFINITION>"
    f"{JOB_DEFINITION}"
    "</JOB_DEFINITION>"
    # "Please output in JSON-format only."
    # "JSON-format is as below:"
    # f"{RESPONSE_FORMAT}"
    "Let's think step by step."
    # f"Please output in {lang_setting}"
    )

    def generate_response(prompt):

        prompt_template = f"I would like to know'{prompt}'"
        # prompt_template = story_template.replace('##PROMPT##',prompt)
        # prompt_template = classification_template.replace('##PROMPT##',prompt)
        result = user_proxy.initiate_chat(
        recipient=assistant,
        message=prompt_template
        )

        response = result.chat_history
        return response

    def show_chat_history(chat_hsitory):
        for entry in chat_hsitory:
            role = entry.get('role')
            name = entry.get('name')
            content = entry.get('content')
            st.session_state.messages.append({"role": f"{role}", "content": content})

            if len(content.strip()) != 0: 
                if 'ALL DONE' in content:
                    return 
                else: 
                    if role != 'assistant':
                        st_c_chat.chat_message(f"{role}").write((content))
                    else:
                        st_c_chat.chat_message("user",avatar=user_image).write(content)
    
        return 

    # Chat function section (timing included inside function)
    def chat(prompt: str):
        st_c_chat.chat_message("user",avatar=user_image).write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        response = generate_response(prompt)
        show_chat_history(response)
    
    if prompt := st.chat_input(placeholder=placeholderstr, key="chat_bot"):
        chat(prompt)

if __name__ == "__main__":
    main()
