# inky
A script designed to display weather information on a [Pimoroni Inky wHAT](https://shop.pimoroni.com/products/inky-what?variant=13590497624147). It's reading data from my local mqtt server that's using specific topic names. I need to clean up that code and will link to that as well.

A mqtt.conf file must be created. It's a standard configparser doc that must
define a MQTT server and it's port (default port is 1883). Rooms (and optional
rooms at a different location) must also be defined in this config file.
