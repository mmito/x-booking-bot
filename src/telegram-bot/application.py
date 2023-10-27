import logging
import configparser

from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler
from handlers import Handlers
from handlers import CREDENTIALS_ASK, USERNAME_SET, PASSWORD_SET, BOOKING_ASK, TIME_SET, DAY_SET, ACTIVITY_SET, START_ASK, CHECK_BOOKINGS, ACTION_ASK, ACTIVITY_CATEGORY_SET, checkmark, crossmark


# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

CHECK_STATES = {
    CHECK_BOOKINGS: [MessageHandler(filters.Regex(f'check'), Handlers.check)],
    ACTION_ASK: [MessageHandler(filters.Regex(f"^(Book 📗|Check 🔎)$"), Handlers.action_ask)],
}

BOOKING_STATES = CHECK_STATES | {
    BOOKING_ASK: [MessageHandler(filters.Regex(f"^(Time\(s\)|Day|Activity|{checkmark}|{crossmark})$"), Handlers.booking_ask)],
    TIME_SET: [MessageHandler(filters.TEXT, Handlers.time_set)],
    DAY_SET: [MessageHandler(filters.TEXT, Handlers.day_set)],
    ACTIVITY_SET: [MessageHandler(filters.TEXT, Handlers.activity_set)],
    ACTIVITY_CATEGORY_SET: [MessageHandler(filters.TEXT, Handlers.activity_category_set)],
}
LOGIN_STATES = BOOKING_STATES | CHECK_STATES | {
    CREDENTIALS_ASK: [MessageHandler(filters.Regex(f"^(Username|Password|{checkmark}|{crossmark})$"), Handlers.credentials_ask)],
    USERNAME_SET: [MessageHandler(filters.TEXT, Handlers.username_set)],
    PASSWORD_SET: [MessageHandler(filters.TEXT, Handlers.password_set)],
}
START_STATES = LOGIN_STATES | BOOKING_STATES | CHECK_STATES | {
    START_ASK: [MessageHandler(filters.Regex(f"^(Login 🔒)$"), Handlers.start_ask)]
}

STATES = START_STATES | LOGIN_STATES | BOOKING_STATES | CHECK_STATES


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.cfg')
    application = ApplicationBuilder().token(config['APP_CONFIG']['TOKEN']).post_stop(Handlers.stop).build()

    # start_handler = CommandHandler('start', Handlers.start)
    start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', Handlers.start)],
        states=STATES,
        fallbacks=[CommandHandler("cancel", Handlers.cancel)],
    )
    application.add_handler(start_handler)

    # login_handler = CommandHandler('login', Handlers.login)
    login_handler = ConversationHandler(
        entry_points=[CommandHandler('login', Handlers.login)],
        states=STATES,
        fallbacks=[CommandHandler("cancel", Handlers.cancel)],
    )
    application.add_handler(login_handler)

    # book_handler = CommandHandler('book', Handlers.book)
    book_handler = ConversationHandler(
        entry_points=[CommandHandler('book', Handlers.book)],
        states=STATES,
        fallbacks=[CommandHandler("cancel", Handlers.cancel)],
    )
    application.add_handler(book_handler)


    # check_handler = CommandHandler('check', Handlers.check)
    check_handler = ConversationHandler(
        entry_points=[CommandHandler('check', Handlers.check)],
        states=STATES,
        fallbacks=[CommandHandler("cancel", Handlers.cancel)],
    )
    application.add_handler(check_handler)

    abort_handler = CommandHandler('abort', Handlers.abort_booking)
    application.add_handler(abort_handler)

    application.run_polling()