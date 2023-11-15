from http import HTTPStatus

import logging
import os
import sys
import time

import requests

from contextlib import suppress
from dotenv import load_dotenv
from telegram.error import TelegramError
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


logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s '
    '(Функция - %(funcName)s, строка - %(lineno)d, '
    'время работы (мс) - %(relativeCreated)d)'
)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка обязательных переменных окружения."""
    TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    names = []
    for name, token in TOKENS.items():
        if not token:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{name}"'
            )
            names.append(name)
    if len(names) >= 1:
        raise SystemExit('Ошибка проверки переменных окружения')
    logger.debug('Проверка переменных окружения пройдена успешно')


def send_message(bot, message):
    """Отправление сообщения в Telegram чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Бот отправил сообщение')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except requests.RequestException as error:
        logger.error(error)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ValueError('Эндпоинт API недоступен')
    logger.debug('Эндпоинт API доступен')
    try:
        return homework_statuses.json()
    except ValueError as error:
        return ValueError(
            f'Ошибка, тип данных не соответствует Python - {error}'
        )


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    logger.info('Начало проверки API.')
    if not isinstance(response, dict):
        raise TypeError('Ошибка, в response получен не словарь')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')
    homeworks_data = response['homeworks']
    if not isinstance(homeworks_data, list):
        raise TypeError('Ошбика, данные в homework не являются списком')
    logger.info('Проверка ответа API успешно завершилась.')


def parse_status(homework):
    """Извлечение информации о конкретной домашней работе (статус)."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ названия домашки')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ статуса')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Не найден ключ по статусам - {status}')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 200000
    last_error_message = ''
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            timestamp = response.get('current_date', int(time.time()))
            homework = response['homeworks']
            if not homework:
                log_message = 'Нет домашней работы для проверки.'
                logger.debug(log_message)
            else:
                message = parse_status(homework[0])
            if last_message != message:
                send_message(bot, message)
                last_message = message
            else:
                log_message = 'Статус дз не изменился.'
                logger.debug(log_message)
        except TelegramError as error:
            logger.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_error_message != message:
                logger.error(message, exc_info=True)
                with suppress(Exception):
                    send_message(bot, message)
            last_error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
