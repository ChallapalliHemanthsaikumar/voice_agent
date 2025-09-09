
from config import bedrock_model
from tools import get_time



from strands import Agent 


agent = Agent(
    tools=[get_time],
    system_prompt=""" User is Hemanth he is AI Engineer """
)


# # Process user input
# result = agent("Calculate 25 * 48")

# print(result)