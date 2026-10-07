"""Constants for the Essency Water Heater integration."""

from homeassistant.const import Platform

DOMAIN = "essency"

# Default backend configuration (ThingsBoard instance on Essency cloud)
DEFAULT_HOST = "https://server01.essencycloud.com:65443"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_HOST = "host"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_POWER_RATING = "power_rating"
CONF_SAVER_DURATION = "saver_duration"

# Rated power consumption of Essency EXR / E55R (Watts)
DEFAULT_POWER_RATING = 4500
# Default Water Saver duration (minutes)
DEFAULT_SAVER_DURATION = 10

# Supported Platforms
PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

# Essency Heat Mode Enum values
HEAT_MODE_UNKNOWN = -1
HEAT_MODE_OFF = 0
HEAT_MODE_SMART = 1
HEAT_MODE_SAVER = 2
HEAT_MODE_STANDARD = 3
HEAT_MODE_BOOST = 4
HEAT_MODE_VACATION = 5

HEAT_MODE_MAP = {
    HEAT_MODE_OFF: "Off",
    HEAT_MODE_SMART: "Smart",
    HEAT_MODE_SAVER: "Water Saver",
    HEAT_MODE_STANDARD: "Standard",
    HEAT_MODE_BOOST: "Boost",
    HEAT_MODE_VACATION: "Vacation",
}

HEAT_MODE_REVERSE_MAP = {v: k for k, v in HEAT_MODE_MAP.items()}
