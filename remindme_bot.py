from telegram.ext import Updater, CommandHandler
from telegram.ext import MessageHandler, Filters
from telegram import ReplyKeyboardMarkup, KeyboardButton
from scheduler import Scheduler, Reminder
from xml.dom import minidom
from util import BotState
from logging import handlers
import threading
import datetime
import logging
import time
import requests
import util
import sys
import pickle 
import os

TOKEN_FILE = open('token.txt', 'r')
TIMEZONE_DB_API_KEY_FILE = open('api_key.txt', 'r')

TOKEN = TOKEN_FILE.readline()
TIMEZONE_DB_API_KEY = TIMEZONE_DB_API_KEY_FILE.readline()
TIMEZONE_API_URL = "http://api.timezonedb.com/v2/get-time-zone"

TOKEN_FILE.close()
TIMEZONE_DB_API_KEY_FILE.close()

LOGFILE = 'log'

STATE_DUMP_PATH = 'state/'

class RemindMeBot:
	def __init__(self):
		self.updater = Updater(token = TOKEN)
		self.dispatcher = self.updater.dispatcher

		# Describe the state of the bot for each user
		self.pending_reminder = {}
		self.user_state = {}
		self.user_timezone = {}

		# Setting up loggers
		self.logger = logging.getLogger()
		self.logger.setLevel(logging.INFO)

		ch = logging.StreamHandler()
		ch.setLevel(logging.INFO)
		ch_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		ch.setFormatter(ch_format)
		self.logger.addHandler(ch)

		fh = handlers.RotatingFileHandler(LOGFILE, maxBytes=(1048576*5), backupCount=7)
		fh.setLevel(logging.DEBUG)
		fh_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		fh.setFormatter(fh_format)
		self.logger.addHandler(fh)

		def start(bot, update):
			# /start command
			if update.message.chat_id not in self.user_state:
				self.logger.info("New user added.")
			if update.message.chat_id in self.pending_reminder:
				del self.pending_reminder[update.message.chat_id]

			# Add custom keyboard
			replyKeyboard = ReplyKeyboardMarkup(keyboard = [[KeyboardButton("/create")], [KeyboardButton("/help")], [KeyboardButton("/about")], [KeyboardButton("/cancel")]], resize_keyboard = True)

			bot.send_message(chat_id = update.message.chat_id, text = "Hello there! I am a bot that can message you a reminder at a specified time.\n\n\
				Type /create to create a new reminder.\n\
				Type /help to see this exact message.\n\
				Type /about for the GitHub link.\n\
				Send me a location message to set up a new timezone.",
				reply_markup = replyKeyboard)

			self.user_state[update.message.chat_id] = BotState.DEFAULT

		def create_new_reminder(bot, update):
			# /create command
			chat_id = update.message.chat_id
			if chat_id not in self.user_state:
				start(bot, update)
			if self.user_state[chat_id] == BotState.DEFAULT:
				bot.send_message(chat_id = chat_id, text = "Send me a text message with the text for the reminder.")
				self.user_state[chat_id] = BotState.DESRIPTION

		def add_new_reminder_description(bot, update):
			# waiting for description, must be a text message
			chat_id = update.message.chat_id
			if chat_id not in self.user_state:
				start(bot, update)
			if self.user_state[chat_id] == BotState.DESRIPTION:
				reminder = Reminder(update.message.text, chat_id, -1, -1)
				self.pending_reminder[chat_id] = reminder
				self.user_state[chat_id] = BotState.DATE
				location_status_string = "_There is no local timezone set, so I will be using UTC+0 by default. Send me a location if you want to set a different timezone._"
				if chat_id in self.user_timezone:
					location_status_string = "_Your timezone is set to " + self.user_timezone[chat_id][1] + "._"
				bot.send_message(chat_id = chat_id, text = "When should I remind you?\n\n" + 
					"Type \"in X seconds/minutes/hours/weeks\" or the exact date as \"DD/MM/YYYY HH:mm\"\n\n" + 
					location_status_string, parse_mode = "Markdown")

		def add_new_reminder_date(bot, update):
			# waiting for date
			chat_id = update.message.chat_id
			if update.message.chat_id not in self.user_state:
				start(bot, update)
			if self.user_state[chat_id] == BotState.DATE and chat_id in self.pending_reminder:
				self.pending_reminder[chat_id].created_time = time.time()
				reminder_timestamp = util.get_timestamp_from_message(update.message)

				if reminder_timestamp[0] == -1:
					bot.send_message(chat_id = chat_id, text = "I do not understand this date format, try again.")
				else:
					if update.message.chat_id in self.user_timezone and reminder_timestamp[0] == 1:						
						self.pending_reminder[chat_id].reminder_time = reminder_timestamp[1] - self.user_timezone[chat_id][0]
					else:
						self.pending_reminder[chat_id].reminder_time = reminder_timestamp[1]
					self.logger.info('Adding a new reminder to queue')
					self.scheduler.add_reminder(self.pending_reminder[chat_id])
					del self.pending_reminder[chat_id]
					self.user_state[chat_id] = BotState.DEFAULT
					bot.send_message(chat_id = chat_id, text = "Got it!")
					start(bot, update)

		def cancel(bot, update):
			# /cancel
			if update.message.chat_id in self.pending_reminder:
				del self.pending_reminder[update.message.chat_id]
			self.user_state[update.message.chat_id] = BotState.DEFAULT
			bot.send_message(chat_id = update.message.chat_id, text = "Operation cancelled.")
			start(bot, update)

		def update_user_timezone(bot, update):
			# when a location message is received, get the timezone from it
			chat_id = update.message.chat_id
			try:
				if chat_id not in self.user_state:
					start(bot, update)
				params = {'key': TIMEZONE_DB_API_KEY, 'by': 'position', 'lat': update.message.location.latitude, 'lng': update.message.location.longitude}
				response = requests.get(TIMEZONE_API_URL, params = params)
				xmldoc = minidom.parseString(response.text)
				offset_itemlist = xmldoc.getElementsByTagName('gmtOffset')
				zonename_itemlist = xmldoc.getElementsByTagName('zoneName')
				offset = int(offset_itemlist[0].childNodes[0].data)
				zonename = zonename_itemlist[0].childNodes[0].data
				self.user_timezone[chat_id] = (offset, zonename)
				bot.send_message(chat_id = chat_id, text = "Your timezone has been set to " + zonename + ".")
			except:
				bot.send_message(chat_id = chat_id, text = "Unable to set location, try again later.")

		def help(bot, update):
			# /help command
			bot.send_message(chat_id = update.message.chat_id, text = "Hello there! I am a bot that can message you a reminder at a specified time.\n\n\
				Type /create to create a new reminder.\n\
				Send me a location message to set up a new timezone.\n\
				Type /help to see this exact message.")
			start(bot, update)

		def about(bot, update):
			# /about command
			bot.send_message(chat_id = update.message.chat_id, text = "My source code is available at https://github.com/AndrewLeeQ/remindme_telegram_bot")
			start(bot, update)

		start_handler = CommandHandler('start', start)
		cancel_handler = CommandHandler('cancel', cancel)
		create_new_reminder_handler = CommandHandler('create', create_new_reminder)
		help_handler = CommandHandler('help', help)
		about_handler = CommandHandler('about', about)

		add_new_reminder_description_handler = MessageHandler(Filters.text, add_new_reminder_description)
		add_new_reminder_date_handler = MessageHandler(Filters.text, add_new_reminder_date)
		update_user_timezone_handler = MessageHandler(Filters.location, update_user_timezone)

		self.dispatcher.add_handler(start_handler)
		self.dispatcher.add_handler(cancel_handler)
		self.dispatcher.add_handler(create_new_reminder_handler)
		self.dispatcher.add_handler(add_new_reminder_description_handler, group = 1)
		self.dispatcher.add_handler(add_new_reminder_date_handler, group = 0)
		self.dispatcher.add_handler(update_user_timezone_handler)
		self.dispatcher.add_handler(help_handler)
		self.dispatcher.add_handler(about_handler)

		self.keepAlive()

	def __keepAliveThread(self):
		# need this to mainain the HTTP connection, otherwise it breaks after 
		# a long period of idleness :/
		while True:
			self.logger.debug('keeping the connection alive')
			self.updater.bot.getMe()
			time.sleep(60)
			
	def keepAlive(self):
		t = threading.Thread(target = self.__keepAliveThread)
		t.daemon = True
		t.start()

	def start(self):
		self.read_bot_state()
		self.updater.start_polling(poll_interval = 1.0, timeout = 20)

	def stop(self):
		self.updater.stop()
		self.dump_bot_state()

	def set_scheduler(self, scheduler):
		self.scheduler = scheduler

	def dump_bot_state(self):	
		# preserve bot state
		try:	
			if not os.path.isdir(STATE_DUMP_PATH):
				os.mkdir(STATE_DUMP_PATH)
			pickle.dump(self.user_state, open(STATE_DUMP_PATH + 'user_state.p', 'wb'))
			pickle.dump(self.user_timezone, open(STATE_DUMP_PATH + 'user_timezone.p', 'wb'))
			pickle.dump(self.pending_reminder, open(STATE_DUMP_PATH + 'pending_reminder.p', 'wb'))
			self.logger.info('successfully dumped bot state')
		except:
			self.logger.info('unable to dump bot state')

	def read_bot_state(self):
		# read saved bot state if it exists
		try:
			self.user_state = pickle.load(open(STATE_DUMP_PATH + 'user_state.p', 'rb'))
			self.user_timezone = pickle.load(open(STATE_DUMP_PATH + 'user_timezone.p', 'rb'))
			self.pending_reminder = pickle.load(open(STATE_DUMP_PATH + 'pending_reminder.p', 'rb'))
			self.logger.info('successfully loaded saved state')
		except:
			self.logger.info('unable to load saved state, starting with default')

def main():	
	bot = RemindMeBot()
	bot.start()

	scheduler = Scheduler(bot.updater.bot.send_message)
	scheduler.start()

	bot.set_scheduler(scheduler)
	try:
		print("Type \"quit\" to finish.")
		while input() != "quit":
			pass
	finally:
		scheduler.stop()
		bot.stop()

if __name__=='__main__':
    main()



