import logging
import sys
import usb.core
import usb.util
import sched
import time
import logging
import traceback

from threading import Timer
from datetime import datetime
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
#from pushover import Client

# Noise levels configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a logger
logger = logging.getLogger(__name__)

##############################################################################
#CONFIGUE THE BELOW SETTINGS TO YOUR CONVENIENCE
##############################################################################

# InfluxDB connection information
influxdb_host = "127.0.0.1"  # Set the InfluxDB host address (e.g., "192.168.194.240")
influxdb_port = 8086  # Set the InfluxDB port (default: 8086)
influxdb_token = "REPLACE WITH TOKEN"  # Set the InfluxDB token (within double quotes)
influxdb_org = "REPLACE WITH ORG"  # Set the InfluxDB organization name (e.g., "noise_buster")
influxdb_bucket = "REPLACE WITH DB"  # Set the InfluxDB bucket name (e.g., "noise_buster")
influxdb_timeout = 20000  # Set the InfluxDB timeout value in milliseconds (e.g., 20000)

# Pushover connection information (Optional) (uncomment if you want to use pushover!)
#pushover_user_key = "your_pushover_key_here"  # Set the Pushover user key (within double quotes) or leave empty to skip Pushover notifications
#pushover_api_token = "your_pushover_api_token_here"  # Set the Pushover API token (within double quotes) or leave empty to skip Pushover notifications

# Minimum noise level for logging events
minimum_noise_level = 40  # Set the minimum noise level for logging events (e.g., 80)

# Content of messages sent by Pushover (uncomment if you want to use pushover)
#pushover_message = "Lets bust these noise events"  # Set the content of the Pushover message (within double quotes)
#pushover_title = "Noise Buster"  # Set the title of the Pushover message (within double quotes)

# Message to display when starting the script
start_message = "Lets bust these noise events"  # Set the start message to display (within double quotes)

# InfluxDB measurement and location
influxdb_measurement = "noise_buster_events"  # Set the InfluxDB measurement name (within double quotes)
influxdb_location = "noise_buster"  # Set the location for InfluxDB measurement (within double quotes)

##############################################################################
# DO NOT TOUCH ANYTHING BELOW THIS LINE (EXCEPT IF YOU KNOW WHAT YOU ARE DOING)
##############################################################################


# Create a log manager for standard output
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stdout_handler.setFormatter(stdout_formatter)

# Create a logger for standard output
stdout_logger = logging.getLogger('stdout_logger')
stdout_logger.setLevel(logging.INFO)
stdout_logger.addHandler(stdout_handler)

# SPL-25 Buffer
buffer= bytearray([0x03, 0xa5, 0x01, 0xa6] )
buffer= buffer.ljust(32, b'\0')

try:
    #if pushover_user_key and pushover_api_token:
    #    client = Client(pushover_user_key, api_token=pushover_api_token)
    #    client.send_message(pushover_message, title=pushover_title)

    dev = usb.core.find(idVendor=0x1a86, idProduct=0xe010)
    interface = 0
    dev.set_configuration()

    dB = 0

    stdout_logger.info(start_message)

    # Connect to InfluxDB
    influxdb_client = InfluxDBClient(url=f"http://{influxdb_host}:{influxdb_port}", token=influxdb_token,
                                     org=influxdb_org, timeout=influxdb_timeout)
    write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)

    if influxdb_client.health():
        stdout_logger.info("Connected to InfluxDB successfully.")
        #if pushover_user_key and pushover_api_token:
        #    client.send_message("Successfully connected to InfluxDB", title=pushover_title)
    else:
        stdout_logger.info("Error connecting to InfluxDB.")
        #if pushover_user_key and pushover_api_token:
        #    client.send_message("Error connecting to InfluxDB", title=pushover_title)

    # Update noise level data
    def update():
        dev.write(2, buffer, 5000)

	#recieve/store data
        data = []
        data += dev.read(130, 32, 1000)

        global dB
        dB = ((data[12] << 8) + data[13]) / 10

        usb.util.dispose_resources(dev)

        if dB >= minimum_noise_level:
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            stdout_logger.info('%s, %.1f dB', timestamp, round(dB, 1))

            # Write data to InfluxDB
            data = [
                {
                    "measurement": influxdb_measurement,
                    "tags": {
                        "location": influxdb_location
                    },
                    "time": timestamp,
                    "fields": {
                        "level": round(dB, 1)
                    }
                }
            ]
            write_api.write(influxdb_bucket, record=data)

        t = Timer(0.5, update)
        t.start()

    # Start the update loop
    update()
except Exception as e:
   with open('error.log', 'a') as f:
        f.write(str(e) + "\n")
        f.write(traceback.format_exc())
        logger.error(str(e))
        logger.error(traceback.format_exc())
