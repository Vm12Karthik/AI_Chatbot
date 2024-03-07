import streamlit as st
import openai
import sqlite3
import gradio as gr
from config import open_api_key

# Initialize OpenAI API key
openai.api_key = open_api_key

# Function to interact with the OpenAI model
def openai_create(prompt):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
        stop=[" Human:", " AI:"]
    )
    return response.choices[0].text

# Function to create the users table in the SQLite database
def create_users_table():
    connection = sqlite3.connect("users.db")
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
    connection.commit()
    connection.close()

# Function to insert a new user into the database
def insert_user(username, password):
    connection = sqlite3.connect("users.db")
    cursor = connection.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?)", (username, password))
    connection.commit()
    connection.close()

# Function to check if a user exists in the database
def user_exists(username, password):
    connection = sqlite3.connect("users.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    connection.close()
    return user is not None

# Create the users table (if it doesn't exist) when the app starts
create_users_table()

# Specify the URL or file path
logo_url = "./ai.jpeg"  

# Streamlit App
st.set_page_config(
    page_title="chatbot",
    page_icon=":robot:"
)

# Display the doctor's image as a logo
st.sidebar.image(logo_url, use_column_width=True, width=150, output_format="PNG")

st.title("Healthcare Chatbot")
st.subheader("Describe your symptoms or the reason for your visit?")

# User registration
st.sidebar.header("User Registration")
registration_username = st.sidebar.text_input("Username (Register)", key="reg_username")
registration_password = st.sidebar.text_input("Password (Register)", type="password", key="reg_password")
if st.sidebar.button("Register"):
    insert_user(registration_username, registration_password)
    st.sidebar.text("Registration successful!")

# User login
st.sidebar.header("User Login")
login_username = st.sidebar.text_input("Username (Login)", key="login_username")
login_password = st.sidebar.text_input("Password (Login)", type="password", key="login_password")
if st.sidebar.button("Login"):
    if user_exists(login_username, login_password):
        st.sidebar.text("Login successful!")
        st.session_state.logged_in = True
    else:
        st.sidebar.text("Login failed. Please check your credentials or register first.")

# Initialize chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Ensure that the user is logged in to use the chat
if st.session_state.get("logged_in", False):
    def get_text():
        input_text = st.text_input("Text: ", key="input")
        return input_text

    user_input = get_text()

    if user_input:
        # Generate a response using the OpenAI model
        response = openai_create(user_input)

        # Append the user's message and the chatbot's response to the chat history
        st.session_state.chat_history.append((user_input, response))

# Display chat history with bold formatting
for i, (user_message, response) in enumerate(st.session_state.chat_history):
    st.markdown(f'<b>You: </b> {user_message}', unsafe_allow_html=True)
    st.markdown(f'<b>Doctor:\n</b> {response}', unsafe_allow_html=True)


# Add a footer or any other elements to enhance the design
st.markdown(
    """
    <hr style="border: 1px solid #ddd; margin-top: 20px; margin-bottom: 20px;">
    <p style="text-align: center; color: #888;">Chatbot - © 2023</p>
    """,
    unsafe_allow_html=True,
)

