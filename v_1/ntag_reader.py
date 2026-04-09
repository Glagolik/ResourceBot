"""
Улучшенный ридер NTAG213 с поддержкой ключей
"""

import time
from machine import Pin
from rc522 import RC522

class NTAGReader:
    def __init__(self, sck=5, mosi=6, miso=7, cs=4, rst=8):
        """Инициализация ридера"""
        self.rfid = RC522(sck, mosi, miso, cs, rst)
        self.led = Pin(25, Pin.OUT)
        self.led.value(0)
        
        # Статистика
        self.total_reads = 0
        self.successful_reads = 0
        self.failed_reads = 0
        
        print("NTAG Reader инициализирован")
        print(f"Версия RC522: 0x{self.rfid.get_version():02X}")
    
    def read_with_authentication(self, key_hex=None):
        """
        Чтение метки с аутентификацией
        """
        self.led.value(1)
        
        try:
            print(f"\n{'='*60}")
            print("ПОПЫТКА ЧТЕНИЯ МЕТКИ")
            print("="*60)
            
            # Чтение метки с ключом
            success, uid, all_data, user_data = self.rfid.read_ntag_with_key(key_hex, 'A')
            
            if not success or not uid:
                print("Не удалось прочитать метку")
                self.led.value(0)
                return False, None, None
            
            uid_str = self.rfid.format_uid(uid)
            print(f"✓ Метка обнаружена: {uid_str}")
            
            if all_data:
                # Парсинг данных
                parsed_data = self.rfid.parse_ntag_data(all_data)
                
                # Проверка, есть ли реальные данные
                has_real_data = False
                for page in range(4, 36):
                    if page in parsed_data['user_data']:
                        data = parsed_data['user_data'][page]
                        if data and data != [0, 0, 0, 0]:
                            has_real_data = True
                            break
                
                if has_real_data:
                    self.rfid.print_ntag_info(uid, parsed_data)
                    
                    # Обновление статистики
                    self.total_reads += 1
                    self.successful_reads += 1
                    
                    # Мигаем LED при успехе
                    self.blink_led(2, 0.1)
                    
                    return True, uid, parsed_data
                else:
                    print("Метка пустая или данные не прочитаны")
                    
                    # Тестирование ключей
                    print("\nТестирование различных ключей...")
                    key_result = self.rfid.test_keys(uid)
                    
                    if key_result:
                        key_hex, description, data = key_result
                        print(f"\nНайден рабочий ключ!")
                        print(f"Ключ: {key_hex} ({description})")
                        
                        # Повторное чтение с найденным ключом
                        success2, uid2, all_data2, user_data2 = self.rfid.read_ntag_with_key(key_hex, 'A')
                        if success2 and all_data2:
                            parsed_data2 = self.rfid.parse_ntag_data(all_data2)
                            self.rfid.print_ntag_info(uid2, parsed_data2)
                            
                            self.total_reads += 1
                            self.successful_reads += 1
                            self.blink_led(3, 0.05)
                            
                            return True, uid2, parsed_data2
                    
                    self.failed_reads += 1
                    self.blink_led(1, 0.3)  # Одиночное мигание при ошибке
                    return True, uid, None  # Возвращаем UID даже если данных нет
            else:
                print("Не удалось прочитать данные метки")
                self.failed_reads += 1
                self.blink_led(1, 0.3)
                return True, uid, None
                
        except Exception as e:
            print(f"Ошибка при чтении: {e}")
            self.failed_reads += 1
            self.blink_led(3, 0.1)  # Тройное мигание при ошибке
            return False, None, None
        
        finally:
            self.led.value(0)
    
    def blink_led(self, times=1, delay=0.1):
        """Мигание светодиодом"""
        for _ in range(times):
            self.led.value(1)
            time.sleep(delay)
            self.led.value(0)
            time.sleep(delay)
    
    def auto_read(self):
        """
        Автоматическое чтение с попыткой разных методов
        """
        print("\n" + "="*60)
        print("АВТОМАТИЧЕСКОЕ ЧТЕНИЕ МЕТКИ")
        print("="*60)
        
        # Получаем UID
        uid = self.rfid.read_uid()
        if not uid:
            print("Метка не обнаружена")
            return False, None, None
        
        uid_str = self.rfid.format_uid(uid)
        print(f"Обнаружена метка: {uid_str}")
        
        # Список ключей для попытки
        keys_to_try = [
            None,  # Без ключа
            "FFFFFFFFFFFF",  # Ключ по умолчанию
            "425245414B4D454946594F5543414E21",  # Кастомный ключ
            "A0A1A2A3A4A5",  # Тестовый ключ
            "D3F7D3F7D3F7",  # Другой ключ
        ]
        
        for key_hex in keys_to_try:
            if key_hex:
                print(f"\nПопытка с ключом: {key_hex[:12]}...")
            else:
                print(f"\nПопытка без ключа...")
            
            success, read_uid, data = self.read_with_authentication(key_hex)
            
            if success and data:
                print(f"\n✓ Успешно прочитано с ключом: {key_hex if key_hex else 'без ключа'}")
                return True, read_uid, data
        
        print("\n✗ Не удалось прочитать метку ни с одним ключом")
        return False, uid, None
    
    def continuous_read(self, interval=0.2):
        """
        Непрерывное чтение меток
        """
        print("\n" + "="*60)
        print("НЕПРЕРЫВНОЕ ЧТЕНИЕ МЕТОК")
        print("Прикладывайте метки для чтения")
        print("Для выхода нажмите Ctrl+C")
        print("="*60)
        
        last_uid = None
        
        try:
            while True:
                # Проверка метки
                uid = self.rfid.read_uid()
                
                if uid:
                    uid_str = self.rfid.format_uid(uid)
                    
                    if uid_str != last_uid:
                        print(f"\n[!] Обнаружена метка: {uid_str}")
                        
                        # Автоматическое чтение
                        success, read_uid, data = self.auto_read()
                        
                        if success:
                            last_uid = uid_str
                            
                            if data:
                                print(f"[✓] Метка успешно прочитана")
                            else:
                                print(f"[!] Метка прочитана, но данных нет")
                        else:
                            print(f"[✗] Ошибка чтения метки")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.print_stats()
    
    def print_stats(self):
        """Вывод статистики"""
        print("\n" + "="*60)
        print("СТАТИСТИКА РАБОТЫ:")
        print(f"Всего попыток чтения: {self.total_reads}")
        print(f"Успешных чтений: {self.successful_reads}")
        print(f"Неудачных чтений: {self.failed_reads}")
        
        if self.total_reads > 0:
            success_rate = (self.successful_reads / self.total_reads) * 100
            print(f"Процент успеха: {success_rate:.1f}%")
        
        print("="*60)
    
    def read_with_custom_key(self, key_hex):
        """
        Чтение с указанным ключом
        """
        print(f"\nЧтение с ключом: {key_hex}")
        return self.read_with_authentication(key_hex)