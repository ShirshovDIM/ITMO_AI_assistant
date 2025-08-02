"""
Базовые тесты для проверки настройки окружения.
"""

# import pytest
import sys


def test_python_version():
    """Проверка версии Python."""
    assert sys.version_info >= (3, 12), "Требуется Python 3.12 или выше"
