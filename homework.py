from http import HTTPStatus

import logging
import os
import requests
import time

from dotenv import load_dotenv
from logging import StreamHandler
from telegram import Bot


load_dotenv()

PRACTICUM_TOKEN = os.getenv('SECRET_PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('SECRET_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('SECRET_TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler()
logger.addHandler(handler)


def check_tokens():
    """Проверка обязательных переменных окружения."""
    TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, token in TOKENS.items():
        if not token:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{name}"'
            )
            raise SystemExit('Ошибка проверки переменных окружения')
    logger.debug('Проверка переменных окружения пройдена успешно')


def send_message(bot, message):
    """Отправление сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Бот отправил сообщение')
    except Exception:
        logger.error('Ошибка отправки сообщения')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            logger.error('Эндпоинт API недоступен')
            raise AssertionError('Эндпоинт API недоступен')
        else:
            logger.debug('Эндпоинт API доступен')
    except requests.RequestException as error:
        logger.error(error)
    try:
        return homework_statuses.json()
    except ValueError:
        logger.error('Тип данных не соответствует Python')
        return ValueError('Ошибка, тип данных не соответствует Python')


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Ошибка, в response получен не словарь')
        raise TypeError('Ошибка, в response получен не словарь')
    if 'homeworks' not in response:
        logger.error('Отсутствует ключ homeworks')
        raise KeyError('Отсутствует ключ homeworks')
    homeworks_data = response['homeworks']
    current_date_data = response['current_date']
    if not isinstance(homeworks_data, list):
        logger.error('Ошбика, данные в homework не являются списком')
        raise TypeError('Ошбика, данные в homework не являются списком')
    if homeworks_data is None:
        logger.error('Отсутствует значение ключа homeworks')
        raise KeyError('Отсутствует значение ключа homeworks')
    if current_date_data is None:
        logger.error('Отсутствует значение ключа current_date')
        raise KeyError('Отсутствует значение ключа current_date')
    if not isinstance(current_date_data, int):
        logger.error('Формат даты указан неверно')
        raise TypeError('Формат даты указан неверно')
    return homeworks_data


def parse_status(homework):
    """Извлечение информации о конкретной домашней работе (статус)."""
    if 'homework_name' not in homework:
        logger.error('Отсутствует ключ названия домашки')
        raise KeyError('Отсутствует ключ названия домашки')
    if 'status' not in homework:
        logger.error('Отсутствует ключ статуса')
        raise KeyError('Отсутствует ключ статуса')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if homework_name is None:
        logger.error('Пустое поле с названием домашки')
        raise KeyError('Пустое поле с названием домашки')
    if status not in HOMEWORK_VERDICTS:
        logger.error('Не найден ключ по статусам')
        raise KeyError('Не найден ключ по статусам')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.debug('Отсутствуют новые статусы')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
