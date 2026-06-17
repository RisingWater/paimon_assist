"""定时提醒工具 — 添加、列出、删除提醒"""
import logging
from llm_tools import register
import db

_log = logging.getLogger(__name__)


@register(
    name="add_reminder",
    description=(
        "添加一个定时提醒或定时任务。支持一次性、每天、每月（公历/农历）。"
        "例如：'晚上9点提醒我吃药'、'明天下午3点开会'、'每月初一早上8点烧香（农历）'。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "提醒内容，如'提醒王旭吃药'"},
            "rtype": {
                "type": "string",
                "enum": ["once", "daily", "monthly"],
                "description": "once=一次性, daily=每天, monthly=每月",
            },
            "datetime": {
                "type": "string",
                "description": "时间：once用'2026-06-18 21:00'，daily用'21:00'，monthly用'15 21:00'（15号21点）",
            },
            "lunar": {"type": "boolean", "description": "monthly 时是否为农历日期"},
        },
        "required": ["content", "rtype", "datetime"],
    },
)
def add_reminder(args: dict) -> str:
    try:
        uid = db._ensure_reminder_user()
        rid = db.add_reminder(
            uid, args["content"], args["rtype"],
            args["datetime"], args.get("lunar", False),
        )
        return f"已添加提醒 #{rid}：{args['content']}"
    except Exception as e:
        return f"添加提醒失败：{e}"


@register(
    name="list_reminders",
    description="列出所有未完成的定时提醒。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_reminders(_args: dict = {}) -> str:
    try:
        reminders = db.list_reminders()
        if not reminders:
            return "没有待执行的提醒"
        lines = []
        for r in reminders:
            lunar_tag = "农历" if r["lunar"] else ""
            type_cn = {"once": "一次性", "daily": "每天", "monthly": "每月"}
            lines.append(
                f"#{r['id']} [{type_cn.get(r['rtype'], r['rtype'])}{lunar_tag}] "
                f"{r['datetime']} — {r['content']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败：{e}"


@register(
    name="delete_reminder",
    description="删除一个定时提醒。",
    parameters={
        "type": "object",
        "properties": {
            "reminder_id": {"type": "integer", "description": "提醒编号（#id）"}
        },
        "required": ["reminder_id"],
    },
)
def delete_reminder(args: dict) -> str:
    try:
        db.delete_reminder(args["reminder_id"])
        return f"已删除提醒 #{args['reminder_id']}"
    except Exception as e:
        return f"删除失败：{e}"
