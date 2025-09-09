import streamlit as st
import asyncio
import threading
from agent import agent
from polly import synthesize_and_play_direct
from transcribe import MicStream, stream_to_transcribe
import time
import queue


# Configure Streamlit page
st.set_page_config(
    page_title="Voice Agent Chat",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'current_partial' not in st.session_state:
    st.session_state.current_partial = ""
if 'result_queue' not in st.session_state:
    st.session_state.result_queue = queue.Queue()
if 'enable_tts' not in st.session_state:
    st.session_state.enable_tts = True
if 'auto_play_audio' not in st.session_state:
    st.session_state.auto_play_audio = False


# Custom CSS for ChatGPT-like styling
st.markdown("""
<style>
/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Main container styling */
.main > div {
    padding-top: 1rem;
    max-width: 800px;
    margin: 0 auto;
}

/* Chat message styling */
.stChatMessage {
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 10px;
}

/* Input area styling */
.input-container {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 1rem;
    border-top: 1px solid #e0e0e0;
    z-index: 1000;
}

/* Chat container */
.chat-container {
    padding-bottom: 120px;
    min-height: 60vh;
}

/* Recording indicator */
.recording-status {
    background: #ffebee;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    margin: 0.5rem 0;
    border-left: 4px solid #f44336;
}
</style>
""", unsafe_allow_html=True)


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
    if not st.session_state.enable_tts:
        return
        
    def play_audio():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(synthesize_and_play_direct(text))
        except Exception as e:
            print(f"TTS error: {e}")
    
    thread = threading.Thread(target=play_audio, daemon=True)
    thread.start()


def start_voice_recording(result_queue):
    """Start voice recording with live transcription"""
    def record_voice():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def on_partial(text):
                """Handle partial transcription results"""
                result_queue.put({"type": "partial", "text": text})
            
            async def on_final(text):
                """Handle final transcription"""
                if text.strip():
                    result_queue.put({"type": "final", "text": text.strip()})
                result_queue.put({"type": "done"})
            
            async def record_with_transcribe():
                """Main recording function"""
                async with MicStream() as mic:
                    await stream_to_transcribe(mic, on_partial=on_partial, on_final=on_final)
            
            # Run the recording with timeout
            loop.run_until_complete(asyncio.wait_for(record_with_transcribe(), timeout=30.0))
            
        except asyncio.TimeoutError:
            result_queue.put({"type": "timeout"})
        except Exception as e:
            result_queue.put({"type": "error", "message": str(e)})
    
    # Start recording thread
    thread = threading.Thread(target=record_voice, daemon=True)
    thread.start()
    return thread


def main():
    # Header with settings
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title("🤖 Voice Agent")
    
    with col2:
        st.session_state.enable_tts = st.checkbox("🔊 Audio", value=st.session_state.enable_tts)
    
    with col3:
        if st.button("🗑️ Clear"):
            st.session_state.messages = []
            st.rerun()
    
    # Check for recording results
    try:
        while not st.session_state.result_queue.empty():
            result = st.session_state.result_queue.get_nowait()
            
            if result["type"] == "partial":
                st.session_state.current_partial = result["text"]
            
            elif result["type"] == "final":
                user_text = result["text"]
                st.session_state.messages.append({"role": "user", "content": user_text})
                
                # Get agent response
                agent_response = get_agent_response(user_text)
                st.session_state.messages.append({"role": "assistant", "content": agent_response})
                
                # Auto-play response if enabled
                if st.session_state.auto_play_audio and st.session_state.enable_tts:
                    play_audio_async(agent_response)
                
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
            
            elif result["type"] == "done":
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
            
            elif result["type"] == "timeout":
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
                st.warning("⏰ Recording timed out")
            
            elif result["type"] == "error":
                st.session_state.is_recording = False
                st.session_state.current_partial = ""
                st.error(f"❌ Recording error: {result['message']}")
                
    except queue.Empty:
        pass
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        if st.session_state.messages:
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                
                elif message["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.write(message["content"])
                        # Small inline audio button
                        if st.session_state.enable_tts:
                            if st.button("🔊", key=f"play_{i}", help="Play audio"):
                                play_audio_async(message["content"])
        else:
            st.markdown("### 👋 Hello! I'm your AI voice agent.")
            st.markdown("You can interact with me using:")
            st.markdown("- **Voice**: Click the microphone button and speak")
            st.markdown("- **Text**: Type your message below")
            
            st.markdown("**Try asking:**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("What time is it?", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "What time is it?"})
                    response = get_agent_response("What time is it?")
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()
            
            with col2:
                if st.button("Tell me about yourself", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "Tell me about yourself"})
                    response = get_agent_response("Tell me about yourself")
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()
    
    # Recording status display
    if st.session_state.is_recording:
        st.markdown('<div class="recording-status">🔴 <strong>Recording...</strong> Speak now!</div>', 
                   unsafe_allow_html=True)
        
        if st.session_state.current_partial:
            st.info(f"**Transcribing:** {st.session_state.current_partial}")
        
        # Stop button
        if st.button("⏹️ Stop Recording", type="secondary"):
            st.session_state.is_recording = False
            st.session_state.current_partial = ""
            st.rerun()
        
        # Auto-refresh
        time.sleep(0.5)
        st.rerun()
    
    # Bottom input area (ChatGPT-like)
    st.markdown("---")
    
    # Input form
    with st.form("chat_input", clear_on_submit=True):
        col1, col2, col3 = st.columns([6, 1, 1])
        
        with col1:
            user_input = st.text_input(
                "Message",
                placeholder="Type your message here... or use voice input",
                label_visibility="collapsed",
                key="user_message_input"
            )
        
        with col2:
            if not st.session_state.is_recording:
                voice_btn = st.form_submit_button("🎤", help="Voice input")
            else:
                voice_btn = False
        
        with col3:
            send_btn = st.form_submit_button("Send", type="primary")
        
        # Process inputs
        if send_btn and user_input.strip():
            # Add user message
            st.session_state.messages.append({"role": "user", "content": user_input.strip()})
            
            # Get agent response
            with st.spinner("🤔"):
                response = get_agent_response(user_input.strip())
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Auto-play if enabled
                if st.session_state.auto_play_audio and st.session_state.enable_tts:
                    play_audio_async(response)
            
            st.rerun()
        
        elif voice_btn:
            st.session_state.is_recording = True
            st.session_state.current_partial = ""
            # Clear queue
            while not st.session_state.result_queue.empty():
                st.session_state.result_queue.get_nowait()
            # Start recording
            start_voice_recording(st.session_state.result_queue)
            st.rerun()
    
    # Settings in sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.session_state.auto_play_audio = st.checkbox(
            "🔄 Auto-play responses", 
            value=st.session_state.auto_play_audio,
            help="Automatically play audio when agent responds"
        )
        
        st.markdown("---")
        st.header("📊 Stats")
        if st.session_state.messages:
            total = len(st.session_state.messages)
            user_msgs = len([m for m in st.session_state.messages if m["role"] == "user"])
            
            st.metric("Total Messages", total)
            st.metric("Your Messages", user_msgs)
            st.metric("Agent Responses", total - user_msgs)
        
        st.markdown("---")
        st.header("💡 Tips")
        st.markdown("""
        - **Voice**: Click 🎤 and speak naturally
        - **Text**: Type and press Send
        - **Audio**: Toggle 🔊 to enable/disable TTS
        - **Clear**: Remove all conversation history
        """)


if __name__ == "__main__":
    main()
