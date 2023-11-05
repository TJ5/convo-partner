import streamlit as st
import openai
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
import json

from profiles import get_mode_starting_messages

# Load API keys
with open('openai_key.txt') as f:
    openai.api_key = f.read()

with open('google_key.txt') as f:
    GOOGLE_SPEECH_KEY = f.read()

# Initialize recognizer and microphone
r = sr.Recognizer()
m = sr.Microphone()

mode = 'free'
GPT_MODEL = "gpt-4"


def increment_user_score(message_score: int):
    """Increments user_score by message_score"""
    global user_score
    user_score += message_score
    return json.dumps({
        "user_score": user_score,
        "message_score": message_score
    })


def create_model(messages_):
    return openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=messages_,
        functions=FUNCTIONS
    )


FUNCTIONS = [
    {
        "name": "increment_user_score",
        "description": "Call this function every time! Takes an integer from 0 to 10 representing how well the user responded. Adds this integer to the user's score.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_score": {
                    "type ": "integer",
                    "description": "A score from 0 to 10 representing how good the user's last response was. A 10 is a great response while a 0 is a poor or incorrect response."
                }
            },
            "required": ["message_score"]
        }
    },
]

AVAILABLE_FUNCTIONS = {
    # "set_end_flag": set_end_flag,
    "increment_user_score": increment_user_score
}

# Starting messages_ for the conversation
messages = get_mode_starting_messages(mode)
user_score = 0
stop_conversation = False


def tts_save(text: str, filename: str):
    """Saves text to an MP3 file"""
    tts = gTTS(text=text, lang='en', slow=False, tld='us')
    tts.save(filename)
    audio = AudioSegment.from_mp3(filename)
    audio.speedup(playback_speed=1.3).export(filename, format="mp3")


def set_mode(new_mode: str):
    global mode, messages
    mode = new_mode
    messages = get_mode_starting_messages(mode)


st.title("English Tutor Conversation")
st.sidebar.text("User Score: {}".format(user_score))
st.sidebar.button("Free Conversation", on_click=set_mode, args=('free',))
st.sidebar.button("Grammar Practice", on_click=set_mode, args=('grammar',))

try:
    initial_message = create_model(messages)
    assistant_response = initial_message.choices[0].message
    messages.append(assistant_response)
    st.write(f"{assistant_response.content}")
    tts_save(assistant_response.content, "response.mp3")
    st.audio("response.mp3")
except Exception as e:
    st.write("Error: {}".format(e))

# Check if user wants to speak
if st.button("Start Speaking"):
    # Listen to user's speech
    with m as source:
        r.adjust_for_ambient_noise(source)
        st.write("Listening... Speak now!")
        input_audio = r.listen(source, phrase_time_limit=5)

    # Convert speech to text
    try:
        user_speech = r.recognize_google(input_audio)
        st.write("You:", user_speech)
        # Add user's message to the conversation
        messages.append({"role": "user", "content": user_speech})

        # Get a response from OpenAI API
        response = create_model(messages)
        assistant_response = response.choices[0].message

        # Check if a function was called
        if assistant_response.get('function_call'):
            function_name = assistant_response["function_call"]["name"]
            function_to_call = AVAILABLE_FUNCTIONS[function_name]
            function_args = json.loads(assistant_response["function_call"]["arguments"])

            if function_name == "increment_user_score":
                function_response = function_to_call(
                    message_score=function_args.get("message_score")
                )
            else:
                raise Exception("Function not found")

            messages.append(assistant_response)
            messages.append({"role": "function", "name": function_name, "content": function_response})
            response = create_model(messages)
            assistant_response = response.choices[0].message
            messages.append(assistant_response)

        st.write(f"{assistant_response.content}")
        tts_save(assistant_response.content, "response.mp3")
        st.audio("response.mp3")
    except sr.UnknownValueError:
        st.write("Sorry, I couldn't understand that. Please try again.")
    except sr.RequestError as e:
        st.write("Could not request results from Google Speech Recognition service;", e)
