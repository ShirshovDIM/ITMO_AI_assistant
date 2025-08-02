import logging
from itmo_program_parser import ITMOProgramsParser

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Основная функция для запуска парсера"""
    parser = ITMOProgramsParser(logger, headless=True)
    
    try:
        # Парсим все программы
        logger.info("Начинаем парсинг программ ИТМО...")
        parsed_data = parser.parse_all_programs()
        
        # Создаем базу знаний
        logger.info("Создаем базу знаний...")
        knowledge_base = parser.create_knowledge_base(parsed_data)
        
        logger.info(f"Парсинг завершен! Извлечено {len(knowledge_base)} элементов базы знаний")
        
        # Выводим статистику
        print("\nСтатистика парсинга:")
        for program_key, program_data in parsed_data.items():
            print(f"\nПрограмма: {program_key}")
            print(f"- Общая информация: {'✓' if program_data.get('general_info') else '✗'}")
            print(f"- Направления: {len(program_data.get('admission', {}).get('directions', []))}")
            print(f"- Способы поступления: {len(program_data.get('admission', {}).get('methods', []))}")
            print(f"- Партнеры: {len(program_data.get('partners', []))}")
            print(f"- FAQ: {len(program_data.get('faq', []))}")
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    main()
