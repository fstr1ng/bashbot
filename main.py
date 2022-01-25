import logging

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, sessionmaker

from telegram.ext import Updater, CommandHandler

### В начале создаем словарь-конфиг для хранения настроек бота.
### Функция get_token() читает файл и возвращает его содержимое (в файле одна строка с токеном)
### Это нужно чтобы не держать токен в коде, а файл токена можно написать в .gitignore чтобы не пушить в репу.

def get_token():
    with open('./config/token') as token_file:
        return token_file.read().strip()

config = {
        'db_random_buffer': 15,
        'db_echo': False,
        'db_connection_string': 'sqlite:///quotes.db',
        'telegram_token': get_token()
        }

### Далее - работа с БД. Создаем объекты engine и session - они нужны для подключения к базе.
### Также создается класс Base (это базовый класс SQLAlchemy)
### А затем создаем свой класс Quote, наследуя его от Base. В классе Quote мы указываем имя таблицы и имена ее столбцов. Они станут атрибутами объектов класса Quote.
### Иными словами: это нужно для преобразования SQL-запросов в объекты, с которыми мы работаем в питоне.
### Это называется ORM, то есть связь объектно-ориентированного кода с SQL-базами. Получается примерно такая схема:
###
###      | среда     | способ работы с данными | единица данных
###      |___________|_________________________|________________________|
###      | питон-код | методы объекта session  | объекты класса Quote   |
### ORM: -----↕-------------------↕----------------------↕--------------| <- SQL Alchemy связывает эти слои
###      | SQL-база  | SQL-запросы к базе      | строки в таблице quote |

engine = create_engine(config['db_connection_string'], echo=config['db_echo']) # Создаем SQLite3-движок (что-то типа клиента)
Session = sessionmaker()
Session.configure(bind=engine)
session = Session() # Создаем сессию (т.е. покдлючаемся клиентом). Через session будем слать запросы в базу.

Base = declarative_base()
class Quote(Base):
    __tablename__ = 'quotes'
    quote_number = Column(Integer, primary_key=True)
    date = Column(String)
    rating = Column(Integer)
    text = Column(String)
    def __repr__(self):
        return f'#{self.quote_number} {self.date}\n+{self.rating}\n\n{self.text}'

# Вот это особая питон-магия. Генератор - это функция, способная хранить состояние.
# Каждый раз, когда пользователь запрашивает цитату, генератор пытается (try) достать из своего буффера (yield quotes.pop()) объект-цитату (Quote)
# Если выскакивает исключение (except), то запрашивается новая пачка цитат, а затем по бесконечному циклу (while: True) генератор достает из пополненной пачки очередную цитату.

def random_quote_generator(buffer=config['db_random_buffer']):
    while True:
        try:
            logging.info(f"Quotes in cache left: {len(quotes)}")
            yield quotes.pop()
        except:
            logging.info("Getting random quotes from DB")
            quotes = session.query(Quote).order_by(func.random()).limit(buffer).all() # Здесь совершается запрос в базу
            # в этом месте в переменную quotes записывается список объектов [Quote, Quote, Quote, ... ]
            # Каждый объект - это случайная строка из таблицы
            # В атрибутах объекта - значения столбцов из таблицы
            # Quote: {
            #        'quote_number' : 12345,
            #        'date'         : '23.10.2015 9:45',
            #        'rating'       : 123,
            #        'text'         : 'текст цитаты'
            # }

# Создаем генератор
random_quote = random_quote_generator()

##
## Следующая часть относится к телеграм боту.
##

# udater - это объект, который постоянно опрашивает API телеграма на предмет обновлений (т.е. сообщения от собеседников бота)
updater = Updater(token=config['telegram_token'], use_context=True)

# Это стандартный модуль питона для красивого логирования
# Лог будет писаться в stdout, то есть в вывод консоли при запуске скрипта.
# Если обернуть скрипт в systemd-сервис, то лог будет писаться в journald
logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

# Здесь определяются две функции, которые соответствуют командам /start и /quote
# У функций есть два параметра - update и context. Когда пользователь пишет что-то боту, то внутри функции эти объекты содержат сообщение юзера и инфу о чате с ним.

# Функция команды /start
def start(update, context):
    # Пишем в лог, что в чате {effective_chat.id} выполнили команду /start
    logging.info(f"/start command in {update.effective_chat.id}")
    # Посылаем в чат ответное сообщение
    context.bot.send_message(chat_id=update.effective_chat.id, text="Бошорг-бот. Введите /quote для случайной цитаты из лучших.")
# Этот объект-хендлер нуженб чтобы добавить функцию в главный телеграм-бот-объект updater
start_handler = CommandHandler('start', start)

# Функция команды /quote
def quote(update, context):
    logging.info(f"/quote command in {update.effective_chat.id}")
    # Получаем из генератора случайную цитату.
    # Поскольку генератор на весь скрипт один, то буфер цитат общий для всех пользователей.
    quote = next(random_quote)
    # Посылаем в чат цитату
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"{str(quote)}\n\n/quote")
quote_handler = CommandHandler('quote', quote)

# Добавляем в апдейтер хендлеры
updater.dispatcher.add_handler(start_handler)
updater.dispatcher.add_handler(quote_handler)

# Запускаем бота. С этого момента он начинает опрос телеграм-серверов, пока не завершить его по CTRL-C
updater.start_polling()

