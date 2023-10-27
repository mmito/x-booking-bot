import os
from signal import SIGTERM 
import threading
import pytz
import functools
import inspect
import configparser
import json

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler
from datetime import datetime
from utils.booker import Booker, parse_booking_activity, parse_booking_day, parse_booking_times

config = configparser.ConfigParser()
config.read('config.cfg')
START_TIME = datetime.now(tz=pytz.UTC)
config['APP_CONFIG']['START_TIME'] = str(START_TIME)
with open('config.cfg', 'w') as f:
    config.write(f)

activities = {}
with open('activities.json', 'r', newline='') as inputdata:
            activities = json.load(inputdata)

CREDENTIALS_ASK, USERNAME_SET, PASSWORD_SET, BOOKING_ASK, TIME_SET, DAY_SET, ACTIVITY_SET, START_ASK, CHECK_BOOKINGS, ACTION_ASK, ACTIVITY_CATEGORY_SET = range(11)
checkmark = '✅'
crossmark = '❌'

login_reply_keyboard = [['Username','Password'],[crossmark, checkmark]]
login_reply_placeholder = "Make a choice."
login_reply_text = "What do you want to set?"

book_reply_keyboard = [['Time(s)','Day'],['Activity', crossmark, checkmark]]
book_reply_placeholder = "Make a choice."
book_reply_text = "What do you want to book?"

start_reply_keyboard = [['Login 🔒']]
start_reply_placeholder = "Login!"
start_reply_text = "Login?"

action_reply_keyboard = [['Book 📗', 'Check 🔎']]
action_reply_placeholder = "Book or check bookings."
action_reply_text = "What would you like to do?"

activity_reply_keyboard = []
options_per_row = 3
keys = [key for key in activities]
for index in range(len(keys) // options_per_row + 1):
    if index*options_per_row+options_per_row > len(keys):
        activity_reply_keyboard.append(keys[index*options_per_row:] + [crossmark])
    else:
        activity_reply_keyboard.append(keys[index*options_per_row:index*options_per_row+options_per_row])

activity_reply_placeholder = "Make a choice."
activity_reply_text = "What do you want to book today?"

def decorate_class(cls): 
    for name, method in inspect.getmembers(cls, inspect.iscoroutinefunction): 
        setattr(cls, name, check_time_sent(method)) 
    return cls 

def check_time_sent(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        update : Update = args[0]
        context : ContextTypes = args[1]
        if START_TIME > update.message.date.replace(tzinfo=pytz.UTC):
            if 'unprocessed_messages' in context.user_data:
                return
            
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Messages sent when the bot was down. Sorry!\nBot is now back up :)")
            context.user_data['unprocessed_messages'] = True
            return
            
        return await func(*args, **kwargs)
    return wrapper

@decorate_class
class Handlers:

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            return ConversationHandler.END
        
        if 'processes' in context.user_data:
            for process in context.user_data['processes']:
                process.terminate()
        
        for message_id in context.user_data['messages-to-delete']:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        context.user_data['messages-to-delete'] = []

        await context.bot.send_message(chat_id=update.effective_chat.id, text="Back to the homepage!")
        return ConversationHandler.END

    async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
            login_reply_keyboard, one_time_keyboard=True, input_field_placeholder=login_reply_placeholder, resize_keyboard=True
        ),)
        return CREDENTIALS_ASK
    
    async def credentials_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        print(update.message.text)

        if update.message.text == 'Username':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, enter your username.")
            return USERNAME_SET
        elif update.message.text == 'Password':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, enter your password.")
            return PASSWORD_SET
        elif update.message.text == checkmark:
            for message_id in context.user_data['messages-to-delete']:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            context.user_data['messages-to-delete'] = []

            context.user_data['booker'].login()

            if not context.user_data['booker'].get_login_status():
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Login attempt failed. Try again!")
                await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
                    login_reply_keyboard, one_time_keyboard=True, input_field_placeholder=login_reply_placeholder, resize_keyboard=True
                ),)
                return CREDENTIALS_ASK

            await context.bot.send_message(chat_id=update.effective_chat.id, text="You are now logged in! Use /book to book a slot in one or multiple timeslots or /check to check your current bookings.")
            await update.message.reply_text(action_reply_text, reply_markup=ReplyKeyboardMarkup(
                action_reply_keyboard, one_time_keyboard=True, input_field_placeholder=action_reply_placeholder, resize_keyboard=True
                ),)
            return ACTION_ASK
            

        elif update.message.text == crossmark:
            for message_id in context.user_data['messages-to-delete']:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            context.user_data['messages-to-delete'] = []

            context.user_data['booker'].clear_credentials()
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Login attempt canceled.")
            await update.message.reply_text(start_reply_text, reply_markup=ReplyKeyboardMarkup(
                start_reply_keyboard, one_time_keyboard=True, input_field_placeholder=start_reply_placeholder, resize_keyboard=True
            ),)
            return START_ASK
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, use the following format: /login <username> <password>")
            return ConversationHandler.END

    async def username_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        context.user_data['booker'].set_username(update.message.text)
        context.user_data['messages-to-delete'].append(update.message.message_id)

        await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
            login_reply_keyboard, one_time_keyboard=True, input_field_placeholder=login_reply_placeholder, resize_keyboard=True
        ),)
        return CREDENTIALS_ASK
    
    async def password_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        context.user_data['booker'].set_password(update.message.text)
        context.user_data['messages-to-delete'].append(update.message.message_id)

        await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
            login_reply_keyboard, one_time_keyboard=True, input_field_placeholder=login_reply_placeholder, resize_keyboard=True
        ),)
        return CREDENTIALS_ASK
    
    async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        # context.user_data['booker'].select_hours([])
        context.user_data['booker'].select_day()
        context.user_data['booker'].select_activity() 

        await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
        ),)
        return BOOKING_ASK

    async def booking_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        print(update.message.text)

        if update.message.text == 'Time(s)':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, enter the timeslots you want to book (e.g. 10-12 14-16).")
            return TIME_SET
        
        elif update.message.text == 'Day':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, enter the day of the month you want to book (e.g. 1).")
            return DAY_SET
        
        elif update.message.text == 'Activity':
            # await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, enter the activity you want to book (e.g. 'Fitness').")

            await update.message.reply_text(activity_reply_text, reply_markup=ReplyKeyboardMarkup(
            activity_reply_keyboard, one_time_keyboard=True, input_field_placeholder=activity_reply_placeholder, resize_keyboard=True
            ),)
            
            return ACTIVITY_CATEGORY_SET
            # return ACTIVITY_SET
        
        elif update.message.text == checkmark:
            for message_id in context.user_data['messages-to-delete']:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            context.user_data['messages-to-delete'] = []

            if not context.user_data['booker'].get_slots_to_book():
                await context.bot.send_message(chat_id=update.effective_chat.id, text="No valid hours to book. Please, retry.")
                return
            
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Booking for the following hours: " + str(context.user_data['booker'].get_slots_to_book()).strip("[]") + f" on {context.user_data['booker'].get_selected_day()}/{datetime.now().month}...")

            print(context.user_data['booker'].get_slots_to_book())
            print(context.user_data['booker'].get_selected_day())
            print(context.user_data['booker'].get_selected_activity())

            process_return = []
            def mp_book(update: Update, context: ContextTypes.DEFAULT_TYPE, return_list : list):
                result = context.user_data['booker'].attempt_booking()
                return_list.append(result)

            proc = threading.Thread(target=mp_book,args=(update,context, process_return))
            context.user_data['processes'].append(proc)
            proc.start()

            def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
                """Remove job with given name. Returns whether job was removed."""
                current_jobs = context.job_queue.get_jobs_by_name(name)
                if not current_jobs:
                    return False
                for job in current_jobs:
                    job.schedule_removal()
                return True

            async def control_booking_status(context: ContextTypes.DEFAULT_TYPE):
                update, context_book, return_list = context.job.data
                if 'booker' not in context_book.user_data:
                    return ConversationHandler.END
                if 'processes' not in context_book.user_data:
                    return ConversationHandler.END
                
                for process in context_book.user_data['processes']:
                    if process.is_alive():
                        print("Process still alive")
                        # await context.bot.send_message(chat_id=update.effective_chat.id, text="Booking in progress...")
                        return
                    else:
                        print("Process finished!")
                        booked, booked_time = return_list[0]
                        print(booked, booked_time)
                        if booked:
                            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Successfully booked at {booked_time}:00 on {context_book.user_data['booker'].get_selected_day()}/{datetime.now().month}!")
                            # await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Successfully booked at {booked_time}:00!")
                            # await context.bot.send_message(chat_id=update.effective_chat.id, text=f"on {context_book.user_data['booker'].get_selected_day()}/{datetime.now().month}!")
                        else:
                            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not book for your selected timeslots.")
                        remove_job_if_exists(str(update.effective_message.chat_id), context)
                        context_book.user_data['processes'].remove(process)

                # await context.bot.send_message(chat_id=update.effective_chat.id, text="Booking completed!")
                # return ConversationHandler.END

            job_args = [update, context, process_return]
            context.job_queue.run_repeating(control_booking_status, interval=2, chat_id=update.effective_message.chat_id, name=str(update.effective_message.chat_id), data=job_args)
            # booked, booked_time = process_return[0]

            
            await update.message.reply_text(action_reply_text, reply_markup=ReplyKeyboardMarkup(
                action_reply_keyboard, one_time_keyboard=True, input_field_placeholder=action_reply_placeholder, resize_keyboard=True
            ),)
            return ACTION_ASK

        elif update.message.text == crossmark:
            for message_id in context.user_data['messages-to-delete']:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            context.user_data['messages-to-delete'] = []

            await update.message.reply_text(action_reply_text, reply_markup=ReplyKeyboardMarkup(
                action_reply_keyboard, one_time_keyboard=True, input_field_placeholder=action_reply_placeholder, resize_keyboard=True
            ),)
            return ACTION_ASK
        
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, use the following format: /login <username> <password>")
            return ConversationHandler.END
        
    # WRONG NAME        
    async def activity_category_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
        if crossmark in update.message.text:
            await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
            ),)
            return BOOKING_ASK

        # DO STUFF
        options = activities[update.message.text]
        activity_set_reply_keyboard = []
        options_per_row = 3
        for index in range(len(options) // options_per_row + 1):
            if index*options_per_row+options_per_row > len(options):
                activity_set_reply_keyboard.append(options[index*options_per_row:] + [crossmark])
            else:
                activity_set_reply_keyboard.append(options[index*options_per_row:index*options_per_row+options_per_row])
        activity_set_reply_placeholder = "Make a choice."
        activity_set_reply_text = "What do you want to book today?"


        await update.message.reply_text(activity_set_reply_text, reply_markup=ReplyKeyboardMarkup(
        activity_set_reply_keyboard, one_time_keyboard=True, input_field_placeholder=activity_set_reply_placeholder, resize_keyboard=True
        ),)

        return ACTIVITY_SET

    async def time_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        hours_to_book = parse_booking_times(update.message.text.split())
        context.user_data['booker'].select_hours(hours_to_book)

        await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
        ),)
        return BOOKING_ASK
    
    async def day_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        day_to_book = parse_booking_day(update.message.text.split())
        context.user_data['booker'].select_day(day_to_book)

        await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
        ),)
        return BOOKING_ASK
    
    async def activity_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot.")
            return ConversationHandler.END
        
        activity = parse_booking_activity(update.message.text)
        print(activity)
        context.user_data['booker'].select_activity(activity)

        await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
        ),)
        return BOOKING_ASK

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot is already set up! Use /login to log in before booking timeslots.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Initializing browser...")
            context.user_data['booker'] = Booker()
            context.user_data['processes'] = []
            context.user_data['messages-to-delete'] = []
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Browser is now set up! Use /login to log in before booking timeslots.")
        
        await update.message.reply_text(start_reply_text, reply_markup=ReplyKeyboardMarkup(
            start_reply_keyboard, one_time_keyboard=True, input_field_placeholder=start_reply_placeholder, resize_keyboard=True
        ),)
        return START_ASK
    
    async def start_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
        print(update.message.text)

        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot and /login with your credentials.")
            return

        if update.message.text == start_reply_keyboard[0][0]:
            await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
            login_reply_keyboard, one_time_keyboard=True, input_field_placeholder=login_reply_placeholder, resize_keyboard=True
            ),)
            return CREDENTIALS_ASK
        
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, /login to begin!")
            return ConversationHandler.END

    async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'booker' not in context.user_data or not context.user_data['booker'].get_login_status():
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot and /login with your credentials.")
            return ConversationHandler.END
        booked_slots = context.user_data['booker'].check_bookings()
        if not booked_slots:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No booked slots.")
        else:
            print_slots = ''
            for index, slot in enumerate(booked_slots):
                print_slots += "\n" + f'{index+1}.   ' + slot[0] + ', ' + slot[1]
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Booked slots:" + print_slots)

        await update.message.reply_text(login_reply_text, reply_markup=ReplyKeyboardMarkup(
        book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
        ),)
        return ACTION_ASK
        
    async def action_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(update.message.text)

        if 'booker' not in context.user_data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, first make sure to /start the bot and /login with your credentials.")
            return

        if update.message.text == action_reply_keyboard[0][0]:
            await update.message.reply_text(book_reply_text, reply_markup=ReplyKeyboardMarkup(
            book_reply_keyboard, one_time_keyboard=True, input_field_placeholder=book_reply_placeholder, resize_keyboard=True
            ),)
            return BOOKING_ASK
        
        elif update.message.text == action_reply_keyboard[0][1]:
            booked_slots = context.user_data['booker'].check_bookings()
            if not booked_slots:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="No booked slots.")
            else:
                print_slots = ''
                for index, slot in enumerate(booked_slots):
                    print_slots += "\n" + f'{index+1}.   ' + slot[0] + ', ' + slot[1]
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Booked slots:" + print_slots)

            await update.message.reply_text(action_reply_text, reply_markup=ReplyKeyboardMarkup(
            action_reply_keyboard, one_time_keyboard=True, input_field_placeholder=action_reply_placeholder, resize_keyboard=True
            ),)
            return ACTION_ASK
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Please, /login to begin!")
            return ConversationHandler.END
    
    async def abort_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
        for process in context.user_data['processes']:
            context.user_data['booker'].set_kill(True)
            print("Killing process...")

    # TODO: Not working!
    async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # for all users in current chat log
        for user in context.bot_data:
            print(user)
        return ConversationHandler.END