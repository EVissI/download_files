import re
from typing import Optional, Tuple

class EmailValidator:
    """
    Валидатор для проверки корректности email-адреса.
    Соответствует основным требованиям RFC 5322 с некоторыми упрощениями для практического использования.
    """

    # Регулярное выражение для валидации email
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )

    @staticmethod
    def validate(email: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет валидность email-адреса.

        Args:
            email (str): Email-адрес для проверки.

        Returns:
            Tuple[bool, Optional[str]]: Кортеж (валидно ли, сообщение об ошибке или None).
        """
        if not isinstance(email, str):
            return False, "Email должен быть строкой."

        # Удаляем лишние пробелы
        email = email.strip()

        # Проверка на пустую строку
        if not email:
            return False, "Email не может быть пустым."

        # Проверка длины (максимум 254 символа согласно RFC 5321)
        if len(email) > 254:
            return False, "Email слишком длинный (максимум 254 символа)."

        # Проверка на соответствие регулярному выражению
        if not EmailValidator.EMAIL_REGEX.match(email):
            return False, "Неверный формат email-адреса."

        # Дополнительная проверка на наличие запрещенных символов или доменов (опционально)
        try:
            local_part, domain = email.split('@')
            if len(local_part) > 64:  # Максимальная длина локальной части
                return False, "Локальная часть email слишком длинная (максимум 64 символа)."
            if not domain:
                return False, "Домен не указан."
        except ValueError:
            return False, "Email должен содержать символ @."

        return True, None