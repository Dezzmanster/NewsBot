from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class News(BaseModel):
    """Модель данных для новостей"""
    id: str = Field(description="Уникальный идентификатор новости")
    channel: str = Field(description="Название канала, из которого получена новость")
    text: str = Field(description="Текст новости")
    date: str = Field(description="Дата и время публикации новости")
    media_urls: List[str] = Field(default=[], description="Список URL медиафайлов, прикрепленных к новости")
    views: Optional[int] = Field(default=None, description="Количество просмотров новости, если доступно")

class Entities(BaseModel):
    """Именованные сущности, найденные в тексте новости"""
    people: List[str] = Field(description="Список людей, упомянутых в тексте, если нет, то вставляй пустой список")
    organizations: List[str] = Field(description="Список организаций, упомянутых в тексте, если нет, то вставляй пустой список")
    places: List[str] = Field(description="Список мест, упомянутых в тексте, если нет, то вставляй пустой список")

class SimpleAnalyzerOutput(BaseModel):
    """Результат анализа новости, включающий ключевые слова, тональность и сущности"""
    keywords: List[str] = Field(description="Список из 5-7 ключевых слов")
    sentiment: str = Field(description="Тональность текста (позитивная, нейтральная, негативная)")
    # entities: Entities = Field(description="Именованные сущности в тексте")
    importance_score: float = Field(description="Оценка важности новости по шкале от 0 до 1")
    # news: News = Field(description="Исходная новость")

class AnalyzerOutput(SimpleAnalyzerOutput):
    """Результат анализа новости, включающий ключевые слова, тональность и сущности"""
    news: News = Field(description="Исходная новость")

class NewsCategory(str, Enum):
    POLITICS = "Политика"
    ECONOMICS = "Экономика"
    TECHNOLOGY = "Технологии"
    SCIENCE = "Наука"
    SPORTS = "Спорт"
    CULTURE = "Культура"
    SOCIETY = "Общество"
    INCIDENTS = "Происшествия"

class CategoryOutput(BaseModel):
    """Категория новости"""
    category: NewsCategory = Field(description="Категория новости")

class ClassifierOutput(BaseModel):
    """Структурированный вывод для агента-классификатора"""
    category: str = Field(description="Категория новости (Политика, Экономика, Технологии, Наука, Спорт, Культура, Общество, Происшествия)")
    analysis: AnalyzerOutput = Field(description="Результат анализа новости")

class CategorySummary(BaseModel):
    """Сводка по категории новостей"""
    category: str = Field(description="Название категории")
    summary: str = Field(description="Краткая сводка по новостям категории")
    news_count: int = Field(description="Количество новостей в категории")

class ReportCategory(BaseModel):
    """Расширенная категория для отчета с новостями"""
    category: str = Field(description="Название категории")
    summary: str = Field(description="Краткая сводка по новостям категории")
    news_count: int = Field(description="Количество новостей в категории")
    news: List[News] = Field(description="Список новостей в категории")

class Report(BaseModel):
    """Модель данных для отчетов"""
    id: str = Field(description="Уникальный идентификатор отчета")
    title: str = Field(description="Заголовок отчета строго в формате Markdown")
    date: datetime = Field(description="Дата создания отчета")
    period: str = Field(description="Период, за который создан отчет")
    categories: List[ReportCategory] = Field(description="Сводки по категориям строго в формате Markdown")
    overall_summary: str = Field(description="Общая сводка по всем новостям строго в формате Markdown")
