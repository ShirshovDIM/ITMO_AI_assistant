import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.main import ITMOAIChatbot, RecommendationStates, logging


class ITMOBot:
    def __init__(self, token: str, claude_api_key: str = None):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.chatbot = ITMOAIChatbot(claude_api_key=claude_api_key)
        self.user_backgrounds = {}
        
        # Register handlers
        self.register_handlers()
        
    def register_handlers(self):
        """Register all message handlers"""
        
        @self.dp.message(Command("start"))
        async def start_handler(message: types.Message):
            """Handle /start command"""
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🎓 О программах")],
                    [KeyboardButton(text="💰 Стоимость обучения"), KeyboardButton(text="📚 Поступление")],
                    [KeyboardButton(text="💼 Карьера"), KeyboardButton(text="📖 Дисциплины")],
                    [KeyboardButton(text="🎯 Получить рекомендацию")]
                ],
                resize_keyboard=True
            )
            
            welcome_text = """Привет! 👋 Я помощник по выбору магистерской программы в ИТМО.

Помогу разобраться между двумя программами:
• 🤖 **Искусственный интеллект** - для ML-инженеров
• 📊 **Управление ИИ-продуктами** - для AI Product Managers

Выберите интересующую тему или задайте свой вопрос!"""
            
            await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
        
        @self.dp.message(Command("help"))
        async def help_handler(message: types.Message):
            """Handle /help command"""
            help_text = """Я могу рассказать о:

📚 **Поступление** - способы поступления, конкурсы, олимпиады
💰 **Стоимость** - цены, бюджетные места, стипендии
📖 **Дисциплины** - учебные планы, предметы
💼 **Карьера** - кем можно работать, зарплаты
🏢 **Партнеры** - компании-партнеры программ
🌍 **Международные возможности** - стажировки, конференции

Или получите **персональную рекомендацию** по выбору программы!

Просто напишите свой вопрос или используйте кнопки меню."""
            
            await message.answer(help_text, parse_mode="Markdown")
        
        @self.dp.message(Command("recommend"))
        async def recommend_command(message: types.Message, state: FSMContext):
            """Start recommendation flow"""
            await self.start_recommendation(message, state)
        
        @self.dp.message(lambda message: message.text == "🎯 Получить рекомендацию")
        async def recommendation_button_handler(message: types.Message, state: FSMContext):
            """Handle recommendation button"""
            await self.start_recommendation(message, state)
        
        @self.dp.message(lambda message: message.text == "🎓 О программах")
        async def programs_handler(message: types.Message):
            """Handle programs info request"""
            response = self.chatbot.process_query("расскажи подробно о программах магистратуры")
            await message.answer(response, parse_mode="Markdown")
        
        @self.dp.message(lambda message: message.text == "💰 Стоимость обучения")
        async def cost_handler(message: types.Message):
            """Handle cost info request"""
            response = self.chatbot.process_query("сколько стоит обучение и есть ли бюджетные места")
            await message.answer(response, parse_mode="Markdown")
        
        @self.dp.message(lambda message: message.text == "📚 Поступление")
        async def admission_handler(message: types.Message):
            """Handle admission info request"""
            response = self.chatbot.process_query("как поступить на программы, какие есть способы")
            await message.answer(response, parse_mode="Markdown")
        
        @self.dp.message(lambda message: message.text == "💼 Карьера")
        async def career_handler(message: types.Message):
            """Handle career info request"""
            response = self.chatbot.process_query("кем можно работать после окончания и какие зарплаты")
            await message.answer(response, parse_mode="Markdown")
        
        @self.dp.message(lambda message: message.text == "📖 Дисциплины")
        async def disciplines_handler(message: types.Message):
            """Handle disciplines info request"""
            response = self.chatbot.process_query("какие предметы изучают на программах")
            await message.answer(response, parse_mode="Markdown")
        
        # Recommendation flow handlers
        @self.dp.message(RecommendationStates.asking_technical_skills)
        async def process_technical_skills(message: types.Message, state: FSMContext):
            """Process technical skills answer"""
            user_id = message.from_user.id
            if user_id not in self.user_backgrounds:
                self.user_backgrounds[user_id] = {}
            
            answer = message.text.lower()
            self.user_backgrounds[user_id]['technical_skills'] = answer in ['да', 'yes', '+']
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "Интересует ли вас управление продуктами и проектами?",
                reply_markup=keyboard
            )
            await state.set_state(RecommendationStates.asking_management_interest)
        
        @self.dp.message(RecommendationStates.asking_management_interest)
        async def process_management_interest(message: types.Message, state: FSMContext):
            """Process management interest answer"""
            user_id = message.from_user.id
            answer = message.text.lower()
            self.user_backgrounds[user_id]['management_interest'] = answer in ['да', 'yes', '+']
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "Есть ли у вас опыт программирования (любой язык)?",
                reply_markup=keyboard
            )
            await state.set_state(RecommendationStates.asking_programming_experience)
        
        @self.dp.message(RecommendationStates.asking_programming_experience)
        async def process_programming_experience(message: types.Message, state: FSMContext):
            """Process programming experience answer"""
            user_id = message.from_user.id
            answer = message.text.lower()
            self.user_backgrounds[user_id]['programming_experience'] = answer in ['да', 'yes', '+']
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "Знакомы ли вы с машинным обучением (хотя бы базово)?",
                reply_markup=keyboard
            )
            await state.set_state(RecommendationStates.asking_ml_knowledge)
        
        @self.dp.message(RecommendationStates.asking_ml_knowledge)
        async def process_ml_knowledge(message: types.Message, state: FSMContext):
            """Process ML knowledge answer"""
            user_id = message.from_user.id
            answer = message.text.lower()
            self.user_backgrounds[user_id]['ml_knowledge'] = answer in ['да', 'yes', '+']
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "Есть ли у вас опыт работы с цифровыми продуктами (разработка, управление, аналитика)?",
                reply_markup=keyboard
            )
            await state.set_state(RecommendationStates.asking_product_experience)
        
        @self.dp.message(RecommendationStates.asking_product_experience)
        async def process_product_experience(message: types.Message, state: FSMContext):
            """Process product experience answer and give recommendation"""
            user_id = message.from_user.id
            answer = message.text.lower()
            self.user_backgrounds[user_id]['product_experience'] = answer in ['да', 'yes', '+']
            
            # Get recommendation
            recommendation = self.chatbot.recommend_program(self.user_backgrounds[user_id])
            
            # Get disciplines recommendation
            if "Искусственный интеллект" in recommendation and "Управление ИИ-продуктами" not in recommendation or recommendation.count("Искусственный интеллект") > recommendation.count("Управление ИИ-продуктами"):
                disciplines_rec = self.chatbot.get_disciplines_recommendation('ai', self.user_backgrounds[user_id])
            elif "Управление ИИ-продуктами" in recommendation:
                disciplines_rec = self.chatbot.get_disciplines_recommendation('ai_product', self.user_backgrounds[user_id])
            else:
                disciplines_rec = ""
            
            # Create keyboard for return to main menu
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🎓 О программах")],
                    [KeyboardButton(text="💰 Стоимость обучения"), KeyboardButton(text="📚 Поступление")],
                    [KeyboardButton(text="💼 Карьера"), KeyboardButton(text="📖 Дисциплины")],
                    [KeyboardButton(text="🎯 Получить рекомендацию")]
                ],
                resize_keyboard=True
            )
            
            full_response = f"{recommendation}\n\n{disciplines_rec}" if disciplines_rec else recommendation
            
            await message.answer(full_response, reply_markup=keyboard, parse_mode="Markdown")
            await state.clear()
        
        # Default message handler
        @self.dp.message()
        async def general_message_handler(message: types.Message):
            """Handle all other messages"""
            response = self.chatbot.process_query(message.text)
            await message.answer(response, parse_mode="Markdown")
    
    async def start_recommendation(self, message: types.Message, state: FSMContext):
        """Start the recommendation flow"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Отлично! Я задам вам несколько вопросов, чтобы дать персональную рекомендацию.\n\n"
            "У вас есть технический бэкграунд (математика, программирование, инженерия)?",
            reply_markup=keyboard
        )
        await state.set_state(RecommendationStates.asking_technical_skills)

async def main():
    # Get tokens from environment variables
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    
    if not BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return
    
    # Create and start bot
    bot = ITMOBot(token=BOT_TOKEN, claude_api_key=CLAUDE_API_KEY)
    
    try:
        await bot.start()
    except Exception as e:
        logging.error(f"Bot stopped with error: {e}")


if __name__ == "__main__":
    # For local testing, you can set tokens here (DO NOT commit with real tokens!)
    # os.environ["TELEGRAM_BOT_TOKEN"] = "your-telegram-bot-token"
    # os.environ["CLAUDE_API_KEY"] = "your-claude-api-key"  # Optional
    
    asyncio.run(main())
