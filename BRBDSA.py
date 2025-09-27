import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
from datetime import datetime, date
import os
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8246055725:AAFVR4FK3mRWBb-HVdMSu8S2X8aQMOHoF_Y"

# Система прав доступа через Telegram username
ACCESS_CONFIG = {
    'head': ['ocean_jandal', 'director_username', 'your_username'],
    'manager': ['prlbrlgrl', 'manager2', 'sales1', 'sales2']
}

# Тарифы и подменю
TARIFFS = {
    'mts_real': {
        'name': '📱 МТС Риил',
        'submenu': {
            'mts_real_1month': '1 Месяц',
            'mts_real_subscription': 'Абонемент'
        }
    },
    'mts_more': {
        'name': '📶 МТС Больше',
        'submenu': {
            'mts_more_1month': '1 Месяц',
            'mts_more_subscription': 'Абонемент'
        }
    },
    'mts_super': {
        'name': '⚡ МТС Супер',
        'submenu': None
    },
    'membrane': {
        'name': '🛡️ Мембрана',
        'submenu': None
    },
    'yandex_search': {
        'name': '🔍 Яндекс Поиск',
        'submenu': None
    },
    'yandex_x5': {
        'name': '🛒 Яндекс Подписка X5',
        'submenu': {
            'yandex_x5_new': 'Новый клиент',
            'yandex_x5_returning': 'Вернувшийся клиент',
            'yandex_x5_active': 'Действующий клиент'
        }
    },
    'yandex_kids': {
        'name': '👶 Яндекс Подписка Детям',
        'submenu': {
            'yandex_kids_new': 'Новый клиент',
            'yandex_kids_returning': 'Вернувшийся клиент',
            'yandex_kids_active': 'Действующий клиент'
        }
    }
}

# Цены для калькулятора
PRICE_MAP = {
    'mts_real_1month': 81,
    'mts_real_subscription': 155,
    'mts_more_1month': 81,
    'mts_more_subscription': 175,
    'mts_super': 273,
    'membrane': 494,
    'yandex_search': 180,
    'yandex_x5_new': 650,
    'yandex_x5_returning': 250,
    'yandex_x5_active': 50,
    'yandex_kids_new': 650,
    'yandex_kids_returning': 250,
    'yandex_kids_active': 50
}

class SalesBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.sales_data = {}
        
        # Регистрация обработчиков
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("stats", self.stats),
            CommandHandler("report", self.report),
            CommandHandler("help", self.help_command),
            CommandHandler("id", self.get_id),
            CommandHandler("export", self.export_data),
            CallbackQueryHandler(self.button_handler)
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
        
        self.ensure_directories()
        self.migrate_old_data()

    def ensure_directories(self) -> None:
        """Создает необходимые директории для хранения данных"""
        directories = ['data/daily', 'data/monthly', 'data/backups']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Директория создана/проверена: {directory}")

    def migrate_old_data(self) -> None:
        """Миграция старых ключей статистики"""
        logger.info("Запуск миграции старых ключей статистики...")
        
        # Собираем все допустимые ключи
        expected_keys = set(TARIFFS.keys())
        for tariff_info in TARIFFS.values():
            if tariff_info.get('submenu'):
                expected_keys.update(tariff_info['submenu'].keys())

        # Создаем маппинг для преобразования старых ключей
        key_mapping = {}
        for tariff_key, tariff_info in TARIFFS.items():
            submenu = tariff_info.get('submenu') or {}
            for sub_key, human_name in submenu.items():
                # Старые ключи вида "тариф_человеческое_название"
                old_key = f"{tariff_key}_{human_name}"
                key_mapping[old_key] = sub_key
                key_mapping[old_key.strip()] = sub_key

        def process_file(file_path: str) -> bool:
            """Обрабатывает один файл статистики"""
            if not os.path.exists(file_path):
                return False
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                changed = False
                for user_data in data.values():
                    sales = user_data.get('sales', {})
                    new_sales = {}
                    
                    for key, value in sales.items():
                        if key in expected_keys:
                            new_sales[key] = new_sales.get(key, 0) + value
                        elif key in key_mapping:
                            new_key = key_mapping[key]
                            new_sales[new_key] = new_sales.get(new_key, 0) + value
                            changed = True
                        else:
                            # Попытка автоматического преобразования
                            new_key = self._auto_convert_key(key)
                            if new_key and new_key in expected_keys:
                                new_sales[new_key] = new_sales.get(new_key, 0) + value
                                changed = True
                            else:
                                new_sales[key] = new_sales.get(key, 0) + value
                    
                    user_data['sales'] = new_sales
                
                if changed:
                    # Создаем backup
                    backup_path = f"{file_path}.backup"
                    try:
                        if os.path.exists(backup_path):
                            os.remove(backup_path)
                        os.rename(file_path, backup_path)
                    except OSError:
                        logger.warning(f"Не удалось создать backup для {file_path}")
                    
                    # Сохраняем обновленные данные
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"Файл мигрирован: {file_path}")
                
                return changed
                
            except Exception as e:
                logger.error(f"Ошибка при обработке файла {file_path}: {e}")
                return False

        # Обрабатываем все JSON файлы в директориях
        for folder in ['data/daily', 'data/monthly']:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    if filename.endswith('.json') and not filename.endswith('.backup'):
                        file_path = os.path.join(folder, filename)
                        process_file(file_path)
        
        logger.info("Миграция данных завершена")

    def _auto_convert_key(self, key: str) -> str | None:
        """Автоматическое преобразование ключа"""
        if '_' not in key:
            return None
            
        parts = key.split('_', 1)
        if len(parts) != 2:
            return None
            
        tariff_key, suffix = parts
        if tariff_key not in TARIFFS:
            return None
            
        submenu = TARIFFS[tariff_key].get('submenu') or {}
        for sub_key, human_name in submenu.items():
            if human_name.lower() == suffix.lower():
                return sub_key
                
        return None

    def get_user_role(self, username: str | None) -> str | None:
        """Определение роли пользователя по username"""
        if not username:
            return None
            
        clean_username = username.lower().replace('@', '')
        
        if clean_username in ACCESS_CONFIG['head']:
            return 'head'
        elif clean_username in ACCESS_CONFIG['manager']:
            return 'manager'
        else:
            return None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        if not user:
            return
            
        role = self.get_user_role(user.username)
        if not role:
            await update.message.reply_text("❌ Доступ запрещен. Обратитесь к руководителю.")
            return

        # Инициализация данных пользователя
        if user.id not in self.sales_data:
            self.sales_data[user.id] = {
                'username': user.username,
                'full_name': user.full_name,
                'role': role,
                'sales': {}
            }

        await self.show_main_menu(update, user.id, role, is_new_message=True)

    async def show_main_menu(self, update, user_id: int, role: str, is_new_message: bool = False) -> None:
        """Отображение главного меню"""
        if role == 'manager':
            keyboard = [
                [InlineKeyboardButton("📱 МТС Риил", callback_data="tariff_mts_real")],
                [InlineKeyboardButton("📶 МТС Больше", callback_data="tariff_mts_more")],
                [InlineKeyboardButton("⚡ МТС Супер", callback_data="tariff_mts_super")],
                [InlineKeyboardButton("🛡️ Мембрана", callback_data="tariff_membrane")],
                [InlineKeyboardButton("🔍 Яндекс Поиск", callback_data="tariff_yandex_search")],
                [InlineKeyboardButton("🛒 Яндекс Подписка X5", callback_data="tariff_yandex_x5")],
                [InlineKeyboardButton("👶 Яндекс Подписка Детям", callback_data="tariff_yandex_kids")],
                [
                    InlineKeyboardButton("📊 Статистика за день", callback_data="stats_daily"),
                    InlineKeyboardButton("📈 Общая статистика", callback_data="stats_total")
                ],
                [InlineKeyboardButton("🧮 Калькулятор", callback_data="calculator")]
            ]
            welcome_text = "🎯 Выберите тариф для учета продажи:"
        else:
            keyboard = [
                [InlineKeyboardButton("📊 Статистика за день", callback_data="stats_daily")],
                [InlineKeyboardButton("📈 Общая статистика", callback_data="stats_total")],
                [InlineKeyboardButton("👥 Управление менеджерами", callback_data="manage_managers")],
                [InlineKeyboardButton("🔄 Сброс статистики", callback_data="reset_stats")],
                [InlineKeyboardButton("📤 Экспорт данных", callback_data="export_data")],
                [InlineKeyboardButton("🧮 Калькулятор", callback_data="calculator")]
            ]
            welcome_text = "👑 Панель руководителя:"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if is_new_message or isinstance(update, Update):
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        else:
            await update.edit_message_text(welcome_text, reply_markup=reply_markup)

    async def show_tariff_submenu(self, query, tariff_key: str) -> None:
        """Отображение подменю тарифа"""
        tariff_info = TARIFFS.get(tariff_key)
        if not tariff_info:
            await query.edit_message_text("❌ Тариф не найден")
            return

        if tariff_info['submenu']:
            keyboard = []
            for sub_key, sub_name in tariff_info['submenu'].items():
                keyboard.append([InlineKeyboardButton(sub_name, callback_data=sub_key)])
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🎯 {tariff_info['name']}\nВыберите тип:",
                reply_markup=reply_markup
            )
        else:
            await self.record_sale(query, tariff_key)

    async def record_sale(self, query, record_key: str, display_name: str | None = None) -> None:
        """Запись продажи"""
        user_id = query.from_user.id
        if user_id not in self.sales_data:
            await query.edit_message_text("❌ Сессия устарела. Отправьте /start")
            return

        user_data = self.sales_data[user_id]
        
        # Нормализация ключа
        normalized_key = self.normalize_key(record_key)
        if not display_name:
            display_name = self.get_display_name(normalized_key)

        # Обновление данных
        if normalized_key not in user_data['sales']:
            user_data['sales'][normalized_key] = 0
        user_data['sales'][normalized_key] += 1

        # Сохранение
        try:
            self.save_daily_sale(user_id, normalized_key)
            self.save_monthly_sale(user_id, normalized_key)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            await query.edit_message_text("❌ Ошибка при сохранении данных")
            return

        current_count = user_data['sales'][normalized_key]

        await query.edit_message_text(
            f"✅ Продажа записана!\n\n"
            f"📦 Тариф: {display_name}\n"
            f"📊 Всего продаж: {current_count}\n\n"
            f"Продолжайте в том же духе! 💪"
        )

        await asyncio.sleep(2)
        await self.show_main_menu(query, user_id, user_data['role'])

    def normalize_key(self, key: str) -> str:
        """Нормализация ключа тарифа"""
        # Прямое соответствие
        if key in TARIFFS:
            return key
            
        # Поиск в подменю
        for tariff_info in TARIFFS.values():
            submenu = tariff_info.get('submenu') or {}
            if key in submenu:
                return key
                
        # Попытка преобразования
        if '_' in key:
            parts = key.split('_', 1)
            if len(parts) == 2:
                tariff_key, suffix = parts
                if tariff_key in TARIFFS:
                    submenu = TARIFFS[tariff_key].get('submenu') or {}
                    for sub_key, human_name in submenu.items():
                        if human_name == suffix or human_name.strip() == suffix.strip():
                            return sub_key
                            
        return key

    def get_display_name(self, tariff_key: str) -> str:
        """Получение читаемого названия тарифа"""
        display_names = {
            'mts_real_1month': '📱 МТС Риил (1 Месяц)',
            'mts_real_subscription': '📱 МТС Риил (Абонемент)',
            'mts_real': '📱 МТС Риил',
            'mts_more_1month': '📶 МТС Больше (1 Месяц)',
            'mts_more_subscription': '📶 МТС Больше (Абонемент)',
            'mts_more': '📶 МТС Больше',
            'mts_super': '⚡ МТС Супер',
            'membrane': '🛡️ Мембрана',
            'yandex_search': '🔍 Яндекс Поиск',
            'yandex_x5_new': '🛒 Яндекс Подписка X5 (Новый)',
            'yandex_x5_returning': '🛒 Яндекс Подписка X5 (Вернувшийся)',
            'yandex_x5_active': '🛒 Яндекс Подписка X5 (Действующий)',
            'yandex_x5': '🛒 Яндекс Подписка X5',
            'yandex_kids_new': '👶 Яндекс Подписка Детям (Новый)',
            'yandex_kids_returning': '👶 Яндекс Подписка Детям (Вернувшийся)',
            'yandex_kids_active': '👶 Яндекс Подписка Детям (Действующий)',
            'yandex_kids': '👶 Яндекс Подписка Детям'
        }
        
        normalized_key = self.normalize_key(tariff_key)
        return display_names.get(normalized_key, normalized_key)

    def save_daily_sale(self, user_id: int, tariff_key: str) -> None:
        """Сохранение дневной статистики"""
        today = date.today().isoformat()
        filename = f'data/daily/sales_{today}.json'
        self._save_sale_to_file(filename, user_id, tariff_key)

    def save_monthly_sale(self, user_id: int, tariff_key: str) -> None:
        """Сохранение месячной статистики"""
        current_month = datetime.now().strftime('%Y-%m')
        filename = f'data/monthly/sales_{current_month}.json'
        self._save_sale_to_file(filename, user_id, tariff_key)

    def _save_sale_to_file(self, filename: str, user_id: int, tariff_key: str) -> None:
        """Общая функция сохранения статистики в файл"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}

            user_str = str(user_id)
            if user_str not in data:
                user_data = self.sales_data.get(user_id, {})
                data[user_str] = {
                    'username': user_data.get('username', ''),
                    'full_name': user_data.get('full_name', ''),
                    'sales': {}
                }

            if tariff_key not in data[user_str]['sales']:
                data[user_str]['sales'][tariff_key] = 0

            data[user_str]['sales'][tariff_key] += 1

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения в файл {filename}: {e}")
            raise

    def get_daily_stats(self, user_id: int | None = None) -> dict:
        """Получение дневной статистики"""
        today = date.today().isoformat()
        filename = f'data/daily/sales_{today}.json'
        return self._load_stats_from_file(filename, user_id)

    def get_monthly_stats(self, user_id: int | None = None, month: str | None = None) -> dict:
        """Получение месячной статистики"""
        if not month:
            month = datetime.now().strftime('%Y-%m')
        filename = f'data/monthly/sales_{month}.json'
        return self._load_stats_from_file(filename, user_id)

    def _load_stats_from_file(self, filename: str, user_id: int | None) -> dict:
        """Загрузка статистики из файла"""
        if not os.path.exists(filename):
            return {}
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if user_id is not None:
                user_str = str(user_id)
                return data.get(user_str, {'sales': {}})
            else:
                return data
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {filename}: {e}")
            return {}

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /stats - показывает дневную статистику"""
        user = update.effective_user
        if not user:
            return
            
        user_id = user.id
        if user_id not in self.sales_data:
            await update.message.reply_text("❌ Отправьте /start для начала работы")
            return

        daily_stats = self.get_daily_stats(user_id)
        await self._display_stats_message(update.message, daily_stats, "сегодня", "день")

    async def report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /report - общий отчет для руководителя"""
        user = update.effective_user
        if not user:
            return
            
        user_id = user.id
        if user_id not in self.sales_data:
            await update.message.reply_text("❌ Отправьте /start для начала работы")
            return

        user_data = self.sales_data[user_id]
        if user_data['role'] != 'head':
            await update.message.reply_text("❌ Доступ только для руководителя")
            return

        monthly_stats = self.get_monthly_stats()
        await self._display_report_message(update.message, monthly_stats)

    async def _display_stats_message(self, message, stats: dict, period_name: str, period_type: str) -> None:
        """Отображение статистики в сообщении"""
        sales_data = stats.get('sales', {})
        
        if not sales_data:
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            text = f"📊 Статистика за {period_name} ({date_str})\n\n📭 Продаж еще нет"
        else:
            total_sales = 0
            message_lines = []
            
            sorted_sales = sorted(sales_data.items(), key=lambda x: self.get_display_name(x[0]))
            for tariff_key, count in sorted_sales:
                tariff_name = self.get_display_name(tariff_key)
                message_lines.append(f"• {tariff_name}: {count} продаж")
                total_sales += count
                
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            text = f"📊 Статистика за {period_name} ({date_str})\n\n" + "\n".join(message_lines)
            text += f"\n\n📈 Всего за {period_type}: {total_sales} продаж"

        await message.reply_text(text)

    async def _display_report_message(self, message, monthly_stats: dict) -> None:
        """Отображение отчета для руководителя"""
        if not monthly_stats:
            text = f"📈 Общий отчет за {datetime.now().strftime('%B %Y')}\n\n📭 Продаж за этот месяц еще нет"
        else:
            total_all_sales = 0
            managers_stats = {}
            
            for user_str, user_data in monthly_stats.items():
                manager_name = user_data.get('full_name', 'Неизвестный')
                managers_stats[manager_name] = {'total': 0}
                
                for count in user_data.get('sales', {}).values():
                    managers_stats[manager_name]['total'] += count
                    total_all_sales += count

            text = f"📈 Общий отчет за {datetime.now().strftime('%B %Y')}\n\n"
            text += "👥 СТАТИСТИКА ПО МЕНЕДЖЕРАМ:\n\n"
            for manager, stats in sorted(managers_stats.items()):
                text += f"👤 {manager}: {stats['total']} продаж\n"
            
            text += f"\n🎯 ОБЩЕЕ КОЛИЧЕСТВО ПРОДАЖ: {total_all_sales}"

        await message.reply_text(text)

    async def show_daily_stats(self, query, user_id: int) -> None:
        """Показать дневную статистику в inline режиме"""
        daily_stats = self.get_daily_stats(user_id)
        await self._display_stats_inline(query, daily_stats, "сегодня", "день")

    async def show_total_stats(self, query, user_id: int) -> None:
        """Показать общую статистику в inline режиме"""
        monthly_stats = self.get_monthly_stats(user_id)
        await self._display_stats_inline(query, monthly_stats, "текущий месяц", "месяц")

    async def _display_stats_inline(self, query, stats: dict, period_name: str, period_type: str) -> None:
        """Отображение статистики в inline режиме"""
        sales_data = stats.get('sales', {})
        
        if not sales_data:
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            message = f"📊 Статистика за {period_name} ({date_str})\n\n📭 Продаж еще нет"
        else:
            total_sales = 0
            message_lines = []
            
            sorted_sales = sorted(sales_data.items(), key=lambda x: self.get_display_name(x[0]))
            for tariff_key, count in sorted_sales:
                tariff_name = self.get_display_name(tariff_key)
                message_lines.append(f"• {tariff_name}: {count} продаж")
                total_sales += count
                
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            message = f"📊 Статистика за {period_name} ({date_str})\n\n" + "\n".join(message_lines)
            message += f"\n\n📈 Всего за {period_type}: {total_sales} продаж"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_head_daily_stats(self, query) -> None:
        """Показать общую дневную статистику для руководителя"""
        daily_stats = self.get_daily_stats()
        await self._display_head_stats_inline(query, daily_stats, "сегодня", "день")

    async def show_head_total_stats(self, query) -> None:
        """Показать общую месячную статистику для руководителя"""
        monthly_stats = self.get_monthly_stats()
        await self._display_head_stats_inline(query, monthly_stats, "текущий месяц", "месяц")

    async def _display_head_stats_inline(self, query, stats: dict, period_name: str, period_type: str) -> None:
        """Отображение статистики руководителя в inline режиме"""
        if not stats:
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            message = f"📊 Общая статистика за {period_name} ({date_str})\n\n📭 Продаж еще нет"
        else:
            total_all_sales = 0
            message_lines = []
            
            for user_str, user_data in stats.items():
                manager_name = user_data.get('full_name', 'Неизвестный')
                manager_total = 0
                manager_lines = []
                
                for tariff_key, count in user_data.get('sales', {}).items():
                    tariff_name = self.get_display_name(tariff_key)
                    manager_lines.append(f"   • {tariff_name}: {count}")
                    manager_total += count
                
                total_all_sales += manager_total
                message_lines.append(f"👤 {manager_name}: {manager_total} продаж")
                message_lines.extend(manager_lines)
                message_lines.append("")
            
            current_date = datetime.now()
            if period_type == "день":
                date_str = current_date.strftime('%d.%m.%Y')
            else:
                date_str = current_date.strftime('%B %Y')
                
            message = f"📊 Общая статистика за {period_name} ({date_str})\n\n" + "\n".join(message_lines)
            message += f"\n🎯 ОБЩЕЕ КОЛИЧЕСТВО ПРОДАЖ: {total_all_sales}"

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def show_manage_managers(self, query) -> None:
        """Меню управления менеджерами для руководителя"""
        monthly_stats = self.get_monthly_stats()
        managers = []

        for user_str, user_data in monthly_stats.items():
            full_name = user_data.get('full_name', 'Неизвестный')
            total_sales = sum(user_data.get('sales', {}).values())
            managers.append({
                'id': user_str,
                'full_name': full_name,
                'total_sales': total_sales
            })

        keyboard = []
        for manager in managers:
            button_text = f"👤 {manager['full_name']} ({manager['total_sales']} продаж)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"manager_{manager['id']}")])

        keyboard.extend([
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("👥 Управление менеджерами:", reply_markup=reply_markup)

    async def show_reset_options(self, query, manager_id: str | None = None) -> None:
        """Показать опции сброса статистики"""
        if manager_id:
            try:
                manager_id_int = int(manager_id)
                manager_data = self.sales_data.get(manager_id_int)
                if manager_data:
                    message = f"🔄 Сброс статистики для {manager_data['full_name']}\n\n"
                    keyboard = [
                        [InlineKeyboardButton("🗑️ Сбросить дневную статистику", callback_data=f"reset_daily_{manager_id}")],
                        [InlineKeyboardButton("🗑️ Сбросить месячную статистику", callback_data=f"reset_monthly_{manager_id}")],
                        [InlineKeyboardButton("◀️ Назад к менеджерам", callback_data="manage_managers")]
                    ]
                else:
                    message = "❌ Пользователь не найден"
                    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
            except ValueError:
                message = "❌ Неверный ID менеджера"
                keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        else:
            message = "🔄 Сброс всей статистики\n\n"
            keyboard = [
                [InlineKeyboardButton("🗑️ Сбросить всю дневную статистику", callback_data="reset_all_daily")],
                [InlineKeyboardButton("🗑️ Сбросить всю месячную статистику", callback_data="reset_all_monthly")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    def reset_daily_stats(self, manager_id: str | None = None) -> None:
        """Сброс дневной статистики"""
        today = date.today().isoformat()
        filename = f'data/daily/sales_{today}.json'
        self._reset_stats_file(filename, manager_id)

    def reset_monthly_stats(self, manager_id: str | None = None) -> None:
        """Сброс месячной статистики"""
        current_month = datetime.now().strftime('%Y-%m')
        filename = f'data/monthly/sales_{current_month}.json'
        self._reset_stats_file(filename, manager_id)

    def _reset_stats_file(self, filename: str, manager_id: str | None) -> None:
        """Общая функция сброса статистики"""
        if not os.path.exists(filename):
            return

        if manager_id == "all" or not manager_id:
            os.remove(filename)
        else:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if manager_id in data:
                    data[manager_id]['sales'] = {}
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Ошибка сброса статистики: {e}")

    async def show_calculator(self, query, user_id: int) -> None:
        """Показать калькулятор доходов"""
        user_data = self.sales_data.get(user_id, {})
        role = user_data.get('role', 'manager')

        if role == 'head':
            monthly_stats = self.get_monthly_stats()
            if not monthly_stats:
                message = "🧮 Калькулятор: данных нет для текущего месяца"
            else:
                total_all = 0
                message_lines = [f"🧮 Калькулятор дохода — {datetime.now().strftime('%B %Y')}\n"]
                
                for user_str, udata in monthly_stats.items():
                    manager_total = 0
                    message_lines.append(f"\n👤 {udata.get('full_name', '—')}:")
                    
                    for tariff_key, count in udata.get('sales', {}).items():
                        price = PRICE_MAP.get(tariff_key, 0)
                        subtotal = price * count
                        manager_total += subtotal
                        message_lines.append(f"   • {self.get_display_name(tariff_key)}: {count} × {price} = {subtotal} ₽")
                    
                    message_lines.append(f"   ➜ Всего у менеджера: {manager_total} ₽")
                    total_all += manager_total
                
                message_lines.append(f"\n🎯 ИТОГО ПО ВСЕМ МЕНЕДЖЕРАМ: {total_all} ₽")
                message = "\n".join(message_lines)
        else:
            monthly_stats = self.get_monthly_stats(user_id)
            sales_data = monthly_stats.get('sales', {}) if monthly_stats else {}
            
            if not sales_data:
                message = "🧮 Калькулятор: у вас нет продаж за текущий месяц"
            else:
                total = 0
                message_lines = [f"🧮 Калькулятор дохода — {datetime.now().strftime('%B %Y')}\n"]
                
                for tariff_key, count in sales_data.items():
                    price = PRICE_MAP.get(tariff_key, 0)
                    subtotal = price * count
                    total += subtotal
                    message_lines.append(f"• {self.get_display_name(tariff_key)}: {count} × {price} = {subtotal} ₽")
                
                message_lines.append(f"\n💰 Итого: {total} ₽")
                message = "\n".join(message_lines)

        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик нажатий на кнопок"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if user_id not in self.sales_data:
            await query.edit_message_text("❌ Сессия устарела. Отправьте /start")
            return

        user_data = self.sales_data[user_id]
        data = query.data

        try:
            if data == "back_to_main":
                await self.show_main_menu(query, user_id, user_data['role'])
            elif data == "stats_daily":
                if user_data['role'] == 'head':
                    await self.show_head_daily_stats(query)
                else:
                    await self.show_daily_stats(query, user_id)
            elif data == "stats_total":
                if user_data['role'] == 'head':
                    await self.show_head_total_stats(query)
                else:
                    await self.show_total_stats(query, user_id)
            elif data == "manage_managers":
                await self.show_manage_managers(query)
            elif data == "reset_stats":
                await self.show_reset_options(query)
            elif data == "export_data":
                await self.export_data_from_button(query)
            elif data == "calculator":
                await self.show_calculator(query, user_id)
            elif data.startswith("manager_"):
                manager_id = data.split('_')[1]
                await self.show_reset_options(query, manager_id)
            elif data.startswith("reset_daily_"):
                manager_id = data.split('_')[2] if data != "reset_all_daily" else "all"
                self.reset_daily_stats(manager_id)
                await query.edit_message_text("✅ Дневная статистика сброшена")
                await asyncio.sleep(1)
                await self.show_main_menu(query, user_id, user_data['role'])
            elif data.startswith("reset_monthly_"):
                manager_id = data.split('_')[2] if data != "reset_all_monthly" else "all"
                self.reset_monthly_stats(manager_id)
                await query.edit_message_text("✅ Месячная статистика сброшена")
                await asyncio.sleep(1)
                await self.show_main_menu(query, user_id, user_data['role'])
            elif data.startswith("tariff_"):
                tariff_key = data[7:]
                await self.show_tariff_submenu(query, tariff_key)
            elif data in self._get_all_submenu_keys():
                await self.record_sale(query, data)
            elif data in TARIFFS and TARIFFS[data].get('submenu') is None:
                await self.record_sale(query, data)
            else:
                await query.edit_message_text("❌ Неизвестная команда")

        except Exception as e:
            logger.error(f"Ошибка в обработчике кнопок: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте снова.")

    def _get_all_submenu_keys(self) -> set:
        """Получить все ключи подменю"""
        keys = set()
        for tariff_info in TARIFFS.values():
            submenu = tariff_info.get('submenu')
            if submenu:
                keys.update(submenu.keys())
        return keys

    async def export_data_from_button(self, query) -> None:
        """Экспорт данных из кнопки"""
        user_id = query.from_user.id
        user_data = self.sales_data[user_id]
        
        if user_data['role'] != 'head':
            await query.edit_message_text("❌ Доступ только для руководителя")
            return

        await query.edit_message_text("📊 Подготовка экспорта данных...")
        report = self._generate_text_report()
        
        # Разбиваем на части если сообщение слишком длинное
        max_length = 4000
        if len(report) > max_length:
            parts = [report[i:i+max_length] for i in range(0, len(report), max_length)]
            for part in parts:
                await query.message.reply_text(f"```\n{part}\n```", parse_mode='Markdown')
        else:
            await query.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
            
        await query.edit_message_text("✅ Данные успешно экспортированы")

    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Экспорт данных через команду /export"""
        user = update.effective_user
        if not user:
            return
            
        user_id = user.id
        if user_id not in self.sales_data:
            await update.message.reply_text("❌ Отправьте /start для начала работы")
            return

        user_data = self.sales_data[user_id]
        if user_data['role'] != 'head':
            await update.message.reply_text("❌ Доступ только для руководителя")
            return

        await update.message.reply_text("📊 Подготовка экспорта данных...")
        report = self._generate_text_report()
        
        max_length = 4000
        if len(report) > max_length:
            parts = [report[i:i+max_length] for i in range(0, len(report), max_length)]
            for part in parts:
                await update.message.reply_text(f"```\n{part}\n```", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"```\n{report}\n```", parse_mode='Markdown')
            
        await update.message.reply_text("✅ Данные успешно экспортированы")

    def _generate_text_report(self) -> str:
        """Генерация текстового отчета"""
        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("ОТЧЕТ ПО ПРОДАЖАМ")
        report_lines.append(f"Сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 50)
        
        # Дневная статистика
        daily_stats = self.get_daily_stats()
        report_lines.append("\n📊 ДНЕВНАЯ СТАТИСТИКА:")
        if daily_stats:
            for user_str, user_data in daily_stats.items():
                report_lines.append(f"\n👤 {user_data.get('full_name', '—')}:")
                for tariff_key, count in user_data.get('sales', {}).items():
                    report_lines.append(f"   • {self.get_display_name(tariff_key)}: {count}")
        else:
            report_lines.append("   Нет данных")
        
        # Месячная статистика
        monthly_stats = self.get_monthly_stats()
        report_lines.append("\n📈 МЕСЯЧНАЯ СТАТИСТИКА:")
        if monthly_stats:
            for user_str, user_data in monthly_stats.items():
                total = sum(user_data.get('sales', {}).values())
                report_lines.append(f"\n👤 {user_data.get('full_name', '—')}: {total} продаж")
                for tariff_key, count in user_data.get('sales', {}).items():
                    report_lines.append(f"   • {self.get_display_name(tariff_key)}: {count}")
        else:
            report_lines.append("   Нет данных")
            
        return "\n".join(report_lines)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
        """Команда /help"""
        help_text = (
            "🤖 *КОМАНДЫ БОТА:*\n\n"
            "/start - Главное меню\n"
            "/stats - Статистика за сегодня\n"
            "/report - Общий отчет (только для руководителя)\n"
            "/export - Экспорт данных (только для руководителя)\n"
            "/help - Эта справка\n"
            "/id - Показать ваш ID и username\n\n"
            "*ДОСТУПНЫЕ ТАРИФЫ:*\n"
            "• 📱 МТС Риил (1 Месяц/Абонемент)\n"
            "• 📶 МТС Больше (1 Месяц/Абонемент)\n"
            "• ⚡ МТС Супер\n"
            "• 🛡️ Мембрана\n"
            "• 🔍 Яндекс Поиск\n"
            "• 🛒 Яндекс Подписка X5 (Новый/Вернувшийся/Действующий)\n"
            "• 👶 Яндекс Подписка Детям (Новый/Вернувшийся/Действующий)\n\n"
            "*📊 СИСТЕМА СТАТИСТИКИ:*\n"
            "- Дневная статистика (автоматически сохраняется)\n"
            "- Месячная статистика (сохраняется долгосрочно)\n"
            "- Текстовый экспорт для анализа"
        )

        if isinstance(update, Update):
            await update.message.reply_text(help_text, parse_mode='Markdown')
        else:
            await update.edit_message_text(help_text, parse_mode='Markdown')
            await asyncio.sleep(2)
            await self.show_main_menu(update, update.from_user.id, 
                                    self.sales_data[update.from_user.id]['role'])

    async def get_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /id - показать информацию о пользователе"""
        user = update.effective_user
        if not user:
            return
            
        role = self.get_user_role(user.username)

        message = (
            f"🆔 **Ваша информация:**\n\n"
            f"**ID:** `{user.id}`\n"
            f"**Username:** @{user.username or 'не установлен'}\n"
            f"**Имя:** {user.full_name}\n"
            f"**Роль:** {role or 'не определена'}\n\n"
            "📋 **Для доступа к боту:**\n"
            "1. Сообщите ваш username руководителю\n"
            "2. Руководитель добавит вас в систему\n"
            "3. Перезапустите бот командой /start"
        )

        await update.message.reply_text(message, parse_mode='Markdown')

    def run(self) -> None:
        """Запуск бота"""
        print("=" * 60)
        print("🤖 ЗАПУСК ТЕЛЕГРАМ БОТА")
        print(f"🐍 Python version: 3.13.4")
        print("=" * 60)
        
        try:
            self.application.run_polling()
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен")
        except Exception as e:
            print(f"❌ Ошибка: {e}")


# Запуск бота
if __name__ == '__main__':
    bot = SalesBot(BOT_TOKEN)
    bot.run()