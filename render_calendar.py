import os
import datetime
import pytz
import requests
import icalendar
import recurring_ical_events
from PIL import Image, ImageDraw, ImageFont

ICAL_URL = os.environ["ICAL_URL"]
TIMEZONE = "Australia/Sydney"
WIDTH, HEIGHT = 1236, 1648  # 11th Gen Paperwhite (Use 1072, 1448 for Basic)
OUTPUT_PATH = "dashboard.png"

def get_todays_events():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + datetime.timedelta(days=1)

    response = requests.get(ICAL_URL)
    calendar = icalendar.Calendar.from_ical(response.text)
    events = recurring_ical_events.of(calendar).between(start_of_day, end_of_day)

    parsed_events = []
    for event in events:
        summary = str(event.get('SUMMARY', 'Busy'))
        dtstart = event.get('DTSTART').dt
        if isinstance(dtstart, datetime.datetime):
            dtstart = dtstart.astimezone(tz)
            time_str = dtstart.strftime("%I:%M %p").lstrip("0")
            sort_key = dtstart
        else:
            time_str = "All Day"
            sort_key = start_of_day
        parsed_events.append((sort_key, time_str, summary))

    parsed_events.sort(key=lambda x: x[0])
    return now, parsed_events

def generate_image():
    now, events = get_todays_events()
    img = Image.new('L', (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    # Ubuntu servers include DejaVu fonts pre-installed
    font_path_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_path_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    font_time = ImageFont.truetype(font_path_bold, 130)
    font_date = ImageFont.truetype(font_path_reg, 42)
    font_header = ImageFont.truetype(font_path_bold, 38)
    font_event_time = ImageFont.truetype(font_path_bold, 34)
    font_event_title = ImageFont.truetype(font_path_reg, 36)

    # Left Column: Time & Date
    left_margin = 60
    draw.text((left_margin, 120), now.strftime("%I:%M").lstrip("0"), font=font_time, fill=0)
    draw.text((left_margin, 270), now.strftime("%p"), font=font_date, fill=80)
    draw.text((left_margin, 360), now.strftime("%A,\n%B %d"), font=font_date, fill=0)

    # Divider
    divider_x = int(WIDTH * 0.42)
    draw.line([(divider_x, 80), (divider_x, HEIGHT - 80)], fill=0, width=4)

    # Right Column: Events
    right_margin = divider_x + 50
    y_cursor = 120
    draw.text((right_margin, y_cursor), "TODAY'S SCHEDULE", font=font_header, fill=0)
    y_cursor += 80
    draw.line([(right_margin, y_cursor), (WIDTH - 60, y_cursor)], fill=150, width=2)
    y_cursor += 40

    if not events:
        draw.text((right_margin, y_cursor), "No events scheduled.", font=font_event_title, fill=100)
    else:
        for _, time_str, summary in events:
            draw.text((right_margin, y_cursor), time_str, font=font_event_time, fill=80)
            y_cursor += 45
            display_title = (summary[:28] + '..') if len(summary) > 30 else summary
            draw.text((right_margin, y_cursor), display_title, font=font_event_title, fill=0)
            y_cursor += 85

    img.save(OUTPUT_PATH)

if __name__ == "__main__":
    generate_image()
