#!/usr/bin/env python3

import configparser
import json
import sys
import time
import re
import traceback
import urllib.request
import paho.mqtt.client as mqtt
import datetime

from PIL import Image, ImageFont, ImageDraw
from font_hanken_grotesk import HankenGroteskBold, HankenGroteskMedium
from inky import InkyWHAT
from suntime import Sun, SunTimeException

# Global for data storage
g_mqtt_data = {}
g_awair_mqtt_rooms = ()
g_awair_mqtt_ext_rooms = ()
g_heartbeat_url = None
g_mqtt_connected = False
g_recent_disconnect = False  # True if we've disconnected since last display refresh


def on_connect(client, userdata, flags, rc):
    """The callback for when the client receives a CONNACK server response."""
    global g_mqtt_connected

    if rc == 0:
        print("Connected to MQTT broker")
        g_mqtt_connected = True

        mqtt_subscriptions = [("weathergov/forecast", 0),
                              ("weathergov/warnings", 0),
                              ("weewx/sensor", 0),
                              ("purpleair/sensor", 0),
                              ("rainforest/load", 0),
                              ("pool/sensor", 0)]
        for room_list in (g_awair_mqtt_rooms, g_awair_mqtt_ext_rooms):
            for awair_mqtt_room in room_list:
                print(awair_mqtt_room)
                room_tuple = ("awair/" + awair_mqtt_room + "/sensor", 0)
                mqtt_subscriptions.append(room_tuple)

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(mqtt_subscriptions)
    else:
        print(f"Connection failed with code {rc}")
        g_mqtt_connected = False


def on_disconnect(client, userdata, rc):
    """The callback for when the client disconnects from the server."""
    global g_mqtt_connected, g_recent_disconnect
    g_mqtt_connected = False
    g_recent_disconnect = True
    if rc != 0:
        print(f"Unexpected MQTT disconnection (rc={rc}). Will auto-reconnect...")
    else:
        print("Disconnected from MQTT broker")


def on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    global g_mqtt_data

    try:
        print("MESSAGE: "+msg.topic+" -> "+str(msg.payload.decode('UTF-8')))
        message_data = json.loads(str(msg.payload.decode('UTF-8')))
        g_mqtt_data[msg.topic] = message_data
    except json.JSONDecodeError as e:
        print(f"Failed to parse MQTT message on {msg.topic}: {e}")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")


def draw_outside_temp_text_line(inky_display, draw, main_font,
                                small_main_font, diff_font, start_x, start_y):
    """Draws the outside temperature and last hour temperature delta."""
    global g_mqtt_data

    weewx = g_mqtt_data.get('weewx/sensor', {})
    temp = weewx.get('outdoor_temperature', 0)
    temp_delta = weewx.get('outdoor_temp_change', 0)
    temp_24h_delta = weewx.get('outdoor_24h_temp_change', 0)

    # If the temp is >=100, it needs to be a smaller font
    # Also, moving the 1hr delta below the main temp in this case
    big_temp_font = main_font
    delta_x_offset = 0
    delta_y_offset = 0
    if (temp >= 100):
        big_temp_font = small_main_font
        delta_x_offset = -60
        delta_y_offset = 20

    temp_str = '{}\u00b0'.format(int(temp))
    draw.text((start_x, start_y), temp_str, inky_display.BLACK,
              font=big_temp_font)

    # Put the temp change right under the degree symbol of the outside temp
    delta_str = '{:+.1f}\u00b0'.format(float(temp_delta))
    delta_24h_str = '{:+.1f}\u00b0'.format(float(temp_24h_delta))
    delta_x = 120
    draw.text((delta_x + delta_x_offset, start_y + delta_y_offset + 49),
              delta_str, inky_display.BLACK, font=diff_font)
    draw.text((delta_x, start_y + 69),
              delta_24h_str, inky_display.BLACK, font=diff_font)

    y_coord = start_y + 90

    rain_rate = weewx.get('rain_rate', 0)
    last_day_rain = weewx.get('last_day_rain', 0)
    wind_gust = weewx.get('wind_gust', 0)
    purpleair = g_mqtt_data.get('purpleair/sensor', {})
    aqi = purpleair.get('st_aqi', 0)
    lrapa_aqi = purpleair.get('st_lrapa_aqi', 0)
    last_hour_aqi = purpleair.get('st_aqi_last_hour', 0)
    last_hour_lrapa_aqi = purpleair.get('st_lrapa_aqi_last_hour', 0)
    aqi_desc = purpleair.get('st_aqi_desc', '')

    aqi_str = 'A{} {:+d}  L{} {:+d}'.format(aqi, last_hour_aqi,
                                            lrapa_aqi, last_hour_lrapa_aqi)
    draw.text((start_x, y_coord), aqi_str, inky_display.BLACK, font=diff_font)
    y_coord += 18 + 3

    if (aqi > 100):
        draw.text((start_x, y_coord), aqi_desc,
                  inky_display.RED, font=diff_font)
        y_coord += 18 + 3

    if (wind_gust >= 10):
        wind_str = 'GUST: {}'.format(wind_gust)
        draw.text((start_x, y_coord),
                  wind_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 3

    if (last_day_rain > 0):
        last_day_rain_str = '24h: {}"'.format(last_day_rain)
        if (rain_rate > 0):
            last_day_rain_str += ' @{:.2f}"/h'.format(rain_rate)
        draw.text((start_x, y_coord),
                  last_day_rain_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 3

    rainforest = g_mqtt_data.get('rainforest/load', {})
    power_kw = rainforest.get('instantaneous')
    if power_kw is not None:
        draw.text((start_x, y_coord), '{:.2f}kW'.format(float(power_kw)),
                  inky_display.BLACK, font=diff_font)
        y_coord += 18 + 3


def draw_awair_text_line(inky_display, draw, this_font, start_x, start_y,
                         topic_substr):
    """Draws the single line of text for each Awair device."""

    topic_name = 'awair/' + topic_substr + '/sensor'
    if (topic_name in g_mqtt_data):
        temperature = g_mqtt_data[topic_name]['temp']
        co2 = g_mqtt_data[topic_name]['co2']

        temperature_change = 0
        if ('last_hour_temp' in g_mqtt_data[topic_name]):
          temperature_change = g_mqtt_data[topic_name]['last_hour_temp']

        aqi = 0
        if ('aqi' in g_mqtt_data[topic_name]):
            aqi = g_mqtt_data[topic_name]['aqi']

        draw.text((start_x, start_y),
                  topic_substr.split('/')[-1][0], inky_display.BLACK,
                  font=this_font)
        draw.text((start_x + 25, start_y),
                  '{}\u00b0'.format(temperature),
                  inky_display.BLACK, font=this_font)
        draw.text((start_x + 85, start_y),
                  '{:+.1f}\u00b0'.format(float(temperature_change)),
                  inky_display.BLACK, font=this_font)

        if (aqi > 100):
            draw.text((start_x + 150, start_y),
                      'A' + str(int(aqi)), inky_display.RED, font=this_font)
        else:
            text_color = inky_display.BLACK
            if (int(co2) > 1000):
                text_color = inky_display.RED
            draw.text((start_x + 150, start_y),
                      str(int(co2)), text_color, font=this_font)


def draw_ext_awair_text_line(inky_display, draw, this_font, start_x, start_y):
    """Draws the single line of text for external Awair devices."""

    global g_awair_mqtt_ext_rooms
    count = 0

    for ext_room in g_awair_mqtt_ext_rooms:
        topic_name = 'awair/' + ext_room + '/sensor'
        room_name = ext_room.split('/').pop()
        if (topic_name in g_mqtt_data):
            temperature = g_mqtt_data[topic_name]['temp']

            aqi = 0
            if ('aqi' in g_mqtt_data[topic_name]):
                aqi = g_mqtt_data[topic_name]['aqi']

            draw.text((start_x, start_y),
                      room_name[0], inky_display.BLACK,
                      font=this_font)

            start_x_offset = 25
            if (aqi > 100):
                draw.text((start_x + start_x_offset, start_y),
                          'A' + str(int(aqi)), inky_display.RED,
                          font=this_font)
            else:
                draw.text((start_x + start_x_offset, start_y),
                          '{}\u00b0'.format(temperature),
                          inky_display.BLACK, font=this_font)

            start_x += 85

            # Only allow two external rooms to be displayed
            count += 1
            if count > 2:
                break


def draw_kitchen_temp_text_line(inky_display, draw, this_font,
                                start_x, start_y):
    """Draws the single ine of text for the kitchen"""

    topic_name = 'weewx/sensor'
    if (topic_name in g_mqtt_data):
        indoor_temp = g_mqtt_data[topic_name].get('indoor_temperature', 0)
        indoor_temp_change = g_mqtt_data[topic_name].get('indoor_temp_change', 0)

        draw.text((start_x, start_y),
                  'K', inky_display.BLACK, font=this_font)
        draw.text((start_x + 25, start_y),
                  '{:.1f}\u00b0'.format(float(indoor_temp)),
                  inky_display.BLACK, font=this_font)
        draw.text((start_x + 85, start_y),
                  '{:+.1f}\u00b0'.format(float(indoor_temp_change)),
                  inky_display.BLACK, font=this_font)
        draw.text((start_x + 160, start_y),
                  time.strftime("%H:%M", time.localtime()),
                  inky_display.BLACK, font=this_font)


def draw_forecast(inky_display, draw, this_font, start_y):
    """Draws the lines of text for the upcoming weather forecast."""
    # Sample data
    # {'precip_chance': '1', 'temp': '50', 'day': 'OVERNIGHT',
    # 'forecast': 'Chance rain', 'precip_serverity': 2}
    global g_mqtt_data

    count = 1
    max_items = 4
    # Use getbbox for Pillow 10+ compatibility (getsize was removed)
    line_height = this_font.getbbox('Ay')[3]

    warnings = g_mqtt_data.get('weathergov/warnings', [])
    for warning in warnings:
        title = warning.get('title', '')
        desc = warning.get('desc', '')
        day_str = '{}: {}'.format(title.title(), desc)
        draw.text((7, start_y + (count * line_height)),
                  day_str, inky_display.RED, font=this_font)

        count += 1

        # Only show max_items
        # Return here vs break later
        if (count > max_items):
            return

    forecast = g_mqtt_data.get('weathergov/forecast', [])
    for day_info in forecast:
        time_str = day_info.get('day', '')
        time_str = re.sub('BIRTHDAY', 'BDAY', time_str)
        time_str = re.sub(r'(\S{3})\S*DAY', r'\1', time_str)
        time_str = re.sub(r'THIS ', r'', time_str)

        day_str = '{}: {}, {}\u00b0'.format(time_str,
                                            day_info.get('forecast', ''),
                                            day_info.get('temp', ''))

        precip_amount = day_info.get('precip_amount')
        if precip_amount:
            day_str += ' {}'.format(precip_amount)

        draw.text((7, start_y + (count * line_height)),
                  day_str, inky_display.BLACK, font=this_font)

        count += 1

        # Only show max_items
        if (count > max_items):
            break


def paint_image():
    """Paints the entire display, calling other draw functions."""
    global inky_display

    img = Image.new("P", (inky_display.WIDTH, inky_display.HEIGHT))
    draw = ImageDraw.Draw(img)

    font_size = 20
    small_font_size = 18
    large_font_size = 72
    giant_font_size = 96
    giant_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                    giant_font_size)
    large_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                    large_font_size)
    regular_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                      font_size)
    small_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                    small_font_size)

    draw_outside_temp_text_line(inky_display, draw, giant_font,
                                large_font, small_font, 7, 0)

    # Align Awair rows with the visual top of the large temperature text.
    # The 96pt font bbox top=8, 20pt bbox top=1, so offset by the difference.
    temp_val = float(g_mqtt_data.get('weewx/sensor', {}).get('outdoor_temperature', 0))
    temp_font = large_font if temp_val >= 100 else giant_font
    _, temp_top, _, _ = temp_font.getbbox('{}\u00b0'.format(int(temp_val)))
    _, awair_top, _, _ = regular_font.getbbox('F')
    awair_start_y = temp_top - awair_top

    count = 0
    start_x = 175
    for awair_mqtt_room in g_awair_mqtt_rooms:
        draw_awair_text_line(inky_display, draw, regular_font,
                             start_x, awair_start_y + ((font_size+1)*count),
                             awair_mqtt_room)
        count += 1

    start_y = awair_start_y + ((font_size+1)*count)
    draw_kitchen_temp_text_line(inky_display, draw, regular_font,
                                start_x, start_y)
    draw_ext_awair_text_line(inky_display, draw, regular_font, 7, start_y)

    pool = g_mqtt_data.get('pool/sensor', {})
    pool_temp = pool.get('pool_temp')
    if pool_temp is not None:
        pool_str = 'Pool:{:.0f}\u00b0 P:{} H:{} S:{} L:{}'.format(
            pool_temp,
            pool.get('pool_pump', '?'),
            pool.get('pool_heater', '?'),
            pool.get('spa_heater', '?'),
            pool.get('pool_light', '?'))
        draw.text((7, inky_display.HEIGHT - 95 - 23),
                  pool_str, inky_display.BLACK, font=small_font)

    draw.line([(0, inky_display.HEIGHT - 95),
               (inky_display.WIDTH - 1, inky_display.HEIGHT - 95)],
              fill=inky_display.BLACK, width=2)

    draw_forecast(inky_display, draw, small_font, inky_display.HEIGHT - 110)

    # Show a small red "DC" badge in top-right corner if we've had a recent
    # disconnect. Clears after being shown once.
    global g_recent_disconnect
    if g_recent_disconnect:
        dc_font = ImageFont.truetype("freefont/FreeSansBold.ttf", 16)
        draw.text((inky_display.WIDTH - 28, 2), "DC",
                  inky_display.RED, font=dc_font)
        g_recent_disconnect = False

    inky_display.set_image(img)
    inky_display.show()


config = configparser.ConfigParser()
config.read('inky.conf')

mqtt_host = config.get('ALL', 'mqtt_host')
mqtt_host_port = int(config.get('ALL', 'mqtt_host_port'))
g_awair_mqtt_rooms = json.loads(config.get('AWAIR', 'mqtt_subs'))
g_awair_mqtt_ext_rooms = json.loads(config.get('AWAIR', 'mqtt_ext_subs'))
g_heartbeat_url = config.get('ALL', 'heartbeat_url', fallback=None)

client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

client.connect_async(mqtt_host, mqtt_host_port, 60)
client.loop_start()

inky_display = InkyWHAT("red")

time.tzset()
current_time = 0
last_update_time = 0

latitude = float(config.get('LOC', 'latitude'))
longitude = float(config.get('LOC', 'longitude'))
sun = Sun(latitude, longitude)

sunrise = sun.get_local_sunrise_time()
sunset = sun.get_local_sunset_time()
print('sunrise {}, sunset {}'.format(sunrise.strftime('%H:%M'),
                                     sunset.strftime('%H:%M')))

last_heartbeat_time = 0

while(1):
    # Moved sleep to top to allow for mqtt initialization
    time.sleep(10)

    # Log connection status periodically
    if not g_mqtt_connected:
        print('MQTT disconnected, waiting for reconnection...')
        continue

    current_time = int(time.time())

    # Ping heartbeat at most once every 10 minutes regardless of display hours
    if g_heartbeat_url and current_time - last_heartbeat_time >= 600:
        try:
            urllib.request.urlopen(g_heartbeat_url, timeout=5)
            last_heartbeat_time = current_time
        except Exception:
            pass

    time_since_last_update = current_time - last_update_time
    current_hour = int(time.strftime("%H", time.localtime()))
    current_minute = int(time.strftime("%M", time.localtime()))

    # Only update the display during certain hours on the :15's
    # and if it's not been updated for a minute to prevent multiple updates
    # in the same minute.
    current_total_minutes = current_hour * 60 + current_minute
    if (current_total_minutes >= 6 * 60 + 30 and
            current_total_minutes < 22 * 60 + 30 and
            current_minute % 15 == 0 and
            time_since_last_update > 60):
        # Check for minimum required MQTT data before painting
        if 'weewx/sensor' not in g_mqtt_data:
            print('Waiting for weewx/sensor data...')
            continue
        print('Updating display...')
        try:
            paint_image()
            last_update_time = current_time
        except Exception as e:
            print(f'Error updating display: {e}')
            traceback.print_exc()
            # Update timestamp even on error to prevent rapid retry storm
            # (e-ink displays have limited refresh cycles)
            last_update_time = current_time

    # Sample mqtt data
    # weewx/sensor -> {"outdoor_temperature": 43.9, "indoor_temperature": 70.5,
    # "outdoor_humidity": 77, "indoor_humidity": 47,
    # "outdoor_temp_change": -1.2, "rain_rate": 0, "last_day_rain": 0.00,
    # "wind_gust": 0, "indoor_temp_change": -0.9}
    # awair/Family Room/sensor -> {"location": "Family Room", "co2": 517.0,
    # "voc": 109.0, "datetime": "2020-04-04T05:29:59.805Z", "aqi": 6,
    # "dust": "1.0", "temp": "65.2", "humid": "48"}
    # awair/Master Bedroom/sensor -> {"dust": "2.0", "temp": "70.4",
    # "voc": 366.0, "datetime": "2020-04-02T05:02:55.232Z", "location":
    # "Master Bedroom", "co2": 725.0, "humid": "53", "aqi": 13}
