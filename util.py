import datetime
import time
import calendar
from enum import Enum

class BotState(Enum):
	DEFAULT = 0
	DESRIPTION = 1
	DATE = 2
	
WORDS_TO_SECONDS = {'second': 1, 
					'minute': 60,
					'hour': 3600,
					'day': 3600*24,
					'week': 3600*24*7,
					'seconds': 1, 
					'minutes': 60,
					'hours': 3600,
					'days': 3600*24,
					'weeks': 3600*24*7}

def get_timestamp_from_message(message):
	text = message.text.lower()
	id = message.chat_id
	tokens = text.split()

	if len(tokens) == 3 and tokens[0] == 'in':
		for d in tokens[1]:
			if not d.isdigit():
				return (-1, -1)
		value = int(tokens[1])
		if tokens[2] in WORDS_TO_SECONDS:
			return (0, value * WORDS_TO_SECONDS[tokens[2]] + time.time())

	try:
		d = datetime.datetime.strptime(text, '%d/%m/%Y %H:%M')
		return (1, calendar.timegm(d.utctimetuple()))
	except ValueError:
		return (-1, -1)

	return (-1, -1)



