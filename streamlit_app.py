import streamlit as st
import websockets
import asyncio
import base64
import json
import pyaudio
import os
from pathlib import Path

# Session state
if 'text' not in st.session_state:
    st.session_state['text'] = 'Listening...'
    st.session_state['run'] = False

# Audio parameters
st.sidebar.header('Audio Parameters')

FRAMES_PER_BUFFER = int(st.sidebar.text_input('Frames per buffer', 3200))
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = int(st.sidebar.text_input('Rate', 16000))

p = pyaudio.PyAudio()

# Open an audio stream with the above parameter settings
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)

# Start/stop audio transmission
def start_listening():
    st.session_state['run'] = True

def stop_listening():
    st.session_state['run'] = False

# Download the transcription file
def download_transcription():
    with open('transcription.txt', 'r') as read_txt:
        st.download_button(
            label="Download transcription",
            data=read_txt,
            file_name='transcription_output.txt',
            mime='text/plain')

# Web user interface
st.title('🎙️ Real-Time Transcription App')

with st.expander('About this App'):
    st.markdown('''
    This Streamlit app uses the AssemblyAI API to perform real-time transcription.
    
    Libraries used:
    - `streamlit` - web framework
    - `pyaudio` - for audio processing
    - `websockets` - interaction with the API
    - `asyncio` - concurrent input/output processing
    - `base64` - encode/decode audio data
    - `json` - processing API responses
    ''')

col1, col2 = st.columns(2)
col1.button('Start', on_click=start_listening)
col2.button('Stop', on_click=stop_listening)

# Send and receive audio data
async def send_receive():
    URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"

    try:
        async with websockets.connect(
            URL,
            headers={"Authorization": st.secrets['api_key']},
            ping_interval=5,
            ping_timeout=20
        ) as _ws:

            await asyncio.sleep(0.1)  # Allow the connection to establish
            print("WebSocket connected!")

            # Receive initial session start message
            session_begins = await _ws.recv()
            print("Session begins:", session_begins)

            async def send():
                while st.session_state['run']:
                    try:
                        data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                        encoded_data = base64.b64encode(data).decode("utf-8")
                        json_data = json.dumps({"audio_data": encoded_data})
                        await _ws.send(json_data)
                        await asyncio.sleep(0.01)  # Adjust as needed
                    except Exception as e:
                        print("Error in sending audio:", e)
                        break

            async def receive():
                while st.session_state['run']:
                    try:
                        result_str = await _ws.recv()
                        response = json.loads(result_str)

                        if response.get('message_type') == 'FinalTranscript':
                            transcript = response.get('text', '')
                            print("Transcript received:", transcript)
                            st.session_state['text'] = transcript
                            st.write(st.session_state['text'])

                            with open('transcription.txt', 'a') as transcription_txt:
                                transcription_txt.write(st.session_state['text'] + ' ')
                    except Exception as e:
                        print("Error in receiving transcription:", e)
                        break

            await asyncio.gather(send(), receive())

    except Exception as e:
        print("WebSocket error:", e)
 
# Run async loop in a Streamlit-compatible way
if st.session_state['run']:
    asyncio.run(send_receive())

# Handle transcription file
if Path('transcription.txt').is_file():
    st.markdown('### Download')
    download_transcription()
    os.remove('transcription.txt')
