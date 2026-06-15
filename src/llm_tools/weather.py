"""天气查询工具 — 通过 wttr.in 获取今天/明天天气"""
import requests
from llm_tools import register


@register(
    name="get_weather",
    description="查询指定城市今天或明天的天气。返回天气状况、温度（最低/最高/平均）、湿度、风速。",
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如 Beijing、上海、Tokyo",
            },
            "date": {
                "type": "string",
                "enum": ["today", "tomorrow"],
                "description": "查询日期：today=今天（默认），tomorrow=明天",
            },
        },
        "required": ["city"],
    },
)
def get_weather(args: dict) -> str:
    """调用 wttr.in JSON API，解析后返回天气摘要"""
    city = args["city"]
    date = args.get("date", "today")

    try:
        resp = requests.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
            timeout=10,
            headers={"Accept-Language": "zh-CN"},
        )
        resp.encoding = "utf-8"
        data = resp.json()

        weather_list = data.get("weather", [])
        if not weather_list:
            return f"未找到 {city} 的天气信息"

        # weather[0]=今天, weather[1]=明天, weather[2]=后天
        idx = 0 if date == "today" else 1
        if idx >= len(weather_list):
            return f"暂无 {city} {date} 的预报数据"

        day = weather_list[idx]
        date_str = day["date"]
        avg_temp = day.get("avgtempC", "?")
        min_temp = day.get("mintempC", "?")
        max_temp = day.get("maxtempC", "?")

        # 从 hourly 中取第一条的天气描述作为代表
        hourly = day.get("hourly", [])
        weather_desc = (
            hourly[0]["weatherDesc"][0]["value"]
            if hourly and hourly[0].get("weatherDesc")
            else "未知"
        )

        # 尝试获取湿度、风速（wttr.in JSON 中 current_condition 才有这些字段）
        current = data.get("current_condition", [])
        humidity = current[0].get("humidity", "?") if current else "?"
        wind = current[0].get("winddir16Point", "") + " " + current[0].get("windspeedKmph", "?") + "km/h" if current else "?"

        label = "今天" if date == "today" else "明天"
        parts = [
            f"{city} {label}（{date_str}）天气: {weather_desc}",
            f"温度: {min_temp}°C ~ {max_temp}°C（平均 {avg_temp}°C）",
        ]
        if date == "today":
            parts.append(f"湿度: {humidity}%, 风速: {wind}")

        return "，".join(parts)
    except requests.exceptions.RequestException:
        return f"查询天气失败：无法连接天气服务"
    except Exception as e:
        return f"查询天气失败: {e}"
