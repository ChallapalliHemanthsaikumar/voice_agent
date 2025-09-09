


import asyncio
from transcribe import MicStream, stream_to_transcribe
from agent import agent

from polly import synthesize_and_play_direct


async def on_parital(text):
    print(f"[you]:  {text}")
    


async def on_final(text):
    result = agent(text)
    print(result)
    
    try:
        # Handle the structured response from the agent
        if hasattr(result, 'message'):
            response_data = result.message
        elif hasattr(result, 'text'):
            response_data = result.text
        elif hasattr(result, 'content'):
            response_data = result.content
        else:
            response_data = str(result)
        
        # Extract text from the nested structure
        if isinstance(response_data, dict):
            if 'content' in response_data and isinstance(response_data['content'], list):
                # Handle structure: {'role': 'assistant', 'content': [{'text': 'actual text'}]}
                response_text = response_data['content'][0]['text']
            elif 'content' in response_data and isinstance(response_data['content'], str):
                # Handle structure: {'role': 'assistant', 'content': 'actual text'}
                response_text = response_data['content']
            elif 'text' in response_data:
                # Handle structure: {'text': 'actual text'}
                response_text = response_data['text']
            else:
                response_text = str(response_data)
        else:
            response_text = str(response_data)
        
        print(f"[agent]: {response_text}")
        # await synthesize_and_play_direct(response_text)
        
    except Exception as e:
        print(f"Error processing agent response: {e}")
        print(f"Response structure: {result}")
    


async def main():
    async with MicStream() as mic:
        await stream_to_transcribe(mic,on_partial=on_parital,on_final=on_final)


if __name__ == "__main__":
    asyncio.run(main())









