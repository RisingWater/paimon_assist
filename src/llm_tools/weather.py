"""天气查询工具 — 通过 wttr.in 获取今天/明天天气"""
import requests
from llm_tools import register

# wttr.in 天气描述 → 中文
_DESC_CN: dict[str, str] = {
    "Sunny": "晴",
    "Clear": "晴",
    "Partly cloudy": "多云",
    "Partly Cloudy": "多云",
    "Cloudy": "阴",
    "Overcast": "阴",
    "Mist": "薄雾",
    "Fog": "雾",
    "Freezing fog": "冻雾",
    "Patchy rain nearby": "局部阵雨",
    "Patchy rain possible": "局部阵雨",
    "Patchy light rain": "小到中雨",
    "Light rain": "小雨",
    "Moderate rain": "中雨",
    "Moderate rain at times": "间歇中雨",
    "Heavy rain": "大雨",
    "Heavy rain at times": "间歇大雨",
    "Torrential rain shower": "暴雨",
    "Light drizzle": "毛毛雨",
    "Patchy light drizzle": "局部毛毛雨",
    "Light rain shower": "小阵雨",
    "Patchy light rain in area with thunder": "雷阵雨",
    "Moderate or heavy rain shower": "中到大阵雨",
    "Thundery outbreaks in nearby": "周边雷暴",
    "Patchy sleet nearby": "局部雨夹雪",
    "Light sleet": "小雨夹雪",
    "Moderate or heavy sleet": "中到大雨夹雪",
    "Patchy snow nearby": "局部雪",
    "Light snow": "小雪",
    "Moderate snow": "中雪",
    "Heavy snow": "大雪",
    "Blizzard": "暴风雪",
    "Blowing snow": "吹雪",
    "Smoky haze": "霾",
    "Haze": "霾",
    "Freezing drizzle": "冻毛毛雨",
    "Ice pellets": "冰粒",
}


def _translate(desc: str) -> str:
    """英文天气描述 → 中文"""
    desc = desc.strip()
    return _DESC_CN.get(desc, desc)


def _time_str(t: int) -> str:
    """100 进制时间 → HH:MM 字符串"""
    h = t // 100
    m = t % 100
    return f"{h:02d}:{m:02d}"


def _summarize_day(day: dict) -> str:
    """汇总单日天气，包含温度范围和降水时段"""
    date_str = day["date"]
    month = int(date_str[5:7])
    day_num = int(date_str[8:10])
    min_temp = day.get("mintempC", "?")
    max_temp = day.get("maxtempC", "?")
    avg_temp = day.get("avgtempC", "?")

    lines = [f"{month}月{day_num}日 温度 {min_temp}°C ~ {max_temp}°C（平均 {avg_temp}°C）"]

    # 按降水时间段分组
    hourly = day.get("hourly", [])
    precip_slots = []  # [(time, weather_desc_zh, precipMM)]
    for h in hourly:
        t = int(h["time"])
        desc_en = h.get("weatherDesc", [{"value": "未知"}])[0]["value"]
        precip = float(h.get("precipMM", 0))
        precip_slots.append((t, _translate(desc_en), precip))

    # 合并连续相同时段描述
    merged: list[tuple[int, int, str, float]] = []  # (start_time, end_time, desc, max_precip)
    for t, desc, precip in precip_slots:
        if merged and merged[-1][2] == desc:
            merged[-1] = (merged[-1][0], t + 300, desc, max(merged[-1][3], precip))
        else:
            merged.append((t, t + 300, desc, precip))

    # 找出有降水的时段
    rain_parts = [
        f"{_time_str(start)}-{_time_str(end)} {desc}"
        for start, end, desc, precip in merged
        if precip > 0 or any(
            kw in desc for kw in ("雨", "雪", "雷", "雹", "冰")
        )
    ]
    if rain_parts:
        lines.append("降水时段: " + "；".join(rain_parts))
    else:
        lines.append("全天无降水")

    return "\n  ".join(lines)


@register(
    name="get_weather",
    description="查询指定城市今天或明天的天气。返回温度范围、天气状况、降水时段。",
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如 Beijing、上海、Tokyo，留空则自动判断位置",
            },
            "date": {
                "type": "string",
                "enum": ["today", "tomorrow"],
                "description": "查询日期：today=今天（默认），tomorrow=明天",
            },
        },
        "required": [],
    },
)
def get_weather(args: dict) -> str:
    """调用 wttr.in JSON API，解析并汇总天气信息"""
    city = args.get("city", "")
    date = args.get("date", "today")

    # wttr.in: 不指定城市则自动根据 IP 判断位置
    url_city = city if city else ""

    try:
        resp = requests.get(
            f"https://wttr.in/{url_city}",
            params={"format": "j1"},
            timeout=10,
            headers={"Accept-Language": "zh-CN"},
        )
        resp.encoding = "utf-8"
        data = resp.json()

        # 取 wttr.in 返回的实际城市名
        area_list = data.get("nearest_area", [])
        resolved_city = area_list[0]["areaName"][0]["value"] if area_list else (city or "当前地区")

        weather_list = data.get("weather", [])
        if not weather_list:
            return f"未找到 {resolved_city} 的天气信息"

        idx = 0 if date == "today" else 1
        if idx >= len(weather_list):
            return f"暂无 {resolved_city} 未来天气数据"

        summary = _summarize_day(weather_list[idx])

        label = "今天" if date == "today" else "明天"
        result = f"{resolved_city} {label}天气:\n  {summary}"

        if date == "today":
            current = data.get("current_condition", [])
            if current:
                c = current[0]
                desc_en = c.get("weatherDesc", [{"value": "未知"}])[0]["value"]
                result += (
                    f"\n  当前: {_translate(desc_en)}, 气温 {c['temp_C']}°C, "
                    f"体感 {c['FeelsLikeC']}°C, 湿度 {c['humidity']}%, "
                    f"风速 {c['winddir16Point']} {c['windspeedKmph']}km/h"
                )

        return result
    except requests.exceptions.RequestException:
        return "查询天气失败：无法连接天气服务"
    except Exception as e:
        return f"查询天气失败: {e}"


# ---- CLI: python -m llm_tools.weather [城市] [today|tomorrow|all] ----
if __name__ == "__main__":
    import sys

    city = sys.argv[1] if len(sys.argv) > 1 else ""
    date = sys.argv[2] if len(sys.argv) > 2 else "all"
    label = f"「{city}」" if city else "（自动定位）"

    if date == "today":
        print(get_weather({"city": city, "date": "today"}))
    elif date == "tomorrow":
        print(get_weather({"city": city, "date": "tomorrow"}))
    else:
        print(f"查询 {label} 今天天气...\n")
        print(get_weather({"city": city, "date": "today"}))
        print(f"\n查询 {label} 明天天气...\n")
        print(get_weather({"city": city, "date": "tomorrow"}))
