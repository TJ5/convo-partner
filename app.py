import streamlit as st
import os
import openai
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
import json
import base64

GPT_MODEL = "gpt-4"
STATES = ["AWAITING_INPUT", "LISTENING", "RESPONDING", "ENDED_CONVERSATION"]
# Load API keys
with open('openai_key.txt') as f:
    openai.api_key = f.read()

with open('google_key.txt') as f:
    GOOGLE_SPEECH_KEY = f.read()

# Initialize recognizer and microphone
r = sr.Recognizer()
m = sr.Microphone()

# Starting messages for the conversation
INITIAL_MESSAGES = [
    {"role": "system", "content": "You are an English tutor holding a conversation with a student."},
    {"role": "system",
     "content": "Your job is to evaluate how good the student's English is by by calling the increment_user_score function every message."},
    {"role": "system",
     "content": "If the student responds in a nonsensical or incorrect way, correct them as best you can or state that you do not understand."},
    {"role": "system",
     "content": "Otherwise, respond to the student and ask follow up questions to keep the conversation going."},
    {"role": "system",
     "content": "When you assign evaluation scores, assign more points for more complex responses, such as responses that contain multiple sentences or complex words."},
    {"role": "system", "content": "If a sentence is incomplete, ask the student to finish their thought."},
    {"role": "system",
     "content": "If the student is confused or does not know how to answer, offer suggestions. For example, if they do not know how to answer about how the weather is, ask them if it is sunny or rainy."},
    {"role": "system",
     "content": "Make sure to assign evaluation scores every message to reward growth and improvement."},
    {"role": "system", "content": "If responses are consistently too short, ask the student to elaborate. For example, if you ask the student for their hobby, and they respond with just one word, ask the student to say more."},
    {"role": "assistant", "content": "Hello, what do you want to talk about?"}
]

messages = INITIAL_MESSAGES.copy()

#Define list of streamlist strings to write 
if 'session_strings' not in st.session_state:
    st.session_state['session_strings'] = []
    st.session_state['session_strings'].append(INITIAL_MESSAGES[-1]['content'])

if 'user_score' not in st.session_state:
    st.session_state['user_score'] = 0

if 'has_audio' not in st.session_state:
    st.session_state['has_audio'] = False

if 'user_audio' not in st.session_state: 
    st.session_state['user_audio'] = None

if 'current_state' not in st.session_state:
    st.session_state['current_state'] = STATES[0]

def set_state(state: int):
    st.session_state['current_state'] = STATES[state]

#Helper function to play audio in streamlit
def autoplay_audio(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio controls autoplay="true">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(
            md,
            unsafe_allow_html=True,
        )


#Function for GPT to end conversation
def set_end_flag(end_conversation: bool):
    """Sets session state end_conversation to end_conversation"""
    if end_conversation:
        set_state(3)
        st.session_state['session_strings'] = []
        st.session_state['session_strings'].append(INITIAL_MESSAGES[-1]['content'])
        st.session_state['user_score'] = 0
        st.session_state['has_audio'] = False
        st.session_state['user_audio'] = None
    else:
        if st.session_state['current_state'] == STATES[3]:
            set_state(0)
    return json.dumps({
        "conversation_terminated": end_conversation
    })

#Function for GPT to increment user score
def increment_user_score(message_score: int):
    """Increments user_score by message_score"""
    st.session_state['user_score'] += message_score
    return json.dumps({
        "user_score": st.session_state['user_score'],
        "message_score": message_score
    })


functions = [
    {
        "name": "set_end_flag",
        "description": "Ends the current conversation",
        "parameters": {
            "type": "object",
            "properties": {
                "end_conversation": {
                    "type ": "boolean",
                    "description": "Whether or not to end the conversation"
                }
            },
            "required": ["end_conversation"]
        }
    },
    {
        "name": "increment_user_score",
        "description": """Call this function every time! Adds an integer from 100 to 1000 to the user's score, representing how well they responded.""",
        "parameters": {
            "type": "object",
            "properties": {
                "message_score": {
                    "type ": "integer",
                    "description": "A score from 100 to 1000 representing how good the user's last response was. 1000 is a complex, grammatically correct, and relevant response while a 100 is a poor or incorrect response."
                }
            },
            "required": ["message_score"]
        }
    },
]

available_functions = {
    "set_end_flag": set_end_flag,
    "increment_user_score": increment_user_score
}

st.title("English Tutor Conversation")

#Next State Logic
if st.session_state['current_state'] == STATES[0]:
    if st.button("Start Speaking"):
        set_state(1)
        st.rerun()
elif st.session_state['current_state'] == STATES[1]:
    st.button("Listening...", disabled=True)
elif st.session_state['current_state'] == STATES[2]:
    st.button("Loading Response...", disabled=True)
else:
    st.button("Start Speaking", disabled=True)

st.sidebar.text("User Score: {}".format(st.session_state['user_score']))
if st.session_state['current_state'] == STATES[3]:
    st.sidebar.button("Start Conversation", on_click=set_end_flag, args=(False,))
else:
    st.sidebar.button("End Conversation", on_click=set_end_flag, args=(True,))

if st.session_state['current_state'] == STATES[1]:
    # Listen to user's speech
    with m as source:
        r.adjust_for_ambient_noise(source)
        st.session_state['user_audio'] = r.listen(source, phrase_time_limit=5)
    set_state(2)
    st.rerun()
# Convert speech to text
if st.session_state['current_state'] == STATES[2]:
    try:
        user_speech = r.recognize_google(st.session_state['user_audio'])
        st.session_state['session_strings'].append(f"You: {user_speech}")
        # Add user's message to the conversation
        messages.append({"role": "user", "content": user_speech})
        # Get a response from OpenAI API
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            functions=functions
        )

        assistant_response = response.choices[0].message

        # Check if a function was called
        if assistant_response.get('function_call'):
            function_name = assistant_response["function_call"]["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(assistant_response["function_call"]["arguments"])

            if function_name == "set_end_flag":
                function_response = function_to_call(
                    end_conversation=function_args.get("end_conversation")
                )
            elif function_name == "increment_user_score":
                function_response = function_to_call(
                    message_score=function_args.get("message_score")
                )

            messages.append(assistant_response)
            messages.append({"role": "function", "name": function_name, "content": function_response})

            response = openai.ChatCompletion.create(
                model=GPT_MODEL,
                messages=messages,
            )  # get a new response from GPT where it can see the function response

            assistant_response = response.choices[0].message
            messages.append(assistant_response)

        st.session_state['session_strings'].append(f"Assistant: {assistant_response.content}")
        tts = gTTS(text=assistant_response.content, lang='en', slow=False, tld='us')
        tts.save("response.mp3")
        audio = AudioSegment.from_mp3("response.mp3")
        audio.speedup(playback_speed=1.2).export("response.mp3", format="mp3")
        # Consider hosting the MP3 and providing a link or using a package to play it directly in the browser
        #st.audio("response.mp3", format="audio/mp3")
        st.session_state['has_audio'] = True
        st.session_state['user_audio'] = None
    except sr.UnknownValueError:
        st.session_state['session_strings'].append("Sorry, I couldn't understand that. Please try again.")
    except sr.RequestError as e:
        st.session_state['session_strings'].append("Could not request results from Google Speech Recognition service;")
    set_state(0)
    st.rerun()

# If user chooses to end the conversation
if st.session_state['current_state'] == STATES[3]:
    st.write("The conversation has ended. If you'd like to start again, click Start Conversation.")
else:
    #Print the messages in the session state
    for s in st.session_state['session_strings']:
        st.markdown(s)

    if st.session_state['has_audio']:
        try:
            autoplay_audio("response.mp3")
        except:
            pass
