import threading 
import time
import datetime
import logging 
import pickle
import os

UPDATE_TIME = 1 # update every UPDATE_TIME seconds
STATE_DUMP_PATH = 'state/'

class Reminder:
	def __init__(self, message_text, chat_id, created_time, reminder_time):
		self.message_text = message_text
		self.chat_id = chat_id
		self.reminder_time = reminder_time
		self.created_time = created_time

	def __lt__(self, other):
		return self.reminder_time < other.reminder_time

class Scheduler:
	def __init__(self, callback):
		self.scheduler_thread = SchedulerThread(callback)

	def add_reminder(self, reminder):
		self.scheduler_thread.queue.append(reminder)
		self.scheduler_thread.queue = sorted(self.scheduler_thread.queue)

	def stop(self):
		self.scheduler_thread.exit_flag = 1
		self.dump_scheduler_state()

	def start(self):
		self.scheduler_thread.start()
		self.read_scheduler_state()

	def dump_scheduler_state(self):
		try:
			if not os.path.isdir(STATE_DUMP_PATH):
				os.mkdir(STATE_DUMP_PATH)
			pickle.dump(self.scheduler_thread.queue, open(STATE_DUMP_PATH + 'scheduler_queue.p', 'wb'))
			logging.getLogger().info('successfully dumped schedule queue')
		except:
			logging.getLogger().info('unable to dump schedule queue')

	def read_scheduler_state(self):
		try: 			
			self.scheduler_thread.queue = pickle.load(open(STATE_DUMP_PATH + 'scheduler_queue.p', 'rb'))
			logging.getLogger().info('successfully loaded schedule queue')
		except:
			logging.getLogger().info('unable to load schedule queue')

class SchedulerThread(threading.Thread):
	def __init__(self, callback):

		logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		                     level=logging.DEBUG)

		self.logger = logging.getLogger()
		self.logger.setLevel(logging.DEBUG)

		threading.Thread.__init__(self)
		self.queue = []
		self.exit_flag = 0
		self.callback = callback

	def run(self):
		while True:
			if self.exit_flag == 1:
				break
			while len(self.queue) != 0 and self.queue[0].reminder_time <= time.time():
				self.callback(chat_id = self.queue[0].chat_id, text = self.queue[0].message_text)
				self.logger.info('Reminder sent.')
				self.queue = self.queue[1:]
			time.sleep(UPDATE_TIME)
