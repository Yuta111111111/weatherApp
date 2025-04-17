from flask import Flask, render_template, jsonify , request
import requests
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# OpenWeatherMap APIキー
API_KEY = "fe99036ee85183eebd97a16c7d991bda"  # ここに取得したAPIキーを入力

# 都市ID (福岡)
CITY_ID = "1863967"

# APIのエンドポイント(5 day / 3 hour forecast)
FORECAST_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast?"
UNITS = "metric"  # 温度を摂氏で取得
LANG = "ja"      # 言語を日本語に設定

def get_forecast_data(city_name):
    url = f"{FORECAST_BASE_URL}appid={API_KEY}&q={city_name}&units={UNITS}&lang={LANG}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        forecast_data = response.json()
        return forecast_data
    except requests.exceptions.RequestException as e:
        print(f"APIリクエストエラー: {e}")
        return None
    except Exception as e:
        print(f"予期せぬエラー: {e}")
        return None

@app.route("/")
def index():
    city_param = request.args.get('city', 'Fukuoka,JP')  # デフォルトは福岡
    city_name_en = city_param.split(',')[0]  # 都市名のみ抽出 (例: "Nagoya")
    city_name_jp_map = {
        "Fukuoka": "福岡",
        "Tokyo": "東京",
        "Osaka": "大阪",
        "Nagoya": "名古屋",
        "Sapporo": "札幌"
    }

    city_name_jp = city_name_jp_map.get(city_name_en, city_name_en) # 対応がない場合は英語名を表示

    forecast_data = get_forecast_data(city_param)
    three_hourly_forecast_data = []
    daily_forecast_data = {}
    week_names_jp = ["日", "月", "火", "水", "木", "金", "土"]

    if forecast_data and "list" in forecast_data:
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        for item in forecast_data["list"]:
            timestamp = item["dt"]
            forecast_time_utc = datetime.fromtimestamp(timestamp, timezone.utc)
            forecast_time_jst = forecast_time_utc.astimezone(timezone(timedelta(hours=9)))  # ローカルタイムに変換
            #forecast_time = datetime.fromtimestamp(timestamp)
            forecast_data = forecast_time_jst.date()
            date_str = forecast_time_jst.strftime("%Y-%m-%d")
            weekday_jp = week_names_jp[forecast_time_jst.weekday()] # 曜日を日本語で取得

            # 直近二日間の3時間ごとのデータ
            if forecast_data == today or forecast_data == tomorrow:
                three_hourly_forecast_data.append({
                    "time": forecast_time_jst.strftime("%m/%d %H"),
                    "weekday": weekday_jp,
                    "icon_id": item["weather"][0]["icon"],
                    "description": item["weather"][0]["description"],
                    "temp": round(item["main"]["temp"]),
                    "pop": round(item.get("pop", 0) * 100),
                    "rain": item.get("rain", {}).get("3h", 0),
                    "wind_speed": item["wind"].get("speed", 0),
                    "wind_deg": item["wind"].get("deg", 0)
                })

            # 一日ごとのデータを集計
            if date_str not in daily_forecast_data:
                daily_forecast_data[date_str] = {
                    "min_temp": float('inf'),
                    "max_temp": float('-inf'),
                    "icons": {},
                    "pops": []
                }

            daily_forecast_data[date_str]["min_temp"] = min(daily_forecast_data[date_str]["min_temp"], item["main"]["temp"])
            daily_forecast_data[date_str]["max_temp"] = max(daily_forecast_data[date_str]["max_temp"], item["main"]["temp"])
            daily_forecast_data[date_str]["icons"][item["weather"][0]["icon"]] = daily_forecast_data[date_str]["icons"].get(item["weather"][0]["icon"], 0) + 1
            daily_forecast_data[date_str]["pops"].append(item.get("pop", 0))

    # 一日ごとの表示用にデータを整形
    processed_daily_data = []
    
    for date_str, data in daily_forecast_data.items():
        most_frequent_icon = max(data["icons"], key=data["icons"].get, default=None)
        avg_pop = round(sum(data["pops"]) / len(data["pops"]) * 100) if data["pops"] else 0
        forecast_data = datetime.strptime(date_str, "%Y-%m-%d")
        weekday_jp = week_names_jp[forecast_data.weekday()] # 曜日を日本語で取得
        processed_daily_data.append({
            "date": datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d"),
            "weekday": weekday_jp,
            "min_temp": round(data["min_temp"]),
            "max_temp": round(data["max_temp"]),
            "icon_id": most_frequent_icon,
            "pop": avg_pop
        })

    return render_template(
        "index.html",
        three_hourly_forecast_data=three_hourly_forecast_data,
        daily_forecast_data=processed_daily_data,
        current_city=city_name_jp
    )

@app.route('/suggestion/<city_name>/<date_str>')
def get_clothing_suggestion(city_name, date_str):
    forecast_data = get_forecast_data(city_name)
    suggestion = "情報がありません。"
    umbrella = ""

    if forecast_data and "list" in forecast_data:
        pops = []
        for item in forecast_data["list"]:
            forecast_time = datetime.fromtimestamp(item["dt"])
            if forecast_time.strftime("%Y-%m-%d") == date_str:
                pops.append(item.get("pop", 0))

        if pops:
            avg_pop = sum(pops) / len(pops)
            if avg_pop >= 0.5:  # 降水確率50%以上で傘が必要と判断
                umbrella = " 傘をお持ちください!!!!"

            avg_temp = sum(item["main"]["temp"] for item in forecast_data["list"] if datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d") == date_str) / len([item for item in forecast_data["list"] if datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d") == date_str]) if [item for item in forecast_data["list"] if datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d") == date_str] else 0

            if avg_temp >= 25:
                suggestion = "半袖、Tシャツ、薄手のワンピースなどがおすすめです。"
            elif 20 <= avg_temp < 25:
                suggestion = "長袖シャツ、薄手のカーディガン、七分袖などがおすすめです。"
            elif 15 <= avg_temp < 20:
                suggestion = "ジャケット、カーディガン、薄手のセーターなどがおすすめです。"
            elif 10 <= avg_temp < 15:
                suggestion = "セーター、厚手のジャケット、コートなどがおすすめです。"
            else:
                suggestion = "ダウンジャケット、厚手のコート、マフラー、手袋などがおすすめです。"

    return jsonify({'suggestion': suggestion + umbrella})

if __name__ == "__main__":
    app.run(debug=True)