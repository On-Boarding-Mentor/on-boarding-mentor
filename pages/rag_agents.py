import streamlit as st  # type: ignore
import re
import os
import time
from autogen import ConversableAgent, UserProxyAgent  # type: ignore
from autogen.code_utils import content_str  # type: ignore
from typing import Dict, List  # type: ignore
from utils.ui_helper import UIHelper
from utils.llm_setup import LLMSetup   # type: ignore


class Config:
    """Configuration class for API keys and constants."""
    GEMINI1_API_KEY, GEMINI2_API_KEY = LLMSetup.load_api_keys()
    SEED = 42
    ORG_KEYWORDS = ["org", "organization", "structure",
                    "team", "manager", "lead", "report",
                    "department", "chart"]
    TERMINATION_PHRASES = [
        "I'm unable to provide",
        "I am sorry",
        "need more information",
        "please provide a question",
        "please clarify",
        "no relevant answer",
        "I apologize"
    ]


class DocumentLoader:
    """Handles loading of markdown documents from specified directories."""
    @staticmethod
    def load_documents() -> Dict[str, Dict[str, str]]:
        base_dirs = {
            "personal": "uploaded_docs/personal",
            "org": "uploaded_docs/org"
        }
        docs = {"personal": {}, "org": {}}
        for category, path in base_dirs.items():
            if os.path.exists(path):
                for fname in os.listdir(path):
                    if fname.endswith(".md"):
                        with open(os.path.join(path, fname), "r",
                                  encoding="utf-8") as f:
                            docs[category][fname] = f.read()
        return docs


class MermaidExtractor:
    """Extracts Mermaid code blocks from markdown content."""
    @staticmethod
    def extract_mermaid_blocks(markdown_text: str) -> List[str]:
        pattern = r"```mermaid\n(.*?)```"
        return re.findall(pattern, markdown_text, re.DOTALL)


class AgentFactory:
    """Creates and configures autogen agents."""
    @staticmethod
    def create_graph_agent() -> ConversableAgent:
        return ConversableAgent(
            name="GraphRAG_Agent",
            system_message="You are a GraphRAG Agent specializing "
            "in querying an organizational structure stored in a graph DB."
            "Your role is to answer questions about employees,"
            "such as their email, position, or reporting relationships."
            "Use precise and accurate information retrieved from the graph DB"
            "If the query is unclear or the information is unavailable,"
            "politely explain and ask for clarification.",
            llm_config=LLMSetup.create_llm_config(Config.GEMINI2_API_KEY)
        )

    @staticmethod
    def create_text_agent() -> ConversableAgent:
        return ConversableAgent(
            name="TextRAG_Agent",
            system_message="You are a TextRAG Agent designed to"
            "answer questions based on personal markdown notes."
            "Your role is to retrieve relevant information"
            "from the notes and provide clear, concise answers."
            "Focus on understanding the context of the notes"
            "and delivering responses that align with the user's intent."
            "If the notes lack relevant information,"
            "inform the user and"
            "suggest rephrasing or providing more details.",
            llm_config=LLMSetup.create_llm_config(Config.GEMINI1_API_KEY)
        )

    @staticmethod
    def create_user_proxy() -> UserProxyAgent:
        return LLMSetup.create_user_proxy(
            is_termination_msg=lambda x: any(
                phrase in content_str(x.get("content", "")).lower()
                for phrase in Config.TERMINATION_PHRASES
            )
        )


class ChatManager:
    """Manages chat interactions and history."""
    def __init__(self):
        self.graph_agent = AgentFactory.create_graph_agent()
        self.text_agent = AgentFactory.create_text_agent()
        self.user_proxy = AgentFactory.create_user_proxy()
        self.user_name = "OMT Project Management Office, Business Planning"
        self.assistant_avatar = "🧠"
        self.user_avatar = "https://www.w3schools.com/howto/img_avatar.png"
        self.placeholderstr = "Chat with On-boarding Mentor to start on-boarding"
        
        if 'rag_messages' not in st.session_state:
            st.session_state.rag_messages = []

    def should_stop(self, chat_history: List[Dict]) -> bool:
        agent_roles = ["TextRAG_Agent", "GraphRAG_Agent"]
        last_few = [
            msg["content"].strip().lower()
            for msg in chat_history[-3:]
            if msg["role"] in agent_roles
        ]
        generic_phrases = Config.TERMINATION_PHRASES
        return all(any(generic in resp
                       for generic in generic_phrases)for resp in last_few)

    def _get_avatar(self, role: str) -> str:
        if role == "user_proxy":
            return "🧠"
        elif role == "user":
            return "👩‍💼"
        elif role in ["TextRAG_Agent", "GraphRAG_Agent"]:
            return "👩‍💼"
        else:
            return Config.USER_IMAGE

    def stream_response(self, text: str):
        for word in text.split():
            yield word + " "
            time.sleep(0.03)

    def generate_response(self, prompt: str) -> List[Dict]:
        docs = DocumentLoader.load_documents()
        prompt_lower = prompt.lower()
        is_org_related = any(keyword in prompt_lower for
                             keyword in Config.ORG_KEYWORDS)
        if is_org_related:
            mermaid_blocks = []
            for content in docs.get("org", {}).values():
                mermaid_blocks += MermaidExtractor.extract_mermaid_blocks(
                    content
                )
            mermaid_diagrams = "\n\n".join(f"```mermaid\n{block}\n```"
                                           for block in mermaid_blocks)
            final_prompt = (
                "Based on the following organization charts,"
                "answer the user's question."
                "Only use this information to determine reporting lines,"
                "structure, or team relationships."
                "Do not include any Mermaid diagrams or"
                "raw reference material in your response:\n\n"
                f"{mermaid_diagrams}\n\nUser's question: {prompt}"
            )

            # Run the chat with history
            response = self.user_proxy.initiate_chat(
                self.graph_agent,
                message=final_prompt,
                summary_method="reflection_with_llm",
                max_turns=1
            )

            if self.should_stop(response.chat_history):
                response.chat_history.append({
                    "role": self.graph_agent.name,
                    "content": "Ending the chat as "
                    "no relevant answer can be provided."
                })

        else:
            personal_content = "\n\n".join(
                f"# {fname}\n{content}"
                for fname, content in docs.get("personal", {}).items()
            )
            final_prompt = (
                "Use the following personal notes to"
                "answer the user's question."
                "Do not include any raw personal notes"
                "or reference material in your response:\n\n"
                f"{personal_content}\n\nUser's question: {prompt}"
            )

            response = self.user_proxy.initiate_chat(
                self.text_agent,
                message=final_prompt,
                summary_method="reflection_with_llm",
                max_turns=1
            )

            if self.should_stop(response.chat_history):
                response.chat_history.append({
                    "role": self.text_agent.name,
                    "content": "Ending the chat as no helpful"
                    "answer can be provided."
                })

        # Clean history
        filtered_history = [
            msg for msg in response.chat_history
            if not any(keyword in msg.get("content", "").lower()
                       for keyword in [
                "```mermaid", "# personal", "based on the following",
                "use the following"
            ])
        ]
        return filtered_history

    def show_chat_history(self, chat_history: List[Dict], container) -> None:
        for i, entry in enumerate(chat_history):
            role = entry.get("role", "assistant")
            content = entry.get("content", "").strip()
            if not content:
                continue

            avatar = self._get_avatar(role)
            st.session_state.rag_messages.append({"role": role,
                                                  "content": content,
                                                  "avatar": avatar})

            # Handle user input
            if role == "user_proxy":
                container.chat_message(
                    "user", avatar="🧠").write(f"*System prompted:* {content}")
            elif role == "user":
                container.chat_message(
                    "user", avatar="👩‍💼").write(content)

            # Handle agent responses
            elif role in ["TextRAG_Agent", "GraphRAG_Agent"]:
                with container.chat_message("assistant", avatar="👩‍💼"):
                    if i == len(chat_history) - 1:
                        st.write_stream(self.stream_response(content))
                    else:
                        st.markdown(content)  # Older replies render instantly
            else:
                with container.chat_message(
                    "assistant", avatar=Config.USER_IMAGE
                ):
                    if i == len(chat_history) - 1:
                        st.write_stream(self.stream_response(content))
                    else:
                        st.markdown(content)


def stream_data(stream_str: str):
    for word in stream_str.split(" "):
        yield word + " "
        time.sleep(0.05)


def save_lang():
    st.session_state['lang_setting'] = st.session_state.get("language_select")


def run(self):
    UIHelper.config_page()
    UIHelper.setup_sidebar()
    st.title(f"💬 {user_name}")
    st_c_chat = st.container(border=True)
    UIHelper.setup_chat(st_c_chat)
    chat_manager = ChatManager()


if __name__ == "__main__":
    chatmanager = ChatManager()
    chatmanager.run()
