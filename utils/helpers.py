import os
import json
from datetime import datetime
from typing import Dict, List, Any


def safe_parse_date(date_value):
    if isinstance(date_value, str):
        try:
            return datetime.fromisoformat(date_value)
        except ValueError:
            return datetime.now()  # или другое значение по умолчанию
    elif isinstance(date_value, datetime):
        return date_value
    else:
        return datetime.now()  # или другое значение по умолчанию

def format_report_for_telegram(report):
    report = report.model_dump()
    formatted_text = f"📊 *{report['title']}*\n\n"
    formatted_text += f"📅 Дата: {safe_parse_date(report['date']).strftime('%d.%m.%Y %H:%M')}\n\n"
    formatted_text += f"📝 *Общая сводка:*\n{report['overall_summary']}\n\n"
    formatted_text += "📌 *Сводки по категориям:*\n\n"
    for category in report['categories']:
        formatted_text += f"*{category['category']}* ({category['news_count']} новостей):\n"
        formatted_text += f"{category['summary']}\n\n"
    return formatted_text