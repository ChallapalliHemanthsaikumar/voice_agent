import streamlit as st
import asyncio
import threading
from agent import agent
from polly import synthesize_and_play_direct
from transcribe import MicStream, stream_to_transcribe
import time
import io
import numpy as np
import sounddevice as sd
from audio_recorder_streamlit import audio_recorder


# Configure Streamlit page
st.set_page_config(
    page_title="Voice Agent",
    page_icon="🎤",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'recording_state' not in st.session_state:
    st.session_state.recording_state = "idle"  # idle, recording, processing
if 'current_transcript' not in st.session_state:
    st.session_state.current_transcript = ""


def process_agent_response(response):
    """Extract text from the agent response structure"""
    try:
        # Handle the structured response from the agent
        if hasattr(response, 'message'):
            response_data = response.message
        elif hasattr(response, 'text'):
            response_data = response.text
        elif hasattr(response, 'content'):
            response_data = response.content
        else:
            response_data = str(response)
        
        # Extract text from the nested structure
        if isinstance(response_data, dict):
            if 'content' in response_data and isinstance(response_data['content'], list):
                response_text = response_data['content'][0]['text']
            elif 'content' in response_data and isinstance(response_data['content'], str):
                response_text = response_data['content']
            elif 'text' in response_data:
                response_text = response_data['text']
            else:
                response_text = str(response_data)
        else:
            response_text = str(response_data)
        
        return response_text
    except Exception as e:
        return f"Error processing response: {e}"


def get_agent_response(user_input):
    """Get response from the agent"""
    try:
        result = agent(user_input)
        return process_agent_response(result)
    except Exception as e:
        return f"Error: {e}"


def play_audio_async(text):
    """Play audio in a separate thread"""
    def play_audio():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(synthesize_and_play_direct(text))
        except Exception as e:
            print(f"TTS error: {e}")
    
    thread = threading.Thread(target=play_audio)
    thread.daemon = True
    thread.start()


def record_and_transcribe():
    """Record audio and transcribe using existing transcribe functionality"""
    try:
        # This is a simplified version - in production you'd want proper async handling
        st.session_state.recording_state = "recording"
        st.rerun()
        
        # Create a simple recording function
        def do_recording():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            transcript = ""
            
            async def on_partial(text):
                st.session_state.current_transcript = f"Listening: {text}"
            
            async def on_final(text):
                nonlocal transcript
                transcript = text
                st.session_state.current_transcript = f"Final: {text}"
            
            try:
                async def record_voice():
                    async with MicStream() as mic:
                        await stream_to_transcribe(mic, on_partial=on_partial, on_final=on_final)
                
                # Record for 5 seconds
                loop.run_until_complete(asyncio.wait_for(record_voice(), timeout=5.0))
                
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                transcript = f"Recording error: {e}"
            
            st.session_state.recording_state = "idle"
            return transcript
        
        return do_recording()
    
    except Exception as e:
        st.session_state.recording_state = "idle"
        return f"Error: {e}"


def main():
    st.title("🎤 Voice Agent Interface")
    st.markdown("Interact with your AI agent using **voice** or **text** input!")
    
    # Create two columns for input methods
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("🎤 Voice Input")
        
        # Voice recording button
        if st.session_state.recording_state == "idle":
            if st.button("🎤 Start Voice Recording", use_container_width=True, type="primary"):
                st.session_state.recording_state = "recording"
                st.rerun()
        
        elif st.session_state.recording_state == "recording":
            st.warning("🔴 Recording... Speak now! (5 seconds max)")
            
            # Start recording in background
            def record_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    final_transcript = ""
                    
                    async def on_partial(text):
                        st.session_state.current_transcript = f"🎙️ {text}"
                    
                    async def on_final(text):
                        nonlocal final_transcript
                        final_transcript = text
                        # Process the voice input
                        if final_transcript.strip():
                            st.session_state.messages.append({"role": "user", "content": final_transcript})
                            response = get_agent_response(final_transcript)
                            st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    async def record_voice():
                        async with MicStream() as mic:
                            await stream_to_transcribe(mic, on_partial=on_partial, on_final=on_final)
                    
                    # Record for 5 seconds
                    loop.run_until_complete(asyncio.wait_for(record_voice(), timeout=5.0))
                    
                except Exception as e:
                    st.session_state.current_transcript = f"Recording error: {e}"
                
                finally:
                    st.session_state.recording_state = "idle"
            
            # Start recording thread
            if 'recording_thread' not in st.session_state or not st.session_state.recording_thread.is_alive():
                st.session_state.recording_thread = threading.Thread(target=record_thread, daemon=True)
                st.session_state.recording_thread.start()
            
            # Show current transcript
            if st.session_state.current_transcript:
                st.info(st.session_state.current_transcript)
            
            # Stop button
            if st.button("⏹️ Stop Recording", use_container_width=True):
                st.session_state.recording_state = "idle"
                st.session_state.current_transcript = ""
                st.rerun()
        
        # Alternative: Simple audio recorder (if the above doesn't work well)
        st.markdown("---")
        st.markdown("**Alternative: Audio Recorder**")
        
        try:
            # Simple audio recorder widget
            audio_bytes = audio_recorder(
                text="Click to record",
                recording_color="#e8b62c",
                neutral_color="#6ca395",
                icon_name="microphone-lines",
                icon_size="2x",
            )
            
            if audio_bytes:
                st.audio(audio_bytes, format="audio/wav")
                st.info("🔄 Audio recorded! (Note: Transcription requires integration with AWS Transcribe)")
                
                # For now, show a placeholder
                if st.button("� Process Audio", key="process_audio"):
                    placeholder_text = "Audio transcription would happen here with AWS Transcribe"
                    st.session_state.messages.append({"role": "user", "content": placeholder_text})
                    response = get_agent_response(placeholder_text)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()
        
        except Exception as e:
            st.error(f"Audio recorder not available: {e}")
    
    with col2:
        st.header("💬 Text Input")
        
        # Text input form
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_area(
                "Enter your message:",
                placeholder="Type your question or message here...",
                height=150,
                key="user_input"
            )
            
            submitted = st.form_submit_button("💬 Send Message", use_container_width=True)
            
            if submitted and user_input.strip():
                # Add user message
                st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                
                # Get agent response
                with st.spinner("🤔 Agent is thinking..."):
                    response = get_agent_response(user_input.strip())
                    st.session_state.messages.append({"role": "assistant", "content": response})
                
                st.rerun()
    
    # Display conversation history
    if st.session_state.messages:
        st.header("💭 Conversation History")
        
        # Create container for messages
        chat_container = st.container()
        
        with chat_container:
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                else:
                    with st.chat_message("assistant"):
                        st.write(message["content"])
                        
                        # Add audio playback controls
                        col1, col2, col3 = st.columns([1, 1, 4])
                        
                        with col1:
                            if st.button("🔊 Play", key=f"play_{i}", help="Play audio response"):
                                try:
                                    play_audio_async(message["content"])
                                    st.success("🎵 Playing audio...")
                                except Exception as e:
                                    st.error(f"Audio error: {e}")
        
        # Control buttons
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Conversation", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
    
    else:
        st.info("👋 Welcome! Start a conversation by typing a message above.")
        
        # Example messages
        st.markdown("### 💡 Try asking:")
        example_questions = [
            "What time is it?",
            "Tell me about artificial intelligence",
            "How can you help me?",
            "What tools do you have access to?"
        ]
        
        for question in example_questions:
            if st.button(f"💭 {question}", key=f"example_{question}"):
                # Add the example question as user input
                st.session_state.messages.append({"role": "user", "content": question})
                
                # Get response
                with st.spinner("🤔 Agent is thinking..."):
                    response = get_agent_response(question)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                
                st.rerun()
    
    # Sidebar with information
    with st.sidebar:
        st.header("🤖 Voice Agent")
        st.markdown("**User:** Hemanth (AI Engineer)")
        
        st.header("📋 Features")
        st.markdown("""
        ✅ **Text Chat Interface**
        - Type your questions
        - Get AI responses
        - View conversation history
        
        ✅ **Audio Playback** 
        - Click 🔊 to hear responses
        - Text-to-speech with Polly
        
        ✅ **Agent Tools**
        - Time queries
        - AI assistance
        - Custom capabilities
        """)
        
        st.header("⚙️ Status")
        st.success("🟢 Agent Ready")
        
        if st.session_state.messages:
            st.metric("Messages", len(st.session_state.messages))
            
            user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
            agent_msgs = len([m for m in st.session_state.messages if m["role"] == "assistant"])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("You", user_msgs)
            with col2:
                st.metric("Agent", agent_msgs)
        
        st.header("🔧 Tech Stack")
        st.markdown("""
        - **Frontend:** Streamlit
        - **Agent:** Strands Framework
        - **TTS:** Amazon Polly
        - **Backend:** AWS Bedrock
        """)


if __name__ == "__main__":
    main()
