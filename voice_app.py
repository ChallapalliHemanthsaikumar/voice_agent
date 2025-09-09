import streamlit as st
import asyncio
import threading
from agent import agent
from polly import synthesize_and_play_direct
from transcribe import MicStream, stream_to_transcribe
import time


# Configure Streamlit page
st.set_page_config(
    page_title="Voice Agent",
    page_icon="🎤",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'current_partial' not in st.session_state:
    st.session_state.current_partial = ""
if 'recording_thread' not in st.session_state:
    st.session_state.recording_thread = None


def process_agent_response(response):
    """Extract text from the agent response structure"""
    try:
        if hasattr(response, 'message'):
            response_data = response.message
        elif hasattr(response, 'text'):
            response_data = response.text
        elif hasattr(response, 'content'):
            response_data = response.content
        else:
            response_data = str(response)
        
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
            st.error(f"TTS error: {e}")
    
    thread = threading.Thread(target=play_audio, daemon=True)
    thread.start()


def start_voice_recording():
    """Start voice recording with live transcription"""
    def record_voice():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def on_partial(text):
                """Handle partial transcription results"""
                st.session_state.current_partial = text
            
            async def on_final(text):
                """Handle final transcription and get agent response"""
                if text.strip():
                    # Add user message
                    st.session_state.messages.append({"role": "user", "content": text.strip()})
                    
                    # Get agent response
                    response = get_agent_response(text.strip())
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # Auto-play response
                    play_audio_async(response)
                
                # Reset recording state
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
            
            async def record_with_transcribe():
                """Main recording function"""
                async with MicStream() as mic:
                    await stream_to_transcribe(mic, on_partial=on_partial, on_final=on_final)
            
            # Run the recording
            loop.run_until_complete(record_with_transcribe())
            
        except Exception as e:
            st.session_state.messages.append({"role": "system", "content": f"Recording error: {e}"})
            st.session_state.is_recording = False
            st.session_state.current_partial = ""
    
    # Start recording thread
    st.session_state.recording_thread = threading.Thread(target=record_voice, daemon=True)
    st.session_state.recording_thread.start()


def main():
    st.title("🎤 Live Voice Agent")
    st.markdown("**Speak naturally** - the agent will automatically detect when you're done speaking!")
    
    # Voice recording section
    st.header("🎙️ Voice Input")
    
    col1, col2, col3 = st.columns([2, 2, 3])
    
    with col1:
        if not st.session_state.is_recording:
            if st.button("🎤 Start Recording", use_container_width=True, type="primary"):
                st.session_state.is_recording = True
                start_voice_recording()
                st.rerun()
        else:
            if st.button("⏹️ Stop Recording", use_container_width=True, type="secondary"):
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
                st.rerun()
    
    with col2:
        # Status indicator
        if st.session_state.is_recording:
            st.success("🔴 RECORDING")
        else:
            st.info("⚪ Ready to record")
    
    # Live transcription display
    if st.session_state.is_recording or st.session_state.current_partial:
        st.subheader("🎯 Live Transcription")
        if st.session_state.current_partial:
            st.write(f"**You're saying:** {st.session_state.current_partial}")
        else:
            st.write("*Listening for your voice...*")
    
    # Text input as alternative
    st.header("💬 Text Input (Alternative)")
    with st.form("text_form", clear_on_submit=True):
        user_text = st.text_input("Or type your message:", placeholder="Type here if you prefer text...")
        text_submit = st.form_submit_button("Send Text")
        
        if text_submit and user_text.strip():
            # Add user message
            st.session_state.messages.append({"role": "user", "content": user_text.strip()})
            
            # Get agent response
            with st.spinner("🤔 Thinking..."):
                response = get_agent_response(user_text.strip())
                st.session_state.messages.append({"role": "assistant", "content": response})
            
            st.rerun()
    
    # Conversation history
    if st.session_state.messages:
        st.header("💭 Conversation")
        
        for i, message in enumerate(st.session_state.messages):
            if message["role"] == "user":
                with st.chat_message("user", avatar="🧑"):
                    st.write(message["content"])
            
            elif message["role"] == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(message["content"])
                    
                    # Audio playback button
                    if st.button(f"🔊 Play Audio", key=f"audio_{i}"):
                        play_audio_async(message["content"])
                        st.success("🎵 Playing...")
            
            elif message["role"] == "system":
                st.error(message["content"])
        
        # Clear conversation
        if st.button("🗑️ Clear History"):
            st.session_state.messages = []
            st.rerun()
    
    else:
        st.info("👋 Welcome! Click 'Start Recording' to begin a voice conversation with your AI agent.")
        
        # Quick start examples
        st.markdown("### 💡 Try saying:")
        examples = [
            "What time is it?",
            "Tell me about yourself",
            "What can you help me with?",
            "Hello, how are you?"
        ]
        
        for example in examples:
            st.markdown(f"- *\"{example}\"*")
    
    # Sidebar
    with st.sidebar:
        st.header("🎤 Voice Agent")
        st.markdown("**User:** Hemanth (AI Engineer)")
        
        st.markdown("---")
        st.header("📊 Status")
        
        if st.session_state.is_recording:
            st.error("🔴 Recording Active")
        else:
            st.success("🟢 Ready")
        
        if st.session_state.messages:
            total_messages = len(st.session_state.messages)
            user_messages = len([m for m in st.session_state.messages if m["role"] == "user"])
            
            st.metric("Total Messages", total_messages)
            st.metric("Your Messages", user_messages)
            st.metric("Agent Responses", total_messages - user_messages)
        
        st.markdown("---")
        st.header("🛠️ Features")
        st.markdown("""
        ✅ **Live Voice Recording**
        - Automatic speech detection
        - Real-time transcription
        - Auto-stop when finished
        
        ✅ **Instant Response**
        - AI agent processing
        - Text-to-speech output
        - Conversation memory
        
        ✅ **Backup Text Input**
        - Type instead of speak
        - Same AI processing
        """)
        
        st.markdown("---")
        st.header("🎯 How to Use")
        st.markdown("""
        1. Click **"Start Recording"**
        2. **Speak naturally**
        3. Wait for **auto-stop**
        4. Get **instant response**
        5. Listen to **audio reply**
        """)
    
    # Auto-refresh when recording
    if st.session_state.is_recording:
        time.sleep(0.5)
        st.rerun()


if __name__ == "__main__":
    main()
