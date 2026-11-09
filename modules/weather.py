"""Current weather and tomorrow's forecast via Open-Meteo, without an API key."""
import json
import re
from urllib.parse import urlencode
from urllib.request import urlopen
from modules.language import detect_language, choose


def _get(url, params):
    with urlopen(url + "?" + urlencode(params), timeout=8) as response:
        return json.load(response)


def describe_weather(question):
    language = detect_language(question)
    match = re.search(r"\b(?:in|for|at|di|untuk)\s+(.+)", question, re.I)
    if not match:
        return choose(language, "Which city should I check? Try asking, ‘What’s the weather in Jakarta?’", "Mau cek cuaca di kota mana? Coba bilang, bagaimana cuaca di Jakarta?")
    city = re.sub(r"\b(?:today|tomorrow|right now|this morning|this evening|hari ini|besok|sekarang|pagi ini|malam ini)\b", "", match[1], flags=re.I).strip(" ?.!,")
    try:
        locations = _get("https://geocoding-api.open-meteo.com/v1/search",
                         {"name": city, "count": 1, "language": language, "format": "json"}).get("results", [])
        if not locations:
            return choose(language, f"I couldn’t find {city}. Could you give me the city and country?", f"Aku belum menemukan {city}. Bisa sebutkan nama kota dan negaranya?")
        place = locations[0]
        data = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 2,
        })
        daily = data["daily"]
        tomorrow = bool(re.search(r"\b(?:tomorrow|besok)\b", question, re.I))
        day = 1 if tomorrow else 0
        rain = daily["precipitation_probability_max"][day]
        if language == "id":
            if tomorrow:
                return (f"Besok di {place['name']}, suhu diperkirakan {daily['temperature_2m_min'][day]:.0f} "
                        f"sampai {daily['temperature_2m_max'][day]:.0f} derajat Celsius, dengan kemungkinan hujan {rain:.0f} persen. "
                        "Prakiraan dari Open-Meteo.")
            current = data["current"]
            return (f"Di {place['name']}, suhunya {current['temperature_2m']:.0f} derajat Celsius dan terasa seperti "
                    f"{current['apparent_temperature']:.0f} derajat, menurut data pukul {current['time'][11:16]} waktu setempat. "
                    f"Kemungkinan hujan hari ini {rain:.0f} persen, menurut Open-Meteo.")
        if tomorrow:
            return (f"Tomorrow in {place['name']}, {place.get('country', '')}, expect "
                    f"{daily['temperature_2m_min'][day]:.0f} to {daily['temperature_2m_max'][day]:.0f} degrees Celsius, "
                    f"with a {rain:.0f} percent chance of rain. Forecast from Open-Meteo.")
        current = data["current"]
        return (f"In {place['name']}, {place.get('country', '')}, it’s {current['temperature_2m']:.0f} degrees Celsius "
                f"and feels like {current['apparent_temperature']:.0f}, as of {current['time'][11:16]} local time. "
                f"Today’s rain chance is {rain:.0f} percent, according to Open-Meteo.")
    except Exception as error:
        print(f"[WEATHER] {error}")
        return choose(language, "I can’t reach the weather service just now. Try again in a moment.", "Layanan cuaca belum bisa dihubungi. Coba lagi sebentar, ya.")
