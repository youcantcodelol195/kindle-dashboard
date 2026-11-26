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
LATITUDE, LONGITUDE = -33.8688, 151.2093  # Sydney coordinates for live weather
WIDTH, HEIGHT = 1648, 1236  # Landscape canvas for 11th Gen Paperwhite (use 1448, 1072 for Basic)
ROTATE_DEGREES = 90         # Set to 90 or 270 depending on which side your stand rests on
OUTPUT_PATH = "dashboard.png"

# Grid Time Range (24-hour format)
START_HOUR = 7   # 07:00 AM
END_HOUR = 19    # 07:00 PM


def get_weather():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true"
        data = requests.get(url, timeout=5).json()
        temp = round(data["current_weather"]["temperature"])
        return f"{temp}°C"
    except Exception:
        return "--°C"


def get_week_events(tz, now):
    # Find Monday of the current week
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
            # All-day event
            day_dt = tz.localize(datetime.datetime.combine(dtstart, datetime.time(START_HOUR, 0)))
            parsed.append({
                "title": summary,
                "start": day_dt,
                "end": day_dt + datetime.timedelta(minutes=45),
                "all_day": True,
            })
    return monday, parsed


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


def draw_sidebar(draw, weather_str, fonts):
    sidebar_w = 175
    draw.rectangle([0, 0, sidebar_w, HEIGHT], fill=248)
    draw.line([(sidebar_w, 0), (sidebar_w, HEIGHT)], fill=210, width=2)

    # Weather Icon (Cloud + Sun) & Temp
    cx = sidebar_w // 2
    draw.ellipse([cx - 6, 26, cx + 22, 54], outline=0, width=3)
    draw.rounded_rectangle([cx - 28, 42, cx + 26, 68], radius=12, fill=248, outline=0, width=3)
    w_temp = draw.textlength(weather_str, font=fonts["temp"])
    draw.text((cx - w_temp / 2, 82), weather_str, font=fonts["temp"], fill=0)

    # Navigation Items
    nav_items = ["Calendar", "Tasks", "Rewards", "Meals", "Photos", "Lists", "Sleep", "Settings"]
    y = 155
    for idx, label in enumerate(nav_items):
        is_active = idx == 0
        box_x1, box_x2 = 16, sidebar_w - 16
        box_y1, box_y2 = y, y + 96

        if is_active:
            draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=16, fill=35)
            fg = 255
        else:
            fg = 60

        # Minimalist geometric icon
        ix, iy = cx, y + 32
        if label == "Calendar":
            draw.rounded_rectangle([ix - 16, iy - 14, ix + 16, iy + 16], radius=4, outline=fg, width=3)
            draw.line([(ix - 16, iy - 4), (ix + 16, iy - 4)], fill=fg, width=2)
        elif label == "Tasks":
            draw.rounded_rectangle([ix - 15, iy - 15, ix + 15, iy + 15], radius=4, outline=fg, width=3)
            draw.line([(ix - 8, iy), (ix - 2, iy + 7), (ix + 9, iy - 7)], fill=fg, width=3)
        elif label == "Rewards":
            draw.polygon([(ix - 14, iy - 14), (ix + 14, iy - 14), (ix + 8, iy + 4), (ix - 8, iy + 4)], outline=fg, width=3)
            draw.line([(ix, iy + 4), (ix, iy + 15), (ix - 10, iy + 15), (ix + 10, iy + 15)], fill=fg, width=3)
        elif label == "Meals":
            draw.line([(ix - 8, iy - 15), (ix - 8, iy + 15)], fill=fg, width=3)
            draw.line([(ix + 8, iy - 15), (ix + 8, iy + 15)], fill=fg, width=3)
        elif label == "Photos":
            draw.rounded_rectangle([ix - 16, iy - 13, ix + 16, iy + 13], radius=4, outline=fg, width=3)
            draw.polygon([(ix - 12, iy + 10), (ix - 2, iy - 2), (ix + 6, iy + 6), (ix + 12, iy + 10)], fill=fg)
        elif label == "Lists":
            for offset in (-9, 0, 9):
                draw.line([(ix - 12, iy + offset), (ix + 14, iy + offset)], fill=fg, width=3)
        elif label == "Sleep":
            draw.rounded_rectangle([ix - 16, iy - 6, ix + 16, iy + 12], radius=3, outline=fg, width=3)
            draw.line([(ix - 16, iy - 14), (ix - 16, iy + 15)], fill=fg, width=3)
        elif label == "Settings":
            draw.ellipse([ix - 14, iy - 14, ix + 14, iy + 14], outline=fg, width=3)
            draw.ellipse([ix - 5, iy - 5, ix + 5, iy + 5], outline=fg, width=3)

        lw = draw.textlength(label, font=fonts["nav"])
        draw.text((cx - lw / 2, y + 60), label, font=fonts["nav"], fill=fg)
        y += 126

    return sidebar_w


def generate_image():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    weather_str = get_weather()
    monday, events = get_week_events(tz, now)

    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    b_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    r_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    fonts = {
        "temp": ImageFont.truetype(b_font, 28),
        "nav": ImageFont.truetype(r_font, 22),
        "top_date": ImageFont.truetype(b_font, 32),
        "top_time": ImageFont.truetype(b_font, 54),
        "pill": ImageFont.truetype(r_font, 24),
        "day_hdr": ImageFont.truetype(b_font, 26),
        "axis": ImageFont.truetype(r_font, 20),
        "ev_title": ImageFont.truetype(b_font, 21),
        "ev_time": ImageFont.truetype(r_font, 18),
    }

    # 1. Left Sidebar
    sidebar_w = draw_sidebar(draw, weather_str, fonts)

    # 2. Top Header Bar
    main_x = sidebar_w + 30
    draw.text((main_x, 24), now.strftime("%B %d"), font=fonts["top_date"], fill=0)
    time_str = now.strftime("%I:%M %p")
    draw.text((main_x, 64), time_str, font=fonts["top_time"], fill=0)

    # "Schedule v" Pill
    time_w = draw.textlength(time_str, font=fonts["top_time"])
    pill_x = main_x + time_w + 35
    draw.rounded_rectangle([pill_x, 66, pill_x + 175, 114], radius=22, fill=242, outline=180, width=2)
    draw.text((pill_x + 22, 77), "Schedule  v", font=fonts["pill"], fill=20)

    # Right "Filter v" Pill & Wi-Fi Icon
    filter_x = WIDTH - 230
    draw.rounded_rectangle([filter_x, 66, filter_x + 135, 114], radius=22, fill=242, outline=180, width=2)
    draw.text((filter_x + 20, 77), "Filter  v", font=fonts["pill"], fill=20)

    wx, wy = WIDTH - 55, 98
    for r in (26, 18, 10):
        draw.arc([wx - r, wy - r, wx + r, wy + r], start=225, end=315, fill=0, width=3)
    draw.ellipse([wx - 3, wy - 3, wx + 3, wy + 3], fill=0)

    # 3. Weekly Grid Geometry
    axis_w = 105
    grid_x1 = sidebar_w + axis_w
    grid_x2 = WIDTH - 24
    header_y1 = 145
    grid_y1 = 215
    grid_y2 = HEIGHT - 24

    col_w = (grid_x2 - grid_x1) / 7.0
    total_hours = END_HOUR - START_HOUR
    hour_h = (grid_y2 - grid_y1) / float(total_hours)

    # Day Column Headers (Mon 09 .. Sun 15)
    for d in range(7):
        day_dt = monday + datetime.timedelta(days=d)
        cx = grid_x1 + d * col_w + col_w / 2
        day_name = day_dt.strftime("%a")
        day_num = day_dt.strftime("%d")

        is_today = day_dt.date() == now.date()
        name_w = draw.textlength(day_name, font=fonts["day_hdr"])
        num_w = draw.textlength(day_num, font=fonts["day_hdr"])

        if is_today:
            total_w = name_w + num_w + 26
            start_tx = cx - total_w / 2
            draw.text((start_tx, header_y1 + 14), day_name, font=fonts["day_hdr"], fill=0)
            circle_cx = start_tx + name_w + 14 + num_w / 2
            circle_cy = header_y1 + 28
            draw.ellipse([circle_cx - 22, circle_cy - 22, circle_cx + 22, circle_cy + 22], fill=35)
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
            draw.text((sidebar_w + 14, y - 10), lbl, font=fonts["axis"], fill=70)

    for d in range(8):
        x = grid_x1 + d * col_w
        draw.line([(x, grid_y1), (x, grid_y2)], fill=205, width=2)

    # 4. Draw Event Cards
    shades = [235, 225, 242]
    for idx, ev in enumerate(events):
        day_idx = (ev["start"].date() - monday.date()).days
        if not (0 <= day_idx < 7):
            continue

        start_float = ev["start"].hour + ev["start"].minute / 60.0
        end_float = ev["end"].hour + ev["end"].minute / 60.0
        if end_float <= start_float:
            end_float = start_float + 0.75

        # Clamp within visible grid hours
        vis_start = max(START_HOUR, start_float)
        vis_end = min(END_HOUR, end_float)
        if vis_end <= vis_start:
            continue

        x1 = grid_x1 + day_idx * col_w + 6
        x2 = grid_x1 + (day_idx + 1) * col_w - 6
        y1 = grid_y1 + (vis_start - START_HOUR) * hour_h + 3
        y2 = max(y1 + 58, grid_y1 + (vis_end - START_HOUR) * hour_h - 3)

        card_fill = shades[idx % len(shades)]
        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=card_fill, outline=90, width=2)
        # Thick dark left accent border
        draw.rectangle([x1, y1 + 3, x1 + 7, y2 - 3], fill=20)

        # Event Title & Time Range
        text_x = x1 + 14
        max_tw = (x2 - x1) - 20
        title_lines = wrap_text(draw, ev["title"], fonts["ev_title"], max_tw)
        ty = y1 + 8
        for line in title_lines:
            draw.text((text_x, ty), line, font=fonts["ev_title"], fill=0)
            ty += 24

        if ev["all_day"]:
            t_range = "All Day"
        else:
            t_range = f"{ev['start'].strftime('%I:%M')}-{ev['end'].strftime('%I:%M %p')}"
        draw.text((text_x, ty + 2), t_range, font=fonts["ev_time"], fill=50)

        # Status dot at bottom-left of card
        if (y2 - ty) > 38:
            dot_y = ty + 32
            draw.ellipse([text_x, dot_y, text_x + 14, dot_y + 14], fill=50)

    # 5. Floating "+" Action Button (Bottom Right)
    fab_x, fab_y, fab_r = WIDTH - 68, HEIGHT - 68, 34
    draw.ellipse([fab_x - fab_r, fab_y - fab_r, fab_x + fab_r, fab_y + fab_r], fill=255, outline=30, width=3)
    draw.line([(fab_x - 14, fab_y), (fab_x + 14, fab_y)], fill=30, width=3)
    draw.line([(fab_x, fab_y - 14), (fab_x, fab_y + 14)], fill=30, width=3)

    # Rotate 90 degrees so portrait framebuffer displays landscape when Kindle is on its side
    if ROTATE_DEGREES:
        img = img.rotate(ROTATE_DEGREES, expand=True)

    img.save(OUTPUT_PATH)


if __name__ == "__main__":
    generate_image()
