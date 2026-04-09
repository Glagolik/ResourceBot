"""
RC522 RFID Reader класс для MicroPython
Поддержка ключей для чтения защищенных NTAG213 меток
"""

from machine import Pin, SoftSPI
import time

class RC522:
    OK = 0
    NOTAGERR = 1
    ERR = 2
    
    REQIDL = 0x26
    REQALL = 0x52
    AUTHENT1A = 0x60
    AUTHENT1B = 0x61
    
    # Регистры
    CommandReg = 0x01
    ComIEnReg = 0x02
    DivlEnReg = 0x03
    ComIrqReg = 0x04
    DivIrqReg = 0x05
    ErrorReg = 0x06
    Status1Reg = 0x07
    Status2Reg = 0x08
    FIFODataReg = 0x09
    FIFOLevelReg = 0x0A
    WaterLevelReg = 0x0B
    ControlReg = 0x0C
    BitFramingReg = 0x0D
    CollReg = 0x0E
    ModeReg = 0x11
    TxModeReg = 0x12
    RxModeReg = 0x13
    TxControlReg = 0x14
    TxAutoReg = 0x15
    TxSelReg = 0x16
    RxSelReg = 0x17
    RxThresholdReg = 0x18
    DemodReg = 0x19
    MfTxReg = 0x1C
    MfRxReg = 0x1D
    SerialSpeedReg = 0x1F
    CRCResultRegH = 0x21
    CRCResultRegL = 0x22
    ModWidthReg = 0x24
    RFCfgReg = 0x26
    GsNReg = 0x27
    CWGsPReg = 0x28
    ModGsPReg = 0x29
    TModeReg = 0x2A
    TPrescalerReg = 0x2B
    TReloadRegH = 0x2C
    TReloadRegL = 0x2D
    TCounterValueRegH = 0x2E
    TCounterValueRegL = 0x2F
    TestSel1Reg = 0x31
    TestSel2Reg = 0x32
    TestPinEnReg = 0x33
    TestPinValueReg = 0x34
    TestBusReg = 0x35
    AutoTestReg = 0x36
    VersionReg = 0x37
    AnalogTestReg = 0x38
    TestDAC1Reg = 0x39
    TestDAC2Reg = 0x3A
    TestADCReg = 0x3B
    
    # Команды
    CMD_IDLE = 0x00
    CMD_MEM = 0x01
    CMD_GEN_RANDOM_ID = 0x02
    CMD_CALC_CRC = 0x03
    CMD_TRANSMIT = 0x04
    CMD_NO_CMD_CHANGE = 0x07
    CMD_RECEIVE = 0x08
    CMD_TRANSCEIVE = 0x0C
    CMD_MF_AUTHENT = 0x0E
    CMD_SOFT_RESET = 0x0F
    
    def __init__(self, sck=5, mosi=6, miso=7, cs=4, rst=8):
        """
        Инициализация RC522 с SoftSPI
        """
        self.spi = SoftSPI(
            baudrate=100000,
            polarity=0,
            phase=0,
            sck=Pin(sck),
            mosi=Pin(mosi),
            miso=Pin(miso)
        )
        
        self.cs = Pin(cs, Pin.OUT)
        self.rst = Pin(rst, Pin.OUT)
        
        self.cs.value(1)
        self.rst.value(0)
        
        time.sleep_ms(50)
        self.reset()
        self.init()
        
        # Ключи по умолчанию
        self.default_key_a = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]  # Ключ по умолчанию A
        self.default_key_b = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]  # Ключ по умолчанию B
        
        # Ключ из hex строки: 425245414B4D454946594F5543414E21
        self.custom_key = self.hex_to_bytes("425245414B4D454946594F5543414E21")
        
        # Кэш последней метки
        self.last_uid = None
        self.last_time = 0
        self.debounce_time = 1000
        
    def hex_to_bytes(self, hex_string):
        """Конвертация HEX строки в байты"""
        if len(hex_string) % 2 != 0:
            hex_string = '0' + hex_string
        
        result = []
        for i in range(0, len(hex_string), 2):
            result.append(int(hex_string[i:i+2], 16))
        return result
    
    def reset(self):
        """Сброс чипа RC522"""
        self.rst.value(0)
        time.sleep_us(2)
        self.rst.value(1)
        time.sleep_ms(50)
        
        self.write_register(self.CommandReg, self.CMD_SOFT_RESET)
        time.sleep_ms(50)
        
        while self.read_register(self.CommandReg) & (1 << 4):
            time.sleep_us(10)
    
    def write_register(self, addr, val):
        """Запись в регистр"""
        self.cs.value(0)
        self.spi.write(bytes([((addr << 1) & 0x7E), val]))
        self.cs.value(1)
    
    def read_register(self, addr):
        """Чтение регистра"""
        self.cs.value(0)
        self.spi.write(bytes([((addr << 1) & 0x7E) | 0x80]))
        data = self.spi.read(1)
        self.cs.value(1)
        return data[0]
    
    def set_bitmask(self, reg, mask):
        """Установка битовой маски"""
        current = self.read_register(reg)
        self.write_register(reg, current | mask)
    
    def clear_bitmask(self, reg, mask):
        """Сброс битовой маски"""
        current = self.read_register(reg)
        self.write_register(reg, current & (~mask))
    
    def init(self):
        """Инициализация RC522"""
        self.write_register(self.Status2Reg, 0x00)
        self.write_register(self.TModeReg, 0x8D)
        self.write_register(self.TPrescalerReg, 0x3E)
        self.write_register(self.TReloadRegL, 30)
        self.write_register(self.TReloadRegH, 0)
        self.write_register(self.TxAutoReg, 0x40)
        self.write_register(self.ModeReg, 0x3D)
        self.antenna_on()
        time.sleep_ms(10)
        
    def antenna_on(self):
        """Включение антенны"""
        current = self.read_register(self.TxControlReg)
        if not (current & 0x03):
            self.set_bitmask(self.TxControlReg, 0x03)
    
    def antenna_off(self):
        """Выключение антенны"""
        self.clear_bitmask(self.TxControlReg, 0x03)
    
    def to_card(self, command, send_data):
        """Обмен данными с картой"""
        back_data = []
        back_len = 0
        status = self.ERR
        irq_en = 0x00
        wait_irq = 0x00
        
        if command == self.CMD_MF_AUTHENT:
            irq_en = 0x12
            wait_irq = 0x10
        elif command == self.CMD_TRANSCEIVE:
            irq_en = 0x77
            wait_irq = 0x30
        
        self.write_register(self.ComIEnReg, irq_en | 0x80)
        self.clear_bitmask(self.ComIrqReg, 0x80)
        self.set_bitmask(self.FIFOLevelReg, 0x80)
        self.write_register(self.CommandReg, self.CMD_IDLE)
        
        for i in range(len(send_data)):
            self.write_register(self.FIFODataReg, send_data[i])
        
        self.write_register(self.CommandReg, command)
        
        if command == self.CMD_TRANSCEIVE:
            self.set_bitmask(self.BitFramingReg, 0x80)
        
        i = 1000
        while True:
            n = self.read_register(self.ComIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x01) and not (n & wait_irq)):
                break
            time.sleep_us(100)
        
        self.clear_bitmask(self.BitFramingReg, 0x80)
        
        if i != 0:
            if (self.read_register(self.ErrorReg) & 0x1B) == 0x00:
                status = self.OK
                if n & irq_en & 0x01:
                    status = self.NOTAGERR
                elif command == self.CMD_TRANSCEIVE:
                    n = self.read_register(self.FIFOLevelReg)
                    last_bits = self.read_register(self.ControlReg) & 0x07
                    
                    if last_bits != 0:
                        back_len = (n - 1) * 8 + last_bits
                    else:
                        back_len = n * 8
                    
                    if n > 16:
                        n = 16
                    
                    for i in range(n):
                        back_data.append(self.read_register(self.FIFODataReg))
        
        return (status, back_data, back_len)
    
    def request(self, req_mode):
        """Запрос метки"""
        self.write_register(self.BitFramingReg, 0x07)
        tag_type = [req_mode]
        (status, back_data, back_bits) = self.to_card(self.CMD_TRANSCEIVE, tag_type)
        
        if (status != self.OK) or (back_bits != 0x10):
            status = self.ERR
        
        return (status, back_bits)
    
    def anticoll(self):
        """Антиколлизия"""
        self.write_register(self.BitFramingReg, 0x00)
        serial_number = [0x93, 0x20]
        (status, back_data, back_bits) = self.to_card(self.CMD_TRANSCEIVE, serial_number)
        
        if status == self.OK and len(back_data) == 5:
            checksum = 0
            for i in range(4):
                checksum ^= back_data[i]
            
            if checksum != back_data[4]:
                status = self.ERR
        
        return (status, back_data)
    
    def calculate_crc(self, data):
        """Расчет CRC"""
        self.clear_bitmask(self.DivIrqReg, 0x04)
        self.set_bitmask(self.FIFOLevelReg, 0x80)
        
        for i in range(len(data)):
            self.write_register(self.FIFODataReg, data[i])
        
        self.write_register(self.CommandReg, self.CMD_CALC_CRC)
        
        i = 255
        while True:
            n = self.read_register(self.DivIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        
        crc = [
            self.read_register(self.CRCResultRegL),
            self.read_register(self.CRCResultRegH)
        ]
        
        return crc
    
    def select_tag(self, serial):
        """Выбор метки"""
        buffer = [0x93, 0x70]
        
        for i in range(5):
            buffer.append(serial[i])
        
        crc = self.calculate_crc(buffer)
        buffer.append(crc[0])
        buffer.append(crc[1])
        
        (status, back_data, back_len) = self.to_card(self.CMD_TRANSCEIVE, buffer)
        
        if (status == self.OK) and (back_len == 0x18):
            return self.OK
        
        return self.ERR
    
    def authenticate(self, auth_type, block_addr, key, uid):
        """Аутентификация для доступа к данным"""
        buffer = []
        buffer.append(auth_type)
        buffer.append(block_addr)
        
        # Добавляем ключ (6 байт)
        for i in range(6):
            if i < len(key):
                buffer.append(key[i])
            else:
                buffer.append(0xFF)
        
        # Добавляем UID (4 байта)
        for i in range(4):
            if i < len(uid):
                buffer.append(uid[i])
            else:
                buffer.append(0x00)
        
        (status, back_data, back_len) = self.to_card(self.CMD_MF_AUTHENT, buffer)
        return status
    
    def stop_crypto(self):
        """Остановка шифрования"""
        self.clear_bitmask(self.Status2Reg, 0x08)
    
    def read_block(self, block_addr, key=None, key_type='A', uid=None):
        """Чтение блока с аутентификацией"""
        if key is None:
            key = self.default_key_a
        
        if uid is None:
            # Получаем UID если не передан
            uid_data = self.read_uid()
            if not uid_data:
                return None
            uid = uid_data
        
        # Аутентификация
        if key_type == 'A':
            auth_type = self.AUTHENT1A
        else:
            auth_type = self.AUTHENT1B
        
        status = self.authenticate(auth_type, block_addr, key, uid)
        if status != self.OK:
            print(f"Ошибка аутентификации блока {block_addr}")
            return None
        
        # Чтение данных
        data = [0x30, block_addr]
        crc = self.calculate_crc(data)
        data.append(crc[0])
        data.append(crc[1])
        
        (status, back_data, back_len) = self.to_card(self.CMD_TRANSCEIVE, data)
        
        # Останавливаем шифрование
        self.stop_crypto()
        
        if status == self.OK and len(back_data) == 16:
            return back_data
        
        return None
    
    def get_version(self):
        """Получение версии чипа"""
        return self.read_register(self.VersionReg)
    
    def read_uid(self):
        """Быстрое чтение UID метки"""
        current_time = time.ticks_ms()
        
        (status, _) = self.request(self.REQIDL)
        if status != self.OK:
            return None
        
        (status, uid_data) = self.anticoll()
        if status != self.OK or not uid_data:
            return None
        
        if (self.last_uid == uid_data and 
            time.ticks_diff(current_time, self.last_time) < self.debounce_time):
            return None
        
        self.last_uid = uid_data
        self.last_time = current_time
        
        return uid_data[:4]
    
    def read_ntag_page(self, page, key=None, key_type='A'):
        """Чтение страницы NTAG с аутентификацией"""
        uid = self.read_uid()
        if not uid:
            return None
        
        # Для NTAG213 чтение страниц не требует аутентификации до 0x80
        # Но если метка защищена, нужно использовать ключ
        
        data = self.read_block(page, key, key_type, uid)
        if data:
            return data[:4]  # NTAG возвращает 4 байта на страницу
        return None
    
    def read_ntag_with_key(self, key_hex=None, key_type='A'):
        """
        Чтение NTAG метки с использованием ключа
        """
        if key_hex:
            key = self.hex_to_bytes(key_hex)
        else:
            key = self.custom_key
        
        uid = self.read_uid()
        if not uid:
            return False, None, None, None
        
        all_data = {}
        
        try:
            # Выбор метки
            if self.select_tag(uid + [0]) != self.OK:
                print("Ошибка выбора метки")
                return True, uid, None, None
            
            # Пробуем читать без аутентификации сначала
            print("Попытка чтения без аутентификации...")
            for page in range(0, 36):
                data = self.read_ntag_page(page, None, key_type)
                if data:
                    all_data[page] = data
                else:
                    # Пробуем с ключом
                    if key:
                        data = self.read_ntag_page(page, key, key_type)
                        if data:
                            all_data[page] = data
                        else:
                            all_data[page] = [0, 0, 0, 0]
                    else:
                        all_data[page] = [0, 0, 0, 0]
            
            # Извлечение пользовательских данных
            user_data = {}
            for page in range(4, 36):
                if page in all_data:
                    user_data[page] = all_data[page]
            
            return True, uid, all_data, user_data
            
        except Exception as e:
            print(f"Ошибка чтения с ключом: {e}")
            return False, uid, None, None
    
    def read_full_ntag(self):
        """
        Полное чтение NTAG213 метки с разными методами
        """
        # Сначала пробуем прочитать без ключа
        print("Попытка чтения без ключа...")
        success1, uid1, all_data1, user_data1 = self.read_ntag_with_key(None, 'A')
        
        if success1 and uid1 and all_data1:
            # Проверяем, есть ли реальные данные
            has_data = False
            for page in range(4, 36):
                if page in all_data1 and all_data1[page] != [0, 0, 0, 0]:
                    has_data = True
                    break
            
            if has_data:
                return success1, uid1, all_data1, user_data1
        
        # Если не получилось, пробуем с ключом по умолчанию
        print("Попытка чтения с ключом по умолчанию...")
        success2, uid2, all_data2, user_data2 = self.read_ntag_with_key("FFFFFFFFFFFF", 'A')
        
        if success2 and uid2 and all_data2:
            return success2, uid2, all_data2, user_data2
        
        # Если не получилось, пробуем с кастомным ключом
        print("Попытка чтения с кастомным ключом...")
        success3, uid3, all_data3, user_data3 = self.read_ntag_with_key("425245414B4D454946594F5543414E21", 'A')
        
        if success3 and uid3 and all_data3:
            return success3, uid3, all_data3, user_data3
        
        # Если все методы не сработали, возвращаем UID
        uid = self.read_uid()
        return True, uid, None, None if uid else (False, None, None, None)
    
    def extract_user_data(self, all_data):
        """Извлечение пользовательских данных"""
        if not all_data:
            return {}
        
        user_data = {}
        for page in range(4, 36):
            if page in all_data:
                user_data[page] = all_data[page]
        
        return user_data
    
    def parse_ntag_data(self, all_data):
        """Парсинг данных NTAG метки"""
        if not all_data:
            return {}
        
        result = {
            'system_data': {},
            'user_data': {},
            'raw_text': '',
            'hex_data': ''
        }
        
        # Системные данные
        for page in range(0, 4):
            if page in all_data:
                result['system_data'][page] = all_data[page]
        
        # Пользовательские данные
        for page in range(4, 36):
            if page in all_data:
                result['user_data'][page] = all_data[page]
        
        # Извлечение текста
        text_data = self.extract_text_from_data(result['user_data'])
        result['raw_text'] = text_data
        
        # HEX представление
        result['hex_data'] = self.data_to_hex(result['user_data'])
        
        return result
    
    def extract_text_from_data(self, user_data):
        """Извлечение текста из данных"""
        if not user_data:
            return ""
        
        all_bytes = bytearray()
        for page in sorted(user_data.keys()):
            all_bytes.extend(user_data[page])
        
        # Удаляем нулевые байты в конце
        while all_bytes and all_bytes[-1] == 0:
            all_bytes = all_bytes[:-1]
        
        # Пытаемся декодировать
        try:
            text = all_bytes.decode('utf-8', errors='ignore')
            return text.strip()
        except:
            pass
        
        return ""
    
    def data_to_hex(self, user_data):
        """Конвертация данных в HEX строку"""
        if not user_data:
            return ""
        
        all_bytes = bytearray()
        for page in sorted(user_data.keys()):
            all_bytes.extend(user_data[page])
        
        hex_str = ""
        for i, byte in enumerate(all_bytes):
            if i > 0 and i % 16 == 0:
                hex_str += "\n"
            hex_str += f"{byte:02X} "
        
        return hex_str.strip()
    
    def format_uid(self, uid):
        """Форматирование UID"""
        if not uid:
            return ""
        return ''.join(['{:02X}'.format(x) for x in uid])
    
    def print_ntag_info(self, uid, parsed_data):
        """Вывод информации о метке"""
        if not uid or not parsed_data:
            return
        
        uid_str = self.format_uid(uid)
        
        print("\n" + "="*60)
        print(f"NTAG213 МЕТКА")
        print("="*60)
        print(f"UID: {uid_str}")
        print(f"Время: {time.ticks_ms()} мс")
        print("-"*60)
        
        # Системные данные
        print("СИСТЕМНЫЕ ДАННЫЕ:")
        for page in sorted(parsed_data['system_data'].keys()):
            data = parsed_data['system_data'][page]
            hex_str = ' '.join([f'{b:02X}' for b in data])
            ascii_str = ''.join([chr(b) if 32 <= b < 127 else '.' for b in data])
            print(f"  Страница {page:2d}: {hex_str}  |  {ascii_str}")
        
        # Пользовательские данные
        print("\nПОЛЬЗОВАТЕЛЬСКИЕ ДАННЫЕ:")
        user_pages = sorted(parsed_data['user_data'].keys())
        
        for page in user_pages:
            data = parsed_data['user_data'][page]
            hex_str = ' '.join([f'{b:02X}' for b in data])
            ascii_str = ''.join([chr(b) if 32 <= b < 127 else '.' for b in data])
            print(f"  Страница {page:2d}: {hex_str}  |  {ascii_str}")
        
        # Текстовые данные
        if parsed_data['raw_text']:
            print(f"\nТЕКСТОВЫЕ ДАННЫЕ:")
            print(f"  {parsed_data['raw_text']}")
        
        # HEX данные
        if parsed_data['hex_data']:
            print(f"\nHEX ДАННЫЕ:")
            print(f"  {parsed_data['hex_data']}")
        
        print("="*60)
    
    def test_keys(self, uid):
        """Тестирование различных ключей для метки"""
        if not uid:
            return None
        
        test_keys = [
            ("FFFFFFFFFFFF", "Ключ по умолчанию A"),
            ("A0A1A2A3A4A5", "Тестовый ключ A"),
            ("425245414B4D454946594F5543414E21", "Кастомный ключ"),
            ("D3F7D3F7D3F7", "Ключ по умолчанию B"),
            ("000000000000", "Нулевой ключ"),
            ("123456789ABC", "Произвольный ключ"),
        ]
        
        print(f"\nТестирование ключей для UID: {self.format_uid(uid)}")
        print("-" * 40)
        
        for key_hex, description in test_keys:
            print(f"\nПопытка с ключом: {description}")
            print(f"Ключ: {key_hex}")
            
            # Пробуем прочитать страницу 4 с этим ключом
            key = self.hex_to_bytes(key_hex)
            data = self.read_block(4, key, 'A', uid)
            
            if data:
                print(f"  ✓ Успешно! Данные: {data[:4]}")
                return key_hex, description, data
            else:
                print(f"  ✗ Не удалось")
        
        print("\nНи один ключ не подошел")
        return None