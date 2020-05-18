#!/usr/bin/env python3

import configparser
import json
import sys
import time
import paho.mqtt.client as mqtt

from PIL import Image, ImageFont, ImageDraw
from font_hanken_grotesk import HankenGroteskBold, HankenGroteskMedium
from inky import InkyWHAT

# Global for data storage
g_mqtt_data = {}
g_awair_mqtt_rooms = ("Laundry Room", "Family Room", "Cindy's Room",
                      "Kyle's Room", "Living Room", "Dining Room",
                      "Guest Room", "Master Bedroom")


def on_connect(client, userdata, flags, rc):
    """The callback for when the client receives a CONNACK server response."""

    print("Connected with result code "+str(rc))

    mqtt_subscriptions = [("weathergov/forecast", 0),
                          ("weewx/sensor", 0),
                          ("purpleair/sensor", 0)]
    for awair_mqtt_room in g_awair_mqtt_rooms:
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

    print(g_mqtt_data)


def draw_outside_temp_text_line(inky_display, draw, main_font,
                                diff_font, start_x, start_y):
    """Draws the outside temperature and last hour temperature delta."""
    global g_mqtt_data

    temp = g_mqtt_data['weewx/sensor']['outdoor_temperature']
    temp_delta = g_mqtt_data['weewx/sensor']['outdoor_temp_change']

    temp_str = '{}\u00b0'.format(int(temp))
    draw.text((start_x, start_y), temp_str, inky_display.BLACK, font=main_font)

    # Put the temp change right under the degree symbol of the outside temp
    # Double-digit increases (with decimal) is wider. Either drop the decimal
    # over 10 or fix the width. Dropping the decimal is easier right now.
    delta_str = '{:+.1f}\u00b0'.format(float(temp_delta))
    delta_x = 123
    if (temp_delta >= 10):
        delta_x = 115
    draw.text((delta_x, start_y + 70),
              delta_str, inky_display.BLACK, font=diff_font)

    y_coord = start_y + 96 + 5

    rain_rate = g_mqtt_data['weewx/sensor']['rain_rate']
    last_day_rain = g_mqtt_data['weewx/sensor']['last_day_rain']
    wind_gust = g_mqtt_data['weewx/sensor']['wind_gust']
    aqi = g_mqtt_data['purpleair/sensor']['st_aqi']

    wind_str = 'AQI: {}'.format(aqi)
    draw.text((start_x, y_coord), wind_str, inky_display.BLACK, font=diff_font)
    y_coord += 18 + 5

    if (wind_gust >= 10):
        wind_str = 'GUST: {}'.format(wind_gust)
        draw.text((start_x, y_coord),
                  wind_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 5

    if (last_day_rain > 0):
        last_day_rain_str = '24h: {}"'.format(last_day_rain)
        if (rain_rate > 0):
            last_day_rain_str += ' @ {:.2f}"/h'.format(rain_rate)
        draw.text((start_x, y_coord),
                  last_day_rain_str, inky_display.BLACK, font=diff_font)
        y_coord += 18 + 5


def draw_awair_temp_text_line(inky_display, draw, this_font, start_x, start_y,
                              topic_substr):
    """Draws the single line of text for each Awair device."""

    topic_name = 'awair/' + topic_substr + '/sensor'
    if (topic_name in g_mqtt_data):
        # Intentional space at the end to deal with library clipping
        temp_str = '{} {}\u00b0 {:+.1f}\u00b0 {} '\
            .format(topic_substr[0],
                    g_mqtt_data[topic_name]['temp'],
                    float(g_mqtt_data[topic_name]['last_hour_temp']),
                    int(g_mqtt_data[topic_name]['co2']))
        draw.text((start_x, start_y),
                  temp_str, inky_display.BLACK, font=this_font)


def draw_forecast(inky_display, draw, this_font, start_y):
    """Draws the lines of text for the upcoming weather forecast."""
    # Sample data
    # {'precip_chance': '1', 'temp': '50', 'day': 'OVERNIGHT',
    # 'forecast': 'Chance rain', 'precip_serverity': 2}
    global g_mqtt_data

    count = 1

    for day_info in g_mqtt_data['weathergov/forecast']:
        day_str = '{}: {}, {}\u00b0'.format(day_info['day'],
                                            day_info['forecast'],
                                            day_info['temp'])
        str_w, str_h = this_font.getsize(day_str)
        draw.text((7, start_y + (count * str_h)),
                  day_str, inky_display.BLACK, font=this_font)

        # Only show four items
        if (count > 3):
            break

        count += 1


def draw_update_time(inky_display, draw, this_font, start_y):
    """Draws the timestamp showing the last updated time."""

    time_str = time.strftime("%a @ %H:%M", time.localtime())
    draw.text((7, start_y), time_str, inky_display.BLACK, font=this_font)


def paint_image():
    """Paints the entire display, calling other draw functions."""
    inky_display = InkyWHAT("black")
    inky_display.set_border(inky_display.BLACK)

    img = Image.new("P", (inky_display.WIDTH, inky_display.HEIGHT))
    draw = ImageDraw.Draw(img)

    font_size = 20
    small_font_size = 18
    giant_font_size = 96
    giant_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                    giant_font_size)
    regular_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                      font_size)
    small_font = ImageFont.truetype("freefont/FreeSansBold.ttf",
                                    small_font_size)

    draw_outside_temp_text_line(inky_display, draw, giant_font,
                                small_font, 7, 0)

    count = 0
    start_x = 175
    start_y = 7
    for awair_mqtt_room in g_awair_mqtt_rooms:
        draw_awair_temp_text_line(inky_display, draw, regular_font,
                                  start_x, start_y + ((font_size+1)*count),
                                  awair_mqtt_room)
        count += 1

    draw.line([(0, inky_display.HEIGHT - 95),
               (inky_display.WIDTH - 1, inky_display.HEIGHT - 95)],
              fill=inky_display.BLACK, width=2)

    draw_forecast(inky_display, draw, small_font, inky_display.HEIGHT - 110)

    draw_update_time(inky_display, draw, small_font, inky_display.HEIGHT - 120)

    inky_display.set_image(img)
    inky_display.show()


config = configparser.ConfigParser()
config.read('mqtt.conf')

mqtt_host = config.get('ALL', 'mqtt_host')
mqtt_host_port = int(config.get('ALL', 'mqtt_host_port'))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(mqtt_host, mqtt_host_port, 60)

time.tzset()
current_time = 0
last_update_time = 0

while(1):
    print('LOOP')
    print(g_mqtt_data)
    current_time = int(time.time())
    time_since_last_update = current_time - last_update_time
    current_hour = int(time.strftime("%H", time.localtime()))
    current_minute = int(time.strftime("%M", time.localtime()))
    print('Seconds since last update: ' + str(time_since_last_update))

    # Only update the display during certain hours on the :15's
    # and if it's not been updated for a while
    if (current_hour >= 7 and current_hour <= 23 and
            current_minute % 15 == 0 and
            time_since_last_update > 900 and
            'weewx/sensor' in g_mqtt_data and
            'awair/Family Room/sensor' in g_mqtt_data and
            'awair/Master Bedroom/sensor' in g_mqtt_data and
            'awair/Living Room/sensor' in g_mqtt_data):
        print('INSIDE')
        paint_image()
        last_update_time = current_time

    client.loop()
    time.sleep(5)

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
