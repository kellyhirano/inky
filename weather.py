#!/usr/bin/env python3

import configparser
import json
import sys
import time
import json
import re
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


def on_connect(client, userdata, flags, rc):
    """The callback for when the client receives a CONNACK server response."""

    print("Connected with result code "+str(rc))

    mqtt_subscriptions = [("weathergov/forecast", 0),
                          ("weathergov/warnings", 0),
                          ("weewx/sensor", 0),
                          ("purpleair/sensor", 0)]
    for room_list in (g_awair_mqtt_rooms, g_awair_mqtt_ext_rooms):
        for awair_mqtt_room in room_list:
            print(awair_mqtt_room)
            room_tuple = ("awair/" + awair_mqtt_room + "/sensor", 0)
            mqtt_subscriptions.append(room_tuple)

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(mqtt_subscriptions)


def on_message(client, userdata, msg):
    """The callback for when a PUBLISH message is received from the server."""
    global g_mqtt_data

    print("MESSAGE: "+msg.topic+" -> "+str(msg.payload.decode('UTF-8')))
    message_data = json.loads(str(msg.payload.decode('UTF-8')))

    g_mqtt_data[msg.topic] = message_data


def draw_outside_temp_text_line(inky_display, draw, main_font,
                                small_main_font, diff_font, start_x, start_y):
    """Draws the outside temperature and last hour temperature delta."""
    global g_mqtt_data

    temp = g_mqtt_data['weewx/sensor']['outdoor_temperature']
    temp_delta = g_mqtt_data['weewx/sensor']['outdoor_temp_change']
    temp_24h_delta = g_mqtt_data['weewx/sensor']['outdoor_24h_temp_change']

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
    draw.text((delta_x + delta_x_offset, start_y + delta_y_offset + 52),
              delta_str, inky_display.BLACK, font=diff_font)
    draw.text((delta_x, start_y + 72),
              delta_24h_str, inky_display.BLACK, font=diff_font)

    y_coord = start_y + 96 + 5

    rain_rate = g_mqtt_data['weewx/sensor']['rain_rate']
    last_day_rain = g_mqtt_data['weewx/sensor']['last_day_rain']
    wind_gust = g_mqtt_data['weewx/sensor']['wind_gust']
    aqi = g_mqtt_data['purpleair/sensor']['st_aqi']
    lrapa_aqi = g_mqtt_data['purpleair/sensor']['st_lrapa_aqi']
    last_hour_aqi = g_mqtt_data['purpleair/sensor']['st_aqi_last_hour']
    last_hour_lrapa_aqi \
        = g_mqtt_data['purpleair/sensor']['st_lrapa_aqi_last_hour']
    aqi_desc = g_mqtt_data['purpleair/sensor']['st_aqi_desc']

    aqi_str = 'A{} {:+d}  L{} {:+d}'.format(aqi, last_hour_aqi,
                                            lrapa_aqi, last_hour_lrapa_aqi)
    draw.text((start_x, y_coord), aqi_str, inky_display.BLACK, font=diff_font)
    y_coord += 18 + 5

    if (aqi > 100):
        draw.text((start_x, y_coord), aqi_desc,
                  inky_display.RED, font=diff_font)
        y_coord += 18 + 5

    if (wind_gust >= 10):
        wind_str = 'GUST: {}'.format(wind_gust)
        draw.text((start_x, y_coord),
                  wind_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 5

    if (last_day_rain > 0):
        last_day_rain_str = '24h: {}"'.format(last_day_rain)
        if (rain_rate > 0):
            last_day_rain_str += ' @{:.2f}"/h'.format(rain_rate)
        draw.text((start_x, y_coord),
                  last_day_rain_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 5


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
                  topic_substr[0], inky_display.BLACK,
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
        indoor_temp = g_mqtt_data[topic_name]['indoor_temperature']
        indoor_temp_change = g_mqtt_data[topic_name]['indoor_temp_change']

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

    if 'weathergov/warnings' in g_mqtt_data:
        for warning in g_mqtt_data['weathergov/warnings']:
            day_str = '{}: {}'.format(warning['title'].title(),
                                      warning['desc'])
            str_w, str_h = this_font.getsize(day_str)
            draw.text((7, start_y + (count * str_h)),
                      day_str, inky_display.RED, font=this_font)

            count += 1

            # Only show max_items
            # Return here vs break later
            if (count > max_items):
                return

    for day_info in g_mqtt_data['weathergov/forecast']:
        time_str = day_info['day']
        time_str = re.sub('BIRTHDAY', 'BDAY', time_str)
        time_str = re.sub(r'(\S{3})\S*DAY', r'\1', time_str)
        time_str = re.sub(r'THIS ', r'', time_str)

        day_str = '{}: {}, {}\u00b0'.format(time_str,
                                            day_info['forecast'],
                                            day_info['temp'])

        if day_info['precip_amount']:
            day_str += ' {}'.format(day_info['precip_amount'])

        str_w, str_h = this_font.getsize(day_str)
        draw.text((7, start_y + (count * str_h)),
                  day_str, inky_display.BLACK, font=this_font)

        count += 1

        # Only show max_items
        if (count > max_items):
            break


def paint_image():
    """Paints the entire display, calling other draw functions."""
    inky_display = InkyWHAT("red")

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

    count = 0
    start_x = 175
    start_y = 7
    for awair_mqtt_room in g_awair_mqtt_rooms:
        draw_awair_text_line(inky_display, draw, regular_font,
                             start_x, start_y + ((font_size+1)*count),
                             awair_mqtt_room)
        count += 1

    start_y = start_y + ((font_size+1)*count)
    draw_kitchen_temp_text_line(inky_display, draw, regular_font,
                                start_x, start_y)
    draw_ext_awair_text_line(inky_display, draw, regular_font, 7, start_y)

    draw.line([(0, inky_display.HEIGHT - 95),
               (inky_display.WIDTH - 1, inky_display.HEIGHT - 95)],
              fill=inky_display.BLACK, width=2)

    draw_forecast(inky_display, draw, small_font, inky_display.HEIGHT - 110)

    inky_display.set_image(img)
    inky_display.show()


config = configparser.ConfigParser()
config.read('inky.conf')

mqtt_host = config.get('ALL', 'mqtt_host')
mqtt_host_port = int(config.get('ALL', 'mqtt_host_port'))
g_awair_mqtt_rooms = json.loads(config.get('AWAIR', 'mqtt_subs'))
g_awair_mqtt_ext_rooms = json.loads(config.get('AWAIR', 'mqtt_ext_subs'))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect_async(mqtt_host, mqtt_host_port, 60)
client.loop_start()

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

while(1):
    # Moved sleep to top to allow for mqtt initialization
    time.sleep(10)

    current_time = int(time.time())
    time_since_last_update = current_time - last_update_time
    current_hour = int(time.strftime("%H", time.localtime()))
    current_minute = int(time.strftime("%M", time.localtime()))

    # Only update the display during certain hours on the :15's
    # and if it's not been updated for a minute to prevent multiple updates
    # in the same minute.
    if (current_hour >= 7 and current_hour <= 23 and
            current_minute % 15 == 0 and
            time_since_last_update > 60):
        print('Updating display...')
        paint_image()
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
