import streamlit as st  # type: ignore


class UIHelper:
    @staticmethod
    def config_page():
        st.set_page_config(
            page_title='Knowledge Assistant',
            layout='wide',
            initial_sidebar_state='expanded',
            page_icon="💼",
            menu_items={
                'Get Help': 'https://streamlit.io/',
                'Report a bug': 'https://github.com',
                'About': 'About your application: **Hello world**'
            }
        )

    @staticmethod
    def setup_sidebar():
        with st.sidebar:
            # Group under a header for the main app
            st.page_link("pages/rag_agents.py",
                             label="Chat with Notes", icon="📄")

            # Group related pages under an expander
            with st.expander("Notes & Actions", expanded=True):
                st.page_link("pages/documents_upload.py",
                             label="Upload Notes", icon="📁")
                # st.page_link("pages/action_items.py",
                #              label="Check Action Items", icon="✅")

            selected_lang = st.selectbox(
                "Language", ["English"],
                index=0, on_change=UIHelper.save_lang, key="language_select"
            )
            if 'lang_setting' not in st.session_state:
                st.session_state['lang_setting'] = selected_lang

    @staticmethod
    def save_lang():
        st.session_state['lang_setting'] = st.session_state.get(
            "language_select")

    @staticmethod
    def setup_chat(st_c_chat):
        user_image = "https://www.w3schools.com/howto/img_avatar.png"
        # st_c_chat = st.container(border=True)

        if "messages" not in st.session_state:
            st.session_state.messages = []
        else:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st_c_chat.chat_message(
                            msg["role"], avatar=user_image
                        ).markdown(msg["content"])
                elif msg["role"] == "assistant":
                    st_c_chat.chat_message(
                            msg["role"]
                        ).markdown(msg["content"])
                else:
                    try:
                        image_tmp = msg.get("image")
                        if image_tmp:
                            st_c_chat.chat_message(msg["role"],
                                                   avatar=image_tmp
                                                   ).markdown(msg["content"])
                    except Exception:
                        st_c_chat.chat_message(
                            msg["role"]
                            ).markdown(msg["content"])
