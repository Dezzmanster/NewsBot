from typing import List, Dict, Any, TypedDict, Union, Optional
from typing_extensions import Annotated
import operator
import uuid
from datetime import datetime, date, timedelta

from telethon import TelegramClient

# Импорт компонентов langgraph
from langgraph.graph import StateGraph, END, START
from langchain_gigachat import GigaChat
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langsmith.run_helpers import traceable
from dotenv import load_dotenv

# Настройка логирования
import logging

# Импорт схем данных
from models.schemas import (
    News,
    SimpleAnalyzerOutput,
    AnalyzerOutput,
    ClassifierOutput,
    CategoryOutput,
    CategorySummary,
    ReportCategory,
    Report
)

# Импорт конфигов
from config.settings import (
    GIGACHAT,
    TELEGRAM,
    DEFAULT_LIMIT_PER_CHANNEL,
)

# Импорт необходимых промптов
from prompts.agents_prompts import (
    ANALYZER_PROMPT,
    CLASSIFIER_PROMPT,
    SUMMARIZER_PROMPT,
    REPORTER_PROMPT,
    ERROR_PROMPT
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID = int(TELEGRAM["API_ID"])
API_HASH = TELEGRAM["API_HASH"]
SESSION_NAME = "newsbot_session"

LIMIT_PER_CHANNEL = int(DEFAULT_LIMIT_PER_CHANNEL)

# Инициализация модели GigaChat с обработкой ошибок и повторными попытками
gigachat = GigaChat(
    credentials=GIGACHAT['API_KEY'],
    verify_ssl_certs=GIGACHAT['VERIFY_SSL'],
    model=GIGACHAT['MODEL'],
    scope=GIGACHAT['SCOPE'],
    profanity_check=False,
)


# Определение структуры состояния графа
class GraphState(TypedDict):
    channels: Annotated[List[str], operator.add]
    limit_per_channel: int
    collected_news: List[News]
    analyzed_news: List[AnalyzerOutput]
    categorized_news: Dict[str, List[ClassifierOutput]]
    summaries: List[CategorySummary]
    report: Report
    errors: List[str]


async def get_real_news(channel: str, limit: int) -> List[News]:
    """Получение новостей из Telegram канала с фильтрацией по дате"""
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        messages = []

        async for msg in client.iter_messages(channel, limit=limit):
            if msg.text:
                news = News(
                    id=str(msg.id),
                    channel=channel,
                    text=msg.text,
                    date=str(msg.date),
                    media_urls=[],
                    views=msg.views if hasattr(msg, "views") else None
                )
                messages.append(news)

        return messages


# Определение узлов графа (агентов)
@traceable(name="collector_agent")
async def collector_agent(state: GraphState) -> GraphState:
    """Агент для сбора новостей с фильтрацией по дате"""
    logger.info(f"Collecting news from {state['channels']} with limit {state['limit_per_channel']}")

    try:
        collected_news = []
        for channel in state["channels"]:
            real_news = await get_real_news(
                channel,
                state["limit_per_channel"],
            )
            collected_news.extend(real_news)

        return {**state, "collected_news": collected_news}
    except Exception as e:
        logger.error(f"Error in collector_agent: {e}")
        return {**state, "errors": state["errors"] + [f"Collector error: {str(e)}"]}


@traceable(name="analyzer_agent")
def analyzer_agent(state: GraphState) -> GraphState:
    """Агент для анализа новостей с использованием структурированного вывода"""
    logger.info(f"Analyzing {len(state['collected_news'])} news items")
    try:
        analyzed_news = []

        # Создаем модель со структурированным выводом
        structured_gigachat = gigachat.with_structured_output(SimpleAnalyzerOutput)

        prompt = ChatPromptTemplate.from_template(ANALYZER_PROMPT)

        for news in state["collected_news"]:
            chain = prompt | structured_gigachat
            try:
                analysis = chain.invoke({"text": news.text})
                full_analysis = AnalyzerOutput(
                    keywords=analysis.keywords,
                    sentiment=analysis.sentiment,
                    importance_score=analysis.importance_score,
                    news=news
                )
                # Добавляем новость к анализу
                analyzed_news.append(full_analysis)
            except Exception as analysis_error:
                logger.warning(f"Error in analysis: {analysis_error}. Creating fallback analysis.")

                # Резервный вариант: создаем базовый анализ
                fallback_analysis = AnalyzerOutput(
                    keywords=["новость"],
                    sentiment="нейтральная",
                    entities={"people": [], "organizations": [], "places": []},
                    importance_score=0.5,
                    news=news
                )
                analyzed_news.append(fallback_analysis)

        return {**state, "analyzed_news": analyzed_news}
    except Exception as e:
        logger.error(f"Error in analyzer_agent: {e}")
        return {**state, "errors": state["errors"] + [f"Analyzer error: {str(e)}"]}


@traceable(name="classifier_agent")
def classifier_agent(state: GraphState) -> GraphState:
    """Агент для классификации новостей с использованием структурированного вывода"""
    logger.info(f"Classifying {len(state['analyzed_news'])} news items")
    try:
        structured_gigachat = gigachat.with_structured_output(CategoryOutput)

        prompt = ChatPromptTemplate.from_template(CLASSIFIER_PROMPT)

        categorized_news = {}

        for analysis in state["analyzed_news"]:
            chain = prompt | structured_gigachat
            # Выполняем классификацию
            try:
                result = chain.invoke({"text": analysis.news.text})
                category = result.category.value

                # Создаем объект ClassifierOutput
                classification = ClassifierOutput(
                    category=category,
                    analysis=analysis
                )

                # Добавляем классификацию в соответствующую категорию
                if category not in categorized_news:
                    categorized_news[category] = []

                categorized_news[category].append(classification)
            except Exception as classify_error:
                logger.warning(f"Error in classification: {classify_error}. Using fallback category.")

                # Резервный вариант: используем категорию "Общество"
                category = "Общество"

                # Создаем объект ClassifierOutput
                classification = ClassifierOutput(
                    category=category,
                    analysis=analysis
                )

                # Добавляем классификацию в соответствующую категорию
                if category not in categorized_news:
                    categorized_news[category] = []

                categorized_news[category].append(classification)

        return {**state, "categorized_news": categorized_news}
    except Exception as e:
        logger.error(f"Error in classifier_agent: {e}")
        return {**state, "errors": state["errors"] + [f"Classifier error: {str(e)}"]}


@traceable(name="summarizer_agent")
def summarizer_agent(state: GraphState) -> GraphState:
    """Агент для суммаризации новостей с использованием структурированного вывода"""
    logger.info(f"Summarizing {len(state['categorized_news'])} categories")
    try:
        # Создаем модель со структурированным выводом
        structured_gigachat = gigachat.with_structured_output(CategorySummary)
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_PROMPT)
        chain = prompt | structured_gigachat

        summaries = []

        for category, news_list in state["categorized_news"].items():
            all_texts = [item.analysis.news.text for item in news_list]
            combined_text = "\n\n".join(all_texts)

            # Выполняем суммаризацию
            try:
                summary = chain.invoke({
                    "text": combined_text,
                    "category": category,
                    "count": len(news_list)
                })

                summaries.append(summary)
            except Exception as summary_error:
                logger.warning(f"Error in summarization: {summary_error}. Creating fallback summary.")

                # Резервный вариант: создаем базовую сводку
                fallback_summary = CategorySummary(
                    category=category,
                    summary=f"Новости категории {category}",
                    news_count=len(news_list)
                )

                summaries.append(fallback_summary)

        return {**state, "summaries": summaries}
    except Exception as e:
        logger.error(f"Error in summarizer_agent: {e}")
        return {**state, "errors": state["errors"] + [f"Summarizer error: {str(e)}"]}


@traceable(name="reporter_agent")
def reporter_agent(state: GraphState) -> GraphState:
    """Агент для формирования отчета с учетом выбранной даты"""
    logger.info(f"Generating report with {len(state['summaries'])} summaries")

    try:
        # Создаем категории отчета
        report_categories = []
        all_summaries = []

        for summary in state["summaries"]:
            category = summary.category
            news_list = state["categorized_news"].get(category, [])

            # Создаем список новостей для категории
            category_news = [item.analysis.news for item in news_list]

            # Создаем категорию отчета
            report_category = ReportCategory(
                category=category,
                summary=summary.summary,
                news_count=summary.news_count,
                news=category_news
            )

            report_categories.append(report_category)
            all_summaries.append(f"Категория '{category}' ({summary.news_count} новостей): {summary.summary}")

        # Генерируем общую сводку
        combined_text = "\n\n".join(all_summaries)
        prompt = ChatPromptTemplate.from_template(REPORTER_PROMPT)
        chain = prompt | gigachat | StrOutputParser()

        # Выполняем генерацию общей сводки
        overall_summary = chain.invoke({"text": combined_text})

        # Создаем отчет
        report = Report(
            id=str(uuid.uuid4()),
            title=f"Дайджест новостей",
            date=datetime.now(),
            period="день",
            categories=report_categories,
            overall_summary=overall_summary
        )

        return {**state, "report": report}
    except Exception as e:
        logger.error(f"Error in reporter_agent: {e}")
        return {**state, "errors": state["errors"] + [f"Reporter error: {str(e)}"]}


def has_errors(state: GraphState) -> str:
    """Функция проверки наличия ошибок"""
    if state["errors"]:
        return "error_handler"
    return "continue"


def error_handler(state: GraphState) -> GraphState:
    """Обработчик ошибок"""
    logger.error(f"Errors occurred: {state['errors']}")

    # Создаем отчет с ошибкой
    error_report = Report(
        id=str(uuid.uuid4()),
        title="Ошибка при формировании дайджеста",
        date=datetime.now(),
        period="день",
        categories=[],
        overall_summary=f"Произошли ошибки: {', '.join(state['errors'])}"
    )
    return {**state, "report": error_report}


def create_agent_graph():
    """Создание графа агентов"""
    graph = StateGraph(GraphState)

    # 1. Добавляем все узлы
    graph.add_node("collector", collector_agent)
    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("classifier", classifier_agent)
    graph.add_node("summarizer", summarizer_agent)
    graph.add_node("reporter", reporter_agent)
    graph.add_node("error_handler", error_handler)

    # 2. Добавляем ребра
    graph.add_edge(START, "collector")
    graph.add_edge("collector", "analyzer")
    graph.add_edge("analyzer", "classifier")
    graph.add_edge("classifier", "summarizer")
    graph.add_edge("summarizer", "reporter")
    graph.add_edge("reporter", END)

    # 3. Добавляем условные ребра для обработки ошибок
    graph.add_conditional_edges(
        "collector",
        has_errors,
        {
            "error_handler": "error_handler",
            "continue": "analyzer"
        }
    )

    graph.add_conditional_edges(
        "analyzer",
        has_errors,
        {
            "error_handler": "error_handler",
            "continue": "classifier"
        }
    )

    graph.add_conditional_edges(
        "classifier",
        has_errors,
        {
            "error_handler": "error_handler",
            "continue": "summarizer"
        }
    )

    graph.add_conditional_edges(
        "summarizer",
        has_errors,
        {
            "error_handler": "error_handler",
            "continue": "reporter"
        }
    )

    graph.add_edge("error_handler", END)
    return graph.compile()


@traceable(name="process_news_channels")
async def process_news_channels(
        channels: List[str],
        limit_per_channel: int = LIMIT_PER_CHANNEL,
):
    """Обработка новостных каналов с опциональной фильтрацией по дате"""
    agent_graph = create_agent_graph()

    initial_state = {
        "channels": channels,
        "limit_per_channel": limit_per_channel,
        "collected_news": [],
        "analyzed_news": [],
        "categorized_news": {},
        "summaries": [],
        "report": None,
        "errors": [],
    }

    logger.info(f"Starting processing of {len(channels)} channels")

    # Запускаем граф агентов
    final_state = await agent_graph.ainvoke(initial_state)

    logger.info("Processing completed")
    return final_state["report"]
