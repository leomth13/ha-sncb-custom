"""Constants for the SNCB Train Tracker integration."""

DOMAIN = "sncb_train"

# Default polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 90

# API
API_BASE = "https://api.irail.be/v1"
API_VEHICLE = f"{API_BASE}/vehicle/"

# Config keys
CONF_VEHICLE_ID = "vehicle_id"
CONF_STATION = "station"
CONF_NAME = "name"

# Default monitored station
DEFAULT_STATION = "Gembloux"

# Attributes
ATTR_DELAY_MINUTES = "delay_minutes"
ATTR_PLATFORM = "platform"
ATTR_CURRENT_STATION = "current_station"
ATTR_STATUS = "status"
ATTR_OCCUPANCY = "occupancy"
ATTR_SCHEDULED_TIME = "scheduled_time"
ATTR_VEHICLE = "vehicle"
ATTR_SHORTNAME = "shortname"
ATTR_CANCELED = "canceled"
ATTR_LEFT_GEMBLOUX = "left_gembloux"
ATTR_ARRIVED_GEMBLOUX = "arrived_gembloux"
ATTR_LAST_UPDATE = "last_update"
