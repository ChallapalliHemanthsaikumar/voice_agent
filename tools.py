

from datetime import datetime
from strands import tool 

@tool
def get_time():
    """ Return the current time as HH:MM:SS"""
    return datetime.now().strftime("%H:%M:%S")



