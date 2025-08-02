import os
import json
import time
import re
from typing import Dict, List, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class ITMOProgramsParser:
    """Парсер для извлечения информации о магистерских программах ИТМО по ИИ"""
    
    def __init__(self, logger, headless: bool = True):
        """
        Инициализация парсера
        
        Args:
            headless: Запускать ли браузер в headless режиме
        """
        self.programs_urls = {
            "ai": "https://abit.itmo.ru/program/master/ai",
            "ai_product": "https://abit.itmo.ru/program/master/ai_product"
        }

        # получение логера из контекста
        self.logger = logger
        
        # Настройка Chrome options
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Создание директории для данных
        self.data_dir = "data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
    def _init_driver(self) -> webdriver.Chrome:
        """Инициализация веб-драйвера"""
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.implicitly_wait(10)
        return driver
    
    def _safe_find_element(self, driver: webdriver.Chrome, by: By, value: str) -> Optional[str]:
        """Безопасный поиск элемента"""
        try:
            element = driver.find_element(by, value)
            return element.text.strip()
        except NoSuchElementException:
            return None
            
    def _safe_find_elements(self, driver: webdriver.Chrome, by: By, value: str) -> List[str]:
        """Безопасный поиск множества элементов"""
        try:
            elements = driver.find_elements(by, value)
            return [el.text.strip() for el in elements if el.text.strip()]
        except NoSuchElementException:
            return []
    
    def parse_program_page(self, program_key: str, url: str) -> Dict:
        """
        Парсинг страницы программы
        
        Args:
            program_key: Ключ программы (ai или ai_product)
            url: URL страницы программы
            
        Returns:
            Словарь с извлеченной информацией
        """
        driver = self._init_driver()
        program_data = {
            "program_key": program_key,
            "url": url,
            "parsed_at": datetime.now().isoformat(),
            "general_info": {},
            "admission": {},
            "career": {},
            "curriculum": {},
            "partners": [],
            "faq": []
        }
        
        try:
            self.logger.info(f"Загрузка страницы {url}")
            driver.get(url)
            time.sleep(3)  # Ждем полной загрузки
            
            # Основная информация о программе
            self.logger.info("Извлечение основной информации")
            
            # Название программы
            title = self._safe_find_element(driver, By.TAG_NAME, "h1")
            if title:
                program_data["general_info"]["title"] = title
            
            # Попробуем найти основной текст страницы
            try:
                # Сначала получим весь текст страницы для анализа
                page_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Извлекаем ключевую информацию с помощью регулярных выражений
                # Длительность
                duration_match = re.search(r'длительность[:\s]+(\d+\s*года?)', page_text, re.IGNORECASE)
                if duration_match:
                    program_data["general_info"]["duration"] = duration_match.group(1)
                
                # Стоимость
                cost_match = re.search(r'стоимость[^:]*[:\s]+(\d+\s*\d+\s*₽)', page_text, re.IGNORECASE)
                if cost_match:
                    program_data["general_info"]["cost"] = cost_match.group(1)
                
                # Форма обучения
                form_match = re.search(r'форма обучения[:\s]+(\w+)', page_text, re.IGNORECASE)
                if form_match:
                    program_data["general_info"]["form"] = form_match.group(1)
                
                # Язык обучения
                lang_match = re.search(r'язык обучения[:\s]+(\w+)', page_text, re.IGNORECASE)
                if lang_match:
                    program_data["general_info"]["language"] = lang_match.group(1)
                
                # Описание программы - ищем блок "о программе"
                about_match = re.search(r'о программе(.*?)(?=способ|карьер|партнер|$)', page_text, re.IGNORECASE | re.DOTALL)
                if about_match:
                    description = about_match.group(1).strip()
                    # Очищаем от лишних переносов строк
                    description = re.sub(r'\n+', ' ', description)
                    description = re.sub(r'\s+', ' ', description)
                    if len(description) > 50:  # Минимальная длина для валидного описания
                        program_data["general_info"]["description"] = description[:1000]  # Ограничиваем длину
                
                # Количество бюджетных мест
                budget_matches = re.findall(r'(\d+)\s*бюджетн', page_text, re.IGNORECASE)
                if budget_matches:
                    program_data["admission"]["budget_places"] = budget_matches
                
                # Контрактные места
                contract_matches = re.findall(r'(\d+)\s*контрактн', page_text, re.IGNORECASE)
                if contract_matches:
                    program_data["admission"]["contract_places"] = contract_matches
                
                # Направления подготовки
                directions = []
                direction_matches = re.findall(r'(\d{2}\.\d{2}\.\d{2})\s+([^0-9]+?)(?=\d+\s*бюджет|\d+\s*контракт|$)', page_text)
                for code, name in direction_matches:
                    directions.append({
                        "code": code.strip(),
                        "name": name.strip()
                    })
                if directions:
                    program_data["admission"]["directions"] = directions
                
                # Партнеры
                known_partners = ["X5", "Ozon", "МТС", "Sber", "Napoleon IT", "Альфа", "Татнефть", "AIRI", "DeepPavlov", "Норникель", "Genotek", "Raft"]
                found_partners = []
                for partner in known_partners:
                    if partner in page_text:
                        found_partners.append(partner)
                program_data["partners"] = found_partners
                
                # Карьерные позиции
                positions = []
                position_patterns = [
                    r'ML Engineer',
                    r'Data Engineer', 
                    r'AI Product Developer',
                    r'Data Analyst',
                    r'AI Product Manager',
                    r'AI Project Manager',
                    r'Product Data Analyst'
                ]
                for pattern in position_patterns:
                    if re.search(pattern, page_text, re.IGNORECASE):
                        positions.append(pattern)
                if positions:
                    program_data["career"]["positions"] = positions
                
                # Зарплаты
                salary_matches = re.findall(r'(\d+)[\s\-–]+(\d+)\s*(?:тыс|тысяч|000)', page_text)
                if salary_matches:
                    program_data["career"]["salary_ranges"] = [f"{s[0]}-{s[1]}" for s in salary_matches]
                
            except Exception as e:
                self.logger.error(f"Ошибка при извлечении текста: {str(e)}")
            
            # Информация в карточках (длительность, язык, стоимость и т.д.)
            info_cards = driver.find_elements(By.CSS_SELECTOR, ".program-info-card, .info-item")
            for card in info_cards:
                try:
                    label = card.find_element(By.CSS_SELECTOR, ".label, .info-label").text.strip()
                    value = card.find_element(By.CSS_SELECTOR, ".value, .info-value").text.strip()
                    
                    if "длительность" in label.lower():
                        program_data["general_info"]["duration"] = value
                    elif "язык" in label.lower():
                        program_data["general_info"]["language"] = value
                    elif "стоимость" in label.lower():
                        program_data["general_info"]["cost"] = value
                    elif "форма" in label.lower():
                        program_data["general_info"]["form"] = value
                except:
                    continue
            
            # Описание программы
            description_selectors = [
                ".program-description",
                ".about-program", 
                "[class*='description']"
            ]
            
            for selector in description_selectors:
                description = self._safe_find_element(driver, By.CSS_SELECTOR, selector)
                if description:
                    program_data["general_info"]["description"] = description
                    break
            
            # Направления подготовки и количество мест
            self.logger.info("Извлечение информации о направлениях подготовки")
            
            directions = []
            direction_sections = driver.find_elements(By.CSS_SELECTOR, ".direction-item, .program-direction")
            
            for section in direction_sections:
                try:
                    direction = {
                        "code": self._safe_find_element(section, By.CSS_SELECTOR, ".direction-code"),
                        "name": self._safe_find_element(section, By.CSS_SELECTOR, ".direction-name"),
                        "budget_places": self._safe_find_element(section, By.CSS_SELECTOR, ".budget-places"),
                        "contract_places": self._safe_find_element(section, By.CSS_SELECTOR, ".contract-places"),
                        "target_places": self._safe_find_element(section, By.CSS_SELECTOR, ".target-places")
                    }
                    directions.append(direction)
                except:
                    continue
                    
            if directions:
                program_data["admission"]["directions"] = directions
            
            # Способы поступления
            self.logger.info("Извлечение способов поступления")
            
            admission_methods = []
            admission_sections = driver.find_elements(By.CSS_SELECTOR, ".admission-method, .admission-way")
            
            for section in admission_sections:
                try:
                    method = {
                        "title": self._safe_find_element(section, By.CSS_SELECTOR, "h3, h4, .method-title"),
                        "description": self._safe_find_element(section, By.CSS_SELECTOR, "p, .method-description")
                    }
                    if method["title"]:
                        admission_methods.append(method)
                except:
                    continue
                    
            program_data["admission"]["methods"] = admission_methods
            
            # Карьерные перспективы
            self.logger.info("Извлечение информации о карьере")
            
            career_section = None
            career_selectors = [
                ".career-section",
                "#career",
                "[class*='career']"
            ]
            
            for selector in career_selectors:
                try:
                    career_section = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
                    
            # Если не нашли по селектору, ищем по тексту заголовка
            if not career_section:
                try:
                    # Ищем все h2 элементы и проверяем текст
                    h2_elements = driver.find_elements(By.TAG_NAME, "h2")
                    for h2 in h2_elements:
                        if "карьера" in h2.text.lower():
                            # Находим родительский элемент секции
                            career_section = h2.find_element(By.XPATH, "./parent::*")
                            break
                except:
                    pass
                    
            if career_section:
                career_text = career_section.text
                program_data["career"]["description"] = career_text
                
                # Извлечение позиций и зарплат
                salary_pattern = r'(\d+)\s*(?:000|тыс|тысяч)'
                salaries = re.findall(salary_pattern, career_text)
                if salaries:
                    program_data["career"]["salary_range"] = salaries
                    
                # Позиции
                positions = []
                position_keywords = ["Engineer", "Manager", "Developer", "Analyst", "Lead"]
                for keyword in position_keywords:
                    if keyword in career_text:
                        # Извлекаем контекст вокруг ключевого слова
                        pattern = rf'[\w\s]*{keyword}[\w\s]*'
                        found_positions = re.findall(pattern, career_text)
                        positions.extend(found_positions)
                        
                if positions:
                    program_data["career"]["positions"] = list(set(positions))
            
            # Партнеры программы
            self.logger.info("Извлечение партнеров")
            
            partners_section = None
            partners_selectors = [
                ".partners-section",
                ".program-partners",
                "[class*='partner']"
            ]
            
            for selector in partners_selectors:
                try:
                    partners_section = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
                    
            # Если не нашли по селектору, ищем по тексту заголовка
            if not partners_section:
                try:
                    h2_elements = driver.find_elements(By.TAG_NAME, "h2")
                    for h2 in h2_elements:
                        if "партнер" in h2.text.lower():
                            partners_section = h2.find_element(By.XPATH, "./parent::*")
                            break
                except:
                    pass
                    
            if partners_section:
                # Попробуем найти изображения партнеров
                partner_images = partners_section.find_elements(By.TAG_NAME, "img")
                for img in partner_images:
                    alt_text = img.get_attribute("alt")
                    if alt_text and alt_text not in ["", "partner image"]:
                        program_data["partners"].append(alt_text)
                        
                # Также ищем текстовые упоминания
                partner_text = partners_section.text
                known_partners = ["X5", "Ozon", "МТС", "Sber", "Napoleon IT", "Альфа", "Татнефть"]
                for partner in known_partners:
                    if partner in partner_text and partner not in program_data["partners"]:
                        program_data["partners"].append(partner)
            
            # FAQ секция
            self.logger.info("Извлечение FAQ")
            
            faq_section = None
            faq_selectors = [
                ".faq-section",
                "#faq",
                "[class*='faq']"
            ]
            
            for selector in faq_selectors:
                try:
                    faq_section = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
                    
            # Если не нашли по селектору, ищем по тексту заголовка
            if not faq_section:
                try:
                    h2_elements = driver.find_elements(By.TAG_NAME, "h2")
                    for h2 in h2_elements:
                        if "часто задаваемые вопросы" in h2.text.lower() or "faq" in h2.text.lower():
                            faq_section = h2.find_element(By.XPATH, "./parent::*")
                            break
                except:
                    pass
                    
            if faq_section:
                faq_items = faq_section.find_elements(By.CSS_SELECTOR, ".faq-item, .accordion-item")
                for item in faq_items:
                    try:
                        question = self._safe_find_element(item, By.CSS_SELECTOR, ".question, .accordion-header")
                        answer = self._safe_find_element(item, By.CSS_SELECTOR, ".answer, .accordion-body")
                        if question and answer:
                            program_data["faq"].append({
                                "question": question,
                                "answer": answer
                            })
                    except:
                        continue
            
            # Учебный план (попытка найти ссылку)
            self.logger.info("Поиск информации об учебном плане")
            
            curriculum_link = None
            
            # Ищем ссылки с текстом "учебный план"
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    link_text = link.text.lower()
                    link_href = link.get_attribute("href") or ""
                    
                    if "учебный план" in link_text or "curriculum" in link_href or "plan" in link_href:
                        curriculum_link = link
                        program_data["curriculum"]["link"] = link.get_attribute("href")
                        break
            except:
                pass
            
            # Особенности программы
            self.logger.info("Извлечение особенностей программы")
            
            features = []
            
            # Ищем списки с особенностями
            feature_lists = driver.find_elements(By.CSS_SELECTOR, "ul li, .feature-item")
            for item in feature_lists[:20]:  # Ограничиваем количество
                text = item.text.strip()
                if len(text) > 10 and len(text) < 300:  # Фильтруем по длине
                    features.append(text)
                    
            if features:
                program_data["general_info"]["features"] = features
            
            self.logger.info(f"Парсинг программы {program_key} завершен успешно")
            
        except Exception as e:
            self.logger.error(f"Ошибка при парсинге {url}: {str(e)}")
            program_data["error"] = str(e)
            
        finally:
            driver.quit()
            
        return program_data
    
    def parse_all_programs(self) -> Dict[str, Dict]:
        """Парсинг всех программ"""
        all_data = {}
        
        for program_key, url in self.programs_urls.items():
            self.logger.info(f"Начинаем парсинг программы: {program_key}")
            program_data = self.parse_program_page(program_key, url)
            all_data[program_key] = program_data
            
            # Сохраняем данные для каждой программы отдельно
            output_file = os.path.join(self.data_dir, f"{program_key}_data.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(program_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Данные сохранены в {output_file}")
            
            # Небольшая пауза между запросами
            time.sleep(2)
        
        # Сохраняем объединенные данные
        combined_file = os.path.join(self.data_dir, "all_programs_data.json")
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Объединенные данные сохранены в {combined_file}")
        
        return all_data
    
    def create_knowledge_base(self, parsed_data: Dict[str, Dict]) -> List[Dict[str, str]]:
        """
        Создание базы знаний из спарсенных данных
        
        Args:
            parsed_data: Спарсенные данные программ
            
        Returns:
            База знаний в формате для чатбота
        """
        knowledge_base = []
        
        for program_key, program_data in parsed_data.items():
            program_name = "Искусственный интеллект" if program_key == "ai" else "Управление ИИ-продуктами/AI Product"
            
            # Общая информация
            if program_data.get("general_info", {}).get("description"):
                knowledge_base.append({
                    "id": f"{program_key}_general",
                    "text": f"Программа '{program_name}': {program_data['general_info']['description']}",
                    "program": program_key,
                    "type": "general"
                })
            
            # Информация о стоимости и форме обучения
            general_info = program_data.get("general_info", {})
            if general_info.get("cost") or general_info.get("duration"):
                info_parts = []
                if general_info.get("duration"):
                    info_parts.append(f"Длительность: {general_info['duration']}")
                if general_info.get("cost"):
                    info_parts.append(f"Стоимость: {general_info['cost']}")
                if general_info.get("form"):
                    info_parts.append(f"Форма обучения: {general_info['form']}")
                    
                knowledge_base.append({
                    "id": f"{program_key}_info",
                    "text": f"Программа '{program_name}'. {'. '.join(info_parts)}",
                    "program": program_key,
                    "type": "info"
                })
            
            # Направления подготовки
            if program_data.get("admission", {}).get("directions"):
                directions_text = f"Программа '{program_name}' имеет следующие направления подготовки: "
                for direction in program_data["admission"]["directions"]:
                    if direction.get("name"):
                        parts = [direction["name"]]
                        if direction.get("code"):
                            parts.append(f"код {direction['code']}")
                        if direction.get("budget_places"):
                            parts.append(f"{direction['budget_places']} бюджетных мест")
                        if direction.get("contract_places"):
                            parts.append(f"{direction['contract_places']} контрактных мест")
                        directions_text += f"{', '.join(parts)}. "
                        
                knowledge_base.append({
                    "id": f"{program_key}_directions",
                    "text": directions_text,
                    "program": program_key,
                    "type": "admission"
                })
            
            # Способы поступления
            if program_data.get("admission", {}).get("methods"):
                for i, method in enumerate(program_data["admission"]["methods"]):
                    if method.get("title") and method.get("description"):
                        knowledge_base.append({
                            "id": f"{program_key}_admission_{i}",
                            "text": f"Программа '{program_name}' - способ поступления '{method['title']}': {method['description']}",
                            "program": program_key,
                            "type": "admission"
                        })
            
            # Карьерные перспективы
            if program_data.get("career", {}).get("description"):
                knowledge_base.append({
                    "id": f"{program_key}_career",
                    "text": f"Карьерные перспективы программы '{program_name}': {program_data['career']['description']}",
                    "program": program_key,
                    "type": "career"
                })
            
            # Партнеры
            if program_data.get("partners"):
                partners_text = f"Партнеры программы '{program_name}': {', '.join(program_data['partners'])}"
                knowledge_base.append({
                    "id": f"{program_key}_partners",
                    "text": partners_text,
                    "program": program_key,
                    "type": "partners"
                })
            
            # FAQ
            for i, faq_item in enumerate(program_data.get("faq", [])):
                if faq_item.get("question") and faq_item.get("answer"):
                    knowledge_base.append({
                        "id": f"{program_key}_faq_{i}",
                        "text": f"Программа '{program_name}' - Вопрос: {faq_item['question']} Ответ: {faq_item['answer']}",
                        "program": program_key,
                        "type": "faq"
                    })
            
            # Особенности программы
            if general_info.get("features"):
                features_text = f"Особенности программы '{program_name}': " + "; ".join(general_info["features"][:5])
                knowledge_base.append({
                    "id": f"{program_key}_features",
                    "text": features_text,
                    "program": program_key,
                    "type": "features"
                })
        
        # Сохраняем базу знаний
        kb_file = os.path.join(self.data_dir, "knowledge_base.json")
        with open(kb_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
        self.logger.info(f"База знаний сохранена в {kb_file}")
        
        return knowledge_base
