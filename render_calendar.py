import os
import datetime
import pytz
import requests
import icalendar
import recurring_ical_events
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION ---
ICAL_URL = os.environ["ICAL_URL"]
TIMEZONE = "Australia/Sydney"
LOCATION_NAME = "Wollongong"
LATITUDE, LONGITUDE = -34.4244, 150.8939
WIDTH, HEIGHT = 1448, 1072  # Exact landscape dimensions for your 1072x1448 Kindle screen
ROTATE_DEGREES = 90         # Set to 90 or 270 depending on which side your stand rests on
OUTPUT_PATH = "dashboard.png"

# Grid Time Range (24-hour format)
START_HOUR = 7   # 07:00 AM
END_HOUR = 19    # 07:00 PM


def decode_wmo_code(code):
    if code == 0:
        return "Clear Sky", "sun"
    elif code in (1, 2):
        return "Partly Cloudy", "partly"
    elif code == 3:
        return "Overcast", "cloud"
    elif code in (45, 48):
        return "Foggy", "cloud"
    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain", "rain"
    elif code in (95, 96, 99):
        return "Thunderstorm", "storm"
    return "Cloudy", "cloud"


def get_weather():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={LATITUDE}&longitude={LONGITUDE}"
            f"&current=temperature_2m,weather_code"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&timezone=Australia%2FSydney"
        )
        data = requests.get(url, timeout=8).json()
        curr_temp = round(data["current"]["temperature_2m"])
        w_code = data["current"]["weather_code"]
        max_temp = round(data["daily"]["temperature_2m_max"][0])
        min_temp = round(data["daily"]["temperature_2m_min"][0])
        rain_prob = data["daily"]["precipitation_probability_max"][0]
        cond_text, icon_type = decode_wmo_code(w_code)
        return {
            "temp": f"{curr_temp}°C",
            "cond": cond_text,
            "icon": icon_type,
            "details": f"H: {max_temp}°  L: {min_temp}°  •  Rain: {rain_prob}%",
        }
    except Exception:
        return {
            "temp": "--°C",
            "cond": "Weather Unavailable",
            "icon": "cloud",
            "details": "H: --°  L: --°  •  Rain: --%",
        }


def get_week_events(tz, now):
    monday = (now - datetime.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    sunday_end = monday + datetime.timedelta(days=7)

    response = requests.get(ICAL_URL, timeout=15)
    calendar = icalendar.Calendar.from_ical(response.text)
    events = recurring_ical_events.of(calendar).between(monday, sunday_end)

    parsed = []
    for event in events:
        summary = str(event.get("SUMMARY", "Busy"))
        dtstart = event.get("DTSTART").dt
        dtend = event.get("DTEND").dt if event.get("DTEND") else None

        if isinstance(dtstart, datetime.datetime):
            dtstart = dtstart.astimezone(tz)
            if isinstance(dtend, datetime.datetime):
                dtend = dtend.astimezone(tz)
            else:
                dtend = dtstart + datetime.timedelta(hours=1)
            parsed.append({
                "title": summary,
                "start": dtstart,
                "end": dtend,
                "all_day": False,
            })
        else:
            day_dt = tz.localize(datetime.datetime.combine(dtstart, datetime.time(START_HOUR, 0)))
            parsed.append({
                "title": summary,
                "start": day_dt,
                "end": day_dt + datetime.timedelta(minutes=45),
                "all_day": True,
            })

    parsed.sort(key=lambda e: e["start"])
    return monday, parsed


def get_next_reminder(events, now):
    todays_events = [e for e in events if e["start"].date() == now.date()]
    upcoming_timed = [e for e in todays_events if not e["all_day"] and e["end"] >= now]
    all_day_today = [e for e in todays_events if e["all_day"]]

    if upcoming_timed:
        nxt = upcoming_timed[0]
        is_happening = nxt["start"] <= now <= nxt["end"]
        badge = "NOW" if is_happening else "UP NEXT"
        time_lbl = nxt["start"].strftime("%I:%M %p").lstrip("0")
        return badge, nxt["title"], f"Today at {time_lbl}"
    elif all_day_today:
        rem = all_day_today[0]
        return "REMINDER", rem["title"], "All Day Today"
    else:
        return "TODAY", "No more events scheduled", "Enjoy the rest of your day"


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:2]


def draw_weather_icon(draw, cx, cy, icon_type):
    if icon_type == "sun":
        draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=0, width=3)
        for angle_dx, angle_dy in [(0, -28), (0, 28), (-28, 0), (28, 0), (-20, -20), (20, 20), (-20, 20), (20, -20)]:
            draw.line([(cx + int(angle_dx * 0.75), cy + int(angle_dy * 0.75)), (cx + angle_dx, cy + angle_dy)], fill=0, width=3)
    elif icon_type == "partly":
        draw.ellipse([cx - 4, cy - 24, cx + 24, cy + 4], outline=0, width=3)
        draw.rounded_rectangle([cx - 28, cy - 6, cx + 26, cy + 20], radius=12, fill=255, outline=0, width=3)
    else:
        draw.rounded_rectangle([cx - 28, cy - 12, cx + 26, cy + 14], radius=12, fill=255, outline=0, width=3)
        if icon_type in ("rain", "storm"):
            for rx in (-14, 0, 14):
                draw.line([(cx + rx, cy + 20), (cx + rx - 5, cy + 32)], fill=0, width=3)


def draw_weather_widget(draw, weather, right_edge, fonts):
    temp_w = draw.textlength(weather["temp"], font=fonts["w_temp"])
    header_line = f"{LOCATION_NAME}  •  {weather['cond']}"
    header_w = draw.textlength(header_line, font=fonts["w_cond"])
    details_w = draw.textlength(weather["details"], font=fonts["w_sub"])

    text_block_w = max(header_w, details_w)
    text_x = right_edge - text_block_w
    temp_x = text_x - temp_w - 24
    icon_cx = temp_x - 45

    draw_weather_icon(draw, icon_cx, 72, weather["icon"])
    draw.text((temp_x, 38), weather["temp"], font=fonts["w_temp"], fill=0)
    draw.text((text_x, 40), header_line, font=fonts["w_cond"], fill=0)
    draw.text((text_x, 78), weather["details"], font=fonts["w_sub"], fill=60)
    return icon_cx - 45


def draw_reminder_box(draw, badge, title, subtitle, x1, x2, fonts):
    if x2 - x1 < 220:
        return
    draw.rounded_rectangle([x1, 26, x2, 118], radius=14, fill=244, outline=170, width=2)

    # Dark Badge Pill (UP NEXT / NOW / REMINDER)
    badge_w = draw.textlength(badge, font=fonts["rem_badge"]) + 24
    draw.rounded_rectangle([x1 + 16, 40, x1 + 16 + badge_w, 68], radius=8, fill=35)
    draw.text((x1 + 28, 45), badge, font=fonts["rem_badge"], fill=255)

    # Subtitle next to badge (e.g., "Today at 2:30 PM")
    draw.text((x1 + 26 + badge_w, 44), subtitle, font=fonts["rem_sub"], fill=60)

    # Event Title (truncated cleanly to fit box width)
    max_title_w = (x2 - x1) - 32
    disp_title = title
    while draw.textlength(disp_title, font=fonts["rem_title"]) > max_title_w and len(disp_title) > 4:
        disp_title = disp_title[:-4] + "..."
    draw.text((x1 + 16, 78), disp_title, font=fonts["rem_title"], fill=0)


def generate_image():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    weather = get_weather()
    monday, events = get_week_events(tz, now)
    badge, rem_title, rem_sub = get_next_reminder(events, now)

    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    b_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    r_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    fonts = {
        "top_day": ImageFont.truetype(b_font, 32),
        "top_date": ImageFont.truetype(b_font, 56),
        "rem_badge": ImageFont.truetype(b_font, 17),
        "rem_sub": ImageFont.truetype(r_font, 20),
        "rem_title": ImageFont.truetype(b_font, 25),
        "w_temp": ImageFont.truetype(b_font, 54),
        "w_cond": ImageFont.truetype(b_font, 26),
        "w_sub": ImageFont.truetype(r_font, 22),
        "day_hdr": ImageFont.truetype(b_font, 28),
        "axis": ImageFont.truetype(r_font, 21),
        "ev_title": ImageFont.truetype(b_font, 22),
        "ev_time": ImageFont.truetype(r_font, 19),
    }

    # 1. Top Header Bar (Day & Date -> Next Event Reminder -> Wollongong Weather)
    left_margin = 32
    right_margin = WIDTH - 32

    day_str = now.strftime("%A")
    date_str = now.strftime("%B %d")
    draw.text((left_margin, 24), day_str, font=fonts["top_day"], fill=60)
    draw.text((left_margin, 64), date_str, font=fonts["top_date"], fill=0)

    weather_left_x = draw_weather_widget(draw, weather, right_margin, fonts)

    date_w = draw.textlength(date_str, font=fonts["top_date"])
    rem_x1 = left_margin + date_w + 35
    rem_x2 = weather_left_x - 30
    draw_reminder_box(draw, badge, rem_title, rem_sub, rem_x1, rem_x2, fonts)

    # 2. Full-Width Weekly Grid Geometry
    axis_w = 115
    grid_x1 = left_margin + axis_w
    grid_x2 = right_margin
    header_y1 = 145
    grid_y1 = 215
    grid_y2 = HEIGHT - 28

    col_w = (grid_x2 - grid_x1) / 7.0
    total_hours = END_HOUR - START_HOUR
    hour_h = (grid_y2 - grid_y1) / float(total_hours)

    # Day Column Headers (Mon .. Sun)
    for d in range(7):
        day_dt = monday + datetime.timedelta(days=d)
        cx = grid_x1 + d * col_w + col_w / 2
        day_name = day_dt.strftime("%a")
        day_num = day_dt.strftime("%d")

        is_today = day_dt.date() == now.date()
        name_w = draw.textlength(day_name, font=fonts["day_hdr"])
        num_w = draw.textlength(day_num, font=fonts["day_hdr"])

        if is_today:
            total_w = name_w + num_w + 28
            start_tx = cx - total_w / 2
            draw.text((start_tx, header_y1 + 14), day_name, font=fonts["day_hdr"], fill=0)
            circle_cx = start_tx + name_w + 15 + num_w / 2
            circle_cy = header_y1 + 29
            draw.ellipse([circle_cx - 23, circle_cy - 23, circle_cx + 23, circle_cy + 23], fill=35)
            draw.text((circle_cx - num_w / 2, header_y1 + 14), day_num, font=fonts["day_hdr"], fill=255)
        else:
            label = f"{day_name} {day_num}"
            lw = draw.textlength(label, font=fonts["day_hdr"])
            draw.text((cx - lw / 2, header_y1 + 14), label, font=fonts["day_hdr"], fill=40)

    # Grid Background & Hour Lines
    draw.rectangle([grid_x1, grid_y1, grid_x2, grid_y2], fill=248)
    for h in range(total_hours + 1):
        y = grid_y1 + h * hour_h
        draw.line([(grid_x1, y), (grid_x2, y)], fill=205, width=2)
        if h < total_hours:
            hr_24 = START_HOUR + h
            hr_12 = hr_24 if hr_24 <= 12 else hr_24 - 12
            ampm = "am" if hr_24 < 12 else "pm"
            lbl = f"{hr_12:02d}:00 {ampm}"
            draw.text((left_margin + 6, y - 10), lbl, font=fonts["axis"], fill=70)

    for d in range(8):
        x = grid_x1 + d * col_w
        draw.line([(x, grid_y1), (x, grid_y2)], fill=205, width=2)

    # 3. Draw Event Cards
    shades = [235, 225, 242]
    for idx, ev in enumerate(events):
        day_idx = (ev["start"].date() - monday.date()).days
        if not (0 <= day_idx < 7):
            continue

        start_float = ev["start"].hour + ev["start"].minute / 60.0
        end_float = ev["end"].hour + ev["end"].minute / 60.0
        if end_float <= start_float:
            end_float = start_float + 0.75

        vis_start = max(START_HOUR, start_float)
        vis_end = min(END_HOUR, end_float)
        if vis_end <= vis_start:
            continue

        x1 = grid_x1 + day_idx * col_w + 7
        x2 = grid_x1 + (day_idx + 1) * col_w - 7
        y1 = grid_y1 + (vis_start - START_HOUR) * hour_h + 3
        y2 = max(y1 + 60, grid_y1 + (vis_end - START_HOUR) * hour_h - 3)

        card_fill = shades[idx % len(shades)]
        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=card_fill, outline=90, width=2)
        draw.rectangle([x1, y1 + 3, x1 + 7, y2 - 3], fill=20)

        text_x = x1 + 15
        max_tw = (x2 - x1) - 22
        title_lines = wrap_text(draw, ev["title"], fonts["ev_title"], max_tw)
        ty = y1 + 8
        for line in title_lines:
            draw.text((text_x, ty), line, font=fonts["ev_title"], fill=0)
            ty += 25

        if ev["all_day"]:
            t_range = "All Day"
        else:
            t_range = f"{ev['start'].strftime('%I:%M')}-{ev['end'].strftime('%I:%M %p')}"
        draw.text((text_x, ty + 2), t_range, font=fonts["ev_time"], fill=50)

        if (y2 - ty) > 38:
            dot_y = ty + 33
            draw.ellipse([text_x, dot_y, text_x + 14, dot_y + 14], fill=50)

    # Rotate 90 degrees for landscape Kindle stand display
    if ROTATE_DEGREES:
        img = img.rotate(ROTATE_DEGREES, expand=True)

    img.save(OUTPUT_PATH)


if __name__ == "__main__":
    generate_image()
