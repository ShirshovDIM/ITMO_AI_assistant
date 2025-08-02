import os
import logging
from typing import List, Dict
import faiss
from sentence_transformers import SentenceTransformer
import anthropic
from transformers import AutoTokenizer, AutoModelForCausalLM
from aiogram.fsm.state import State, StatesGroup
import torch
import warnings
import json


warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

# States for the recommendation flow
class RecommendationStates(StatesGroup):
    asking_technical_skills = State()
    asking_management_interest = State()
    asking_programming_experience = State()
    asking_ml_knowledge = State()
    asking_product_experience = State()

class ITMOAIChatbot:
    """
    Чатбот для помощи абитуриентам в выборе между программами:
    - Искусственный интеллект
    - Управление ИИ-продуктами/AI Product
    """
    
    def __init__(self, claude_api_key: str = None, max_tokens_per_month: int = 100000):
        """
        Инициализация чатбота
        
        Args:
            claude_api_key: API ключ для Claude
            max_tokens_per_month: Максимальное количество токенов в месяц
        """
        self.claude_api_key = claude_api_key
        self.max_tokens_per_month = max_tokens_per_month
        self.used_tokens = 0
        
        # Инициализация моделей
        self.embedder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        
        if claude_api_key:
            self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
        else:
            self.claude_client = None
        
        # Резервная open-source модель
        self.fallback_model = None
        self.fallback_tokenizer = None
        
        # Загрузка базы знаний
        self.knowledge_base = self._load_knowledge_base()
        self.index = None
        self.create_faiss_index()
        
        # Parsed program data
        self.ai_program_data = None
        self.ai_product_program_data = None
        
    def _load_knowledge_base(self) -> List[Dict[str, str]]:
        """Загрузка базы знаний о программах"""
        
        with open(os.path.join(os.path.dirname(__file__), "knowledge_base.json"), "r", encoding="utf-8") as f:
            knowledge_base = json.load(f)
        
        return knowledge_base
        
    def create_faiss_index(self):
        """Создание FAISS индекса для поиска"""
        texts = [item['text'] for item in self.knowledge_base]
        embeddings = self.embedder.encode(texts)
        
        # Нормализация векторов для косинусного сходства
        faiss.normalize_L2(embeddings)
        
        # Создание индекса
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner Product для косинусного сходства
        self.index.add(embeddings.astype('float32'))
        
    def retrieve_relevant_info(self, query: str, k: int = 5) -> List[Dict[str, str]]:
        """
        Поиск релевантной информации по запросу
        
        Args:
            query: Запрос пользователя
            k: Количество результатов
            
        Returns:
            Список релевантных фрагментов из базы знаний
        """
        # Получение эмбеддинга запроса
        query_embedding = self.embedder.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Поиск ближайших соседей
        distances, indices = self.index.search(query_embedding.astype('float32'), k)
        
        # Возврат релевантных документов
        results = []
        for idx in indices[0]:
            if idx != -1:  # FAISS возвращает -1 если результатов меньше k
                results.append(self.knowledge_base[idx])
                
        return results
    
    def _use_fallback_model(self, prompt: str) -> str:
        """Использование резервной open-source модели LLaMA 2 7B Chat"""
        if self.fallback_model is None:
            logging.info("Загрузка резервной модели LLaMA 2 7B Chat...")

            model_name = "meta-llama/Llama-2-7b-chat-hf"
            self.fallback_tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
            self.fallback_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            self.fallback_tokenizer.pad_token = self.fallback_tokenizer.eos_token

        inputs = self.fallback_tokenizer(prompt, return_tensors="pt", return_token_type_ids=False).to(self.fallback_model.device)

        with torch.no_grad():
            outputs = self.fallback_model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.fallback_tokenizer.eos_token_id
            )

        response = self.fallback_tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Удаляем prompt из начала ответа
        if prompt in response:
            response = response[len(prompt):].strip()

        return response[:1000].strip()

    
    def generate_response(self, query: str, context: List[Dict[str, str]]) -> str:
        """
        Генерация ответа с использованием Claude API или fallback модели
        
        Args:
            query: Запрос пользователя
            context: Контекст из базы знаний
            
        Returns:
            Ответ чатбота
        """
        # Подготовка контекста
        context_text = "\n\n".join([f"- {item['text']}" for item in context])
        
        prompt = f"""Ты - помощник для абитуриентов ИТМО, помогающий выбрать между двумя магистерскими программами:
1. "Искусственный интеллект" - для технических специалистов в ML
2. "Управление ИИ-продуктами/AI Product" - для продакт-менеджеров в ИИ

Используй следующую информацию для ответа:
{context_text}

Вопрос абитуриента: {query}

Дай полезный и конкретный ответ на русском языке. Если нужно - порекомендуй программу исходя из интересов абитуриента."""
        
        try:
            # Попытка использовать Claude API
            if self.claude_client and self.used_tokens < self.max_tokens_per_month:
                response = self.claude_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    temperature=0.7,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Подсчет использованных токенов (приблизительно)
                self.used_tokens += len(prompt.split()) + len(response.content[0].text.split())
                
                return response.content[0].text
            else:
                logging.info("Превышен лимит токенов Claude API или API не настроен. Переключение на резервную модель...")
                return self._use_fallback_model(prompt)
                
        except Exception as e:
            logging.error(f"Ошибка при использовании Claude API: {e}")
            logging.info("Переключение на резервную модель...")
            return self._use_fallback_model(prompt)
    
    def process_query(self, query: str) -> str:
        """
        Обработка запроса пользователя
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Ответ чатбота
        """
        # Проверка на приветствие
        greetings = ["привет", "здравствуй", "добрый день", "добрый вечер", "здравствуйте", "start", "/start"]
        if any(greeting in query.lower() for greeting in greetings):
            return """Здравствуйте! Я помощник по выбору магистерской программы в ИТМО. 
            
Могу рассказать о двух программах:
• "Искусственный интеллект" - для тех, кто хочет стать ML-инженером
• "Управление ИИ-продуктами" - для будущих AI продакт-менеджеров

О чем вы хотели бы узнать? Например:
- Различия между программами
- Стоимость и бюджетные места
- Способы поступления
- Карьерные перспективы
- Требования к поступающим
- Учебные дисциплины

Также могу дать персональную рекомендацию по выбору программы!"""
        
        # Поиск релевантной информации
        relevant_info = self.retrieve_relevant_info(query, k=5)
        
        if not relevant_info:
            return "Извините, я не нашел информации по вашему запросу. Попробуйте спросить о программах, поступлении, карьерных перспективах, дисциплинах или стоимости обучения."
        
        # Генерация ответа
        response = self.generate_response(query, relevant_info)
        
        return response
    
    def recommend_program(self, user_background: Dict[str, any]) -> str:
        """
        Рекомендация программы на основе бэкграунда пользователя
        
        Args:
            user_background: Словарь с информацией о пользователе
                
        Returns:
            Рекомендация с обоснованием
        """
        ai_score = 0
        ai_product_score = 0
        
        # Подсчет баллов для каждой программы
        if user_background.get('technical_skills', False):
            ai_score += 2
            ai_product_score += 1
            
        if user_background.get('management_interest', False):
            ai_product_score += 2
            
        if user_background.get('programming_experience', False):
            ai_score += 2
            ai_product_score += 1
            
        if user_background.get('ml_knowledge', False):
            ai_score += 1
            ai_product_score += 1
            
        if user_background.get('product_experience', False):
            ai_product_score += 2
        
        # Генерация рекомендации
        if ai_score > ai_product_score:
            recommendation = """На основе вашего профиля я рекомендую программу **"Искусственный интеллект"**.

Почему эта программа вам подходит:
• У вас есть технические навыки и опыт программирования - это отличная база для углубления в ML
• Программа позволит стать ML Engineer или Data Engineer уровня Middle за 2 года
• Вы будете работать над реальными проектами компаний (X5, Ozon, МТС, Sber AI)
• Возможность выбрать специализацию: ML Engineering, Data Engineering, AI Development
• Зарплатные ожидания: 170-300 тыс. руб. для Middle-специалиста

Программа включает глубокое изучение алгоритмов ML, работу с большими данными и развертывание моделей в продакшн.

Рекомендуемые дисциплины по выбору:
- MLOps и инфраструктура ML
- Компьютерное зрение или NLP (в зависимости от интересов)
- Reinforcement Learning
- Edge AI для работы с встраиваемыми системами"""
        
        elif ai_product_score > ai_score:
            recommendation = """На основе вашего профиля я рекомендую программу **"Управление ИИ-продуктами/AI Product"**.

Почему эта программа вам подходит:
• Вас интересует продуктовый менеджмент и у вас есть опыт работы с продуктами
• Программа сочетает технические знания ИИ с навыками управления продуктами
• Партнерство с Альфа-Банком дает доступ к реальным кейсам финтеха
• Возможные роли: AI Product Manager, AI Project Manager, Product Data Analyst
• Зарплатные ожидания: 150-400+ тыс. руб. через 1-3 года

Вы научитесь создавать ИИ-решения и выводить их на рынок, понимая как техническую, так и бизнес-сторону.

Рекомендуемые дисциплины по выбору:
- Growth Hacking для AI-продуктов
- Монетизация AI-решений
- Agile и Scrum для AI-проектов
- Digital Marketing с использованием ML"""
        
        else:
            recommendation = """Обе программы могут вам подойти! Давайте определимся точнее:

**"Искусственный интеллект"** выбирайте, если:
• Хотите глубоко погрузиться в технические аспекты ML
• Готовы много программировать и работать с алгоритмами
• Интересуетесь исследованиями и научными публикациями
• Хотите стать ML Engineer или Data Engineer

**"Управление ИИ-продуктами"** выбирайте, если:
• Хотите управлять разработкой ИИ-продуктов
• Интересует работа на стыке технологий и бизнеса
• Важно понимать и техническую, и продуктовую стороны
• Хотите стать AI Product Manager

Рекомендую пройти пробные курсы обеих программ или поговорить с выпускниками для окончательного выбора!"""
        
        return recommendation
    
    def get_disciplines_recommendation(self, program: str, background: Dict[str, any]) -> str:
        """
        Рекомендация дисциплин по выбору на основе бэкграунда
        
        Args:
            program: Выбранная программа ('ai' или 'ai_product')
            background: Бэкграунд пользователя
            
        Returns:
            Рекомендации по дисциплинам
        """
        if program == 'ai':
            recommendations = "**Рекомендуемые дисциплины по выбору для программы 'Искусственный интеллект':**\n\n"
            
            if background.get('programming_experience', False):
                recommendations += "• **MLOps** - для развертывания моделей в продакшн\n"
                recommendations += "• **Распределенные вычисления** - для работы с большими данными\n"
            
            if background.get('ml_knowledge', False):
                recommendations += "• **Reinforcement Learning** - передовое направление в ML\n"
                recommendations += "• **Explainable AI** - для создания интерпретируемых моделей\n"
            
            if not background.get('technical_skills', False):
                recommendations += "• **Математические основы ИИ** - усиленный курс математики\n"
                recommendations += "• **Python для Data Science** - углубленное программирование\n"
            
            recommendations += "\n**Специализации по интересам:**\n"
            recommendations += "• Computer Vision - если интересует работа с изображениями\n"
            recommendations += "• NLP - если интересует работа с текстом\n"
            recommendations += "• Биоинформатика - если есть интерес к медицине\n"
            recommendations += "• Робототехника - для работы с автономными системами\n"
            
        else:  # ai_product
            recommendations = "**Рекомендуемые дисциплины по выбору для программы 'Управление ИИ-продуктами':**\n\n"
            
            if background.get('product_experience', False):
                recommendations += "• **Growth Hacking** - для масштабирования AI-продуктов\n"
                recommendations += "• **Монетизация AI** - стратегии заработка на ML\n"
            
            if not background.get('ml_knowledge', False):
                recommendations += "• **Основы машинного обучения** - базовый технический курс\n"
                recommendations += "• **Анализ данных для PM** - работа с метриками\n"
            
            if background.get('management_interest', False):
                recommendations += "• **Agile для AI** - управление AI-проектами\n"
                recommendations += "• **Венчурные инвестиции** - для запуска стартапов\n"
            
            recommendations += "\n**Дополнительные навыки:**\n"
            recommendations += "• UX для AI - проектирование AI-интерфейсов\n"
            recommendations += "• Digital Marketing - продвижение AI-решений\n"
            recommendations += "• Legal Tech - правовые аспекты AI\n"
            recommendations += "• Поведенческая экономика - понимание пользователей\n"
        
        return recommendations