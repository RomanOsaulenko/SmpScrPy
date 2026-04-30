from __future__ import annotations
from typing import Any
#import xml.etree.ElementTree as ET
import datetime
import asyncio
import sys
import os
import aiohttp
import selectolax.lexbor as Lexbor
import random
import logging.handlers
from queue import SimpleQueue
import re
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode, unquote, quote
import posixpath
import unicodedata
import uuid

class FastAsyncQueueHandler(logging.handlers.QueueHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.enqueue(record)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.handleError(record)


class SmpScr:
    __XML_FILE_FULL_NAME = "smp_scr.xlm"                            #назва xml файлу
    __CATEGORY_PREF_ID = "cat"                                      #префікс id поля category
    __CATEGORIES_XML_FIELD_NAME = "categories"                      #назва поля categories
    __CATEGORY_XML_FIELD_NAME = "category"                          #назва поля category
    __OFFER_PREF_ID = "off"                                         #префікс id поля offer
    __OFFERS_XML_FIELD_NAME: "offers"                               #назва поля offers
    __OFFER_XML_FIELD_NAME: "offer"                                 #назва поля offer
    __TMP_CATEGORY_XML_FNAME = f"{uuid.uuid4().hex}cat.xml.tmp"     #тимчасовий файл для збереження даних категорії
    __TMP_OFFER_XML_F_NAME = f"{uuid.uuid4().hex}off.xml.tmp"       #тимчасовий файл для збереження даних товарів

    __K_PROPS = f"P{uuid.uuid4().hex}"                              #мітка у словнику данних властивості поля
    __K_SELF = f"S{uuid.uuid4().hex}"                               #мітка у словнику данних властивості поля, містить назву поля
    __K_TEXT = f"T{uuid.uuid4().hex}"
    __DEF_ENCODE = "utf-8-sig"                                      #кодування файлів за замовчуванням

    __LOG_FILE_FULL_NAME = "smp_scr.log"                            #назва файлу для логів
    __LOG_MAX_FILE_SIZE = 1*1024*1024                               #розмір файлу логів у байтах
    __LOG_FILE_ROLLS = 1                                            #кількість старих файлів логів (client_logs.log.1, .2)
    __LOG_FILE_URL = ""                                             #URL посилання на файл логу
    __log_queue = SimpleQueue()                                     #створюємо чергу для логів
    __log_listener = None                                           #слухач логів

    __TELEGRAM_BOT_TOKEN = ""                                       #токен телеграм бота
    __TELEGRAM_CHAT_ID = ""                                         #ІД телеграм чату

    __OFFER_SCRAPERS_CNT = 4                                        #кількість скраперів інформації товарів
    __CATEGORY_SCRAPERS_CNT = 1                                     #кількість скрапенів категорій
    __DEF_TIMEOUT = 10                                              #час очікування відповіді за замовчуванням
    __TIMEOUT = aiohttp.ClientTimeout(total=__DEF_TIMEOUT)          #параметр тайм-ауту
    __DEF_MAX_SLEEP = 3                                             #максимальний час для сну
    __MAX_GET_TRIES = 180                                           #кількість повторів запитів
    __HEADERS = {                                                   #заголовки для простої симуляції браузера
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    __TOTAL_INFO_CNT = 0                                            #Підрахунок кількості інформаційних логів
    __TOTAL_ERROR_CNT = 0                                           #Підрахунок кількості помилок
    __TOTAL_WARNING_CNT = 0                                         #Підрахунок кількості попереджень
    __TOTAL_CRITICAL_CNT = 0                                        #Підрахунок критичних помилок
    __GARBAGE_PARAMS = {                                            #Мусорні параметри які можна безпечно видалити
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'yclid', 'msclkid', 'mc_cid', 'mc_eid', '_openstat', 'ref'
    }

    __category_lnk_que = asyncio.Queue()                           #черга інформації про посилання категорії, містить словник: url, id, батьківське id
    __category_data_que = SimpleQueue()                          #черга інформації про категорії, яка оборобляється в __categories_collect
    __offer_lnk_que = asyncio.Queue()                              #черга інформації про посилання на товар, містить словник: url, id, cat_id, available
    __offer_data_que = SimpleQueue()                             #черга інформації про товар, яка оборобляється в  __offers_collect


    def __init__(self, conf_file:str = "cfg"):
        if conf_file == "":
            print("We use default settings")
        else:
            #update parameters from config file
            print("Tries to update config parameters from file")
            self.__update_params(conf_file)
        self.__TIMEOUT = aiohttp.ClientTimeout(total=self.__DEF_TIMEOUT)
        #setup loggin and start it
        self.__setup_logging()

    #update parameters from file
    def __update_params(self, conf_file:str = "cfg"):
        try:
            with (open(conf_file, 'r', encoding='utf-8') as file):
                for line in file:
                    if not line.strip():
                        continue
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        if "" != value:
                            match key:
                                case "XML_FILE_FULL_NAME":
                                    self.__XML_FILE_FULL_NAME = value

                                case "CATEGORY_PREF_ID":
                                    self.__CATEGORY_PREF_ID = value

                                case "CATEGORIES_XML_FIELD_NAME":
                                    self.__CATEGORIES_XML_FIELD_NAME = value

                                case "CATEGORY_XML_FIELD_NAME":
                                    self.__CATEGORY_XML_FIELD_NAME = value

                                case "OFFER_PREF_ID":
                                    self.__OFFER_PREF_ID = value

                                case "OFFERS_XML_FIELD_NAME":
                                    self.__OFFERS_XML_FIELD_NAME = value

                                case "OFFER_XML_FIELD_NAME":
                                    self.__OFFER_XML_FIELD_NAME = value

                                case "DEF_ENCODE":
                                    self.__DEF_ENCODE = value

                                case "LOG_FILE_FULL_NAME":
                                    self.__LOG_FILE_FULL_NAME = value

                                case "LOG_MAX_FILE_SIZE":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__LOG_MAX_FILE_SIZE = value
                                        else:
                                            print(f"{key}:{value} -- warning config pair, we'll use {self.__LOG_MAX_FILE_SIZE}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "LOG_FILE_ROLLS":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__LOG_FILE_ROLLS = value
                                        else:
                                            print(f"{key}:{value} -- warning config pair, we'll use {self.__LOG_FILE_ROLLS}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "LOG_FILE_URL":
                                    self.__LOG_FILE_URL = self.sanitize_url(value)

                                case "TELEGRAM_BOT_TOKEN":
                                    self.__TELEGRAM_BOT_TOKEN = value

                                case "TELEGRAM_CHAT_ID":
                                    self.__TELEGRAM_CHAT_ID = value

                                case "OFFER_SCRAPERS_CNT":
                                    try:
                                        value = int (value)
                                        if value > 0:
                                            self.__OFFER_SCRAPERS_CNT = value
                                        else:
                                            print(f"{key}:{value} -- warning config pair, we'll use {self.__OFFER_SCRAPERS_CNT}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "CATEGORY_SCRAPERS_CNT":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__CATEGORY_SCRAPERS_CNT = value
                                        else:
                                            print(
                                                f"{key}:{value} -- warning config pair, we'll use {self.__CATEGORY_SCRAPERS_CNT}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "DEF_TIMEOUT":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__DEF_TIMEOUT = value
                                        else:
                                            print(
                                                f"{key}:{value} -- warning config pair, we'll use {self.__DEF_TIMEOUT}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "DEF_MAX_SLEEP":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__DEF_MAX_SLEEP = value
                                        else:
                                            print(
                                                f"{key}:{value} -- warning config pair, we'll use {self.__DEF_MAX_SLEEP}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "MAX_GET_TRIES":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__MAX_GET_TRIES = value
                                        else:
                                            print(
                                                f"{key}:{value} -- warning config pair, we'll use {self.__MAX_GET_TRIES}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case "HEADERS":
                                    try:
                                        value = int(value)
                                        if value > 0:
                                            self.__HEADERS = value
                                        else:
                                            print(
                                                f"{key}:{value} -- warning config pair, we'll use {self.__HEADERS}")
                                    except:
                                        print(f"{key}:{value} -- error config pair")

                                case _:
                                    print(f"{key}:{value} -- error config pair")

                        else: print(f"{key}:{value} -- error config pair")
        except:
            print("There are problems with config file, uninitialised data is set by default")


    # Initializing logger
    def __setup_logging(self):

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()  # Видаляємо стандартний вивід
        root_logger.addHandler(FastAsyncQueueHandler(self.__log_queue))

        aiohttp_logger = logging.getLogger('aiohttp')
        aiohttp_logger.handlers.clear()
        aiohttp_logger.addHandler(FastAsyncQueueHandler(self.__log_queue))
        aiohttp_logger.setLevel(logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-18s | %(message)s",
            datefmt="%H:%M:%S"
        )

        from logging.handlers import QueueListener, RotatingFileHandler

        file_handler = RotatingFileHandler(
            self.__XML_FILE_FULL_NAME,
            maxBytes = self.__LOG_MAX_FILE_SIZE,  # 10 МБ на один файл
            backupCount = self.__LOG_FILE_ROLLS ,  # Зберігати старі файли (client_logs.log.1, .2)
            encoding = self.__DEF_ENCODE  #
        )

        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # У файл пишемо все включаючи загальний DEBUG

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)  # В консоль тільки INF0 та вище

        # Запуск Listener
        self.__log_listener = logging.handlers.QueueListener(
            self.__log_queue,
            file_handler,
            console_handler,
            respect_handler_level=True
        )
        self.__log_listener.start()

    async def __raw_xml_data_to_str(self, Data: dict, pref:str = "\t") -> str:
        rez = ""
        t_props : dict | None = Data.get(self.__K_PROPS, None)
        if t_props is None:
            return ""
        Data.pop(self.__K_PROPS)

        m_fild_name : str | None =  t_props.get(self.__K_SELF, None)
        if m_fild_name is None:
            return ""
        t_props.pop(self.__K_SELF)
        m_fild_name = self.sanitize_xml_string(m_fild_name)
        rez += f"{pref}<{m_fild_name} "
        for key in t_props.keys():
            rez += f'{self.sanitize_xml_string(key)}="{self.sanitize_xml_string(t_props[key])}" '
        rez += f">{self.sanitize_xml_string( t_props.get(self.__K_TEXT,"") )}\n"

        new_pref : str = pref +'\t'

        for key in Data.keys():
            if isinstance( Data[key], dict ):
                rez += self.__raw_xml_data_to_str(Data[key], new_pref)
            s_key = self.sanitize_xml_string(key)
            if self.is_url( Data[key] ):
                rez += f'{new_pref}<{s_key}>{self.sanitize_url(Data[key])}</{s_key}>\n'
            else:
                rez += f'{new_pref}<{s_key}>{self.sanitize_xml_string(Data[key])}</{s_key}>\n'

        #params

        rez+= f"{pref}</{m_fild_name}>\n"
        return rez
    #
    async def __categories_collect_to_xml(self):
        print ("Category collector")


    async def __offers_collect_to_xml(self):
        print ("Category collector")

    #запуск скрапера на виконня
    async def run_scraper(self, root_category_url:str):

        print("run_scrapers")

    # !override it
    async def __get_category_urls(self):
        print ( "Get categories links" )

    # !override it
    async def __get_offer_data(self):
        print("Get offer data")

    async def __unite_xmls(self):
        print("Unite data to xml file")

    #!override it
    async def __init_categories_lnks (self, url:str):
        print (f"Get categories links {url}")

    def is_url(text: str, *, allowed_schemes: set[str] | None = None) -> bool:
        if allowed_schemes is None:
            allowed_schemes = {"http", "https", "ftp", "ftps"}
        try:
            result = urlparse(text)
            # вимагаємо схему, мережеве розташування і дозволену схему
            return all([result.scheme, result.netloc]) and result.scheme in allowed_schemes
        except Exception:
            return False


    def sanitize_url(self, url: str, remove_trailing_slash: bool = True) -> str:
        if not url:
            return ""
        # 1. Unicode Нормалізація
        # Зводить різні бітові представлення однакових символів до єдиного стандарту
        url = unicodedata.normalize('NFC', url)

        # 2. Розбираємо URL на частини
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        # 3. Обробка домену (Netloc) та Punycode (IDNA)
        netloc = parsed.netloc.lower()

        # Відділяємо порт від хоста для обробки IDNA
        if ':' in netloc:
            hostname, port = netloc.split(':', 1)
        else:
            hostname, port = netloc, None

        # Конвертуємо розширені символи домену (кирилицю тощо) в Punycode
        try:
            hostname = hostname.encode('idna').decode('ascii')
        except UnicodeError:
            pass  # Якщо домен не валідний, залишаємо як є

        # Збираємо домен назад, ігноруючи дефолтні порти
        if port:
            if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
                netloc = hostname
            else:
                netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        # 4. Обробка шляху (Path)
        # Спочатку розкодовуємо (%XX -> символи), щоб уникнути подвійного кодування
        path = unquote(parsed.path)

        # Нормалізуємо шлях (видаляємо /../ та зайві сліші)
        path = posixpath.normpath(path)
        if path == '.':
            path = ''
        path = re.sub(r'//+', '/', path)

        if remove_trailing_slash and path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Кодуємо розширені символи назад (Кирилиця, пробіли, емодзі -> %XX)
        # safe="/~" гарантує, що слеші не будуть закодовані
        path = quote(path, safe="/~")

        # 5. Фільтрація та кодування параметрів
        query_params = parse_qsl(parsed.query, keep_blank_values=True)

        cleaned_params = []
        for k, v in query_params:
            if k.lower() not in self.__GARBAGE_PARAMS:
                cleaned_params.append((k, v))

        cleaned_params.sort(key=lambda x: x[0])

        # urlencode автоматично перетворює всі розширені символи в параметрах на %XX
        # Використовуємо quote_via=quote для заміни пробілів на %20 замість '+' (сучасніший стандарт)
        new_query = urlencode(cleaned_params, quote_via=quote)

        # 6. Збираємо фінальний URL без фрагмента (#)
        canonical_url = urlunparse((scheme, netloc, path, parsed.params, new_query, ''))
        return canonical_url

    def sanitize_xml_string(self, some_string: str):
        escape_map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&apos;'
        }
        xml_valid_pattern = re.compile( r'[&<>\"]|[\x09\x0A\x0D\x20-\xD7FF\xE000-\xFFFD\U00010000-\U0010FFFF]' )

        def replacer(match: re.Match) -> str:
            char = match.group(0)
            return escape_map.get(char, char)

        return (xml_valid_pattern.sub(replacer, some_string)).strip()

    async def finish(self):
        # send general info to telegram

        # finish logging
        if self.__log_listener is not None:
            self.__log_listener.stop()
            self.__log_listener = None

        print("Job is finished")

    def __del__(self): #destructor
        #self.finish()
        print("on Close methond")

