# Essency Water Heater Integration for Home Assistant

A custom HACS-compatible Home Assistant integration for **Essency EXR / E55R** smart on-demand electric tank water heaters.

Communicates with Essency's cloud backend (ThingsBoard IoT) to provide full monitoring, controls, and **automatic energy (kWh) tracking for the Home Assistant Energy Dashboard**.

---

## Features

### 🚰 Water Heater Entity (`water_heater`)
* **Set Target Temperature:** Adjust temperature setpoint (110°F – 140°F).
* **Operation Modes:** 
  * `Electric / Standard`: Normal operation.
  * `Eco / Water Saver`: Energy saving profile.
  * `Performance / Boost`: High output mode.
  * `Off`: Standby.
* **Away Mode:** Toggle vacation mode on/off directly from Home Assistant.
* **Current Temperature / Availability:** Displays calculated hot water temperature based on remaining capacity.

### ⚡ Energy & Power Tracking (Energy Dashboard Ready)
* **Estimated Power (`sensor.*_estimated_power`):** Real-time power draw in Watts (`4500 W` when heating elements are active, `0 W` when idle).
* **Estimated Energy Usage (`sensor.*_estimated_energy_usage`):** Continuous, persistent cumulative energy consumption in **kWh** (`total_increasing`). 
  > **Note:** Automatically selectable in the **Home Assistant Energy Dashboard** under **Individual Devices**!

### 📊 Sensors & Metrics
* **Hot Water Available (`%`):** Live tank hot water reservoir percentage (`0% – 100%`).
* **Target Temperature:** Target setpoint in °F.
* **Operating Mode:** Current mode (Standard, Boost, Water Saver, Vacation).
* **Heat Source Status:** Diagnostic status indicating if heating elements are energized.
* **Cycle Counters:** Lifetime counters for Boost, Vacation, and Saver activations.
* **Device Network & Diagnostics:** Device local IP (e.g. `192.168.1.50`), Firmware version (`V-1-6-8`), Wi-Fi firmware (`WF-1-6-8`).

### 🔘 Switches & Controls
* **Boost Mode Switch:** Temporarily trigger or cancel a 1-hour hot water boost.
* **Water Saver Switch:** Toggle Water Saver mode.
* **Vacation Mode Switch:** Toggle Vacation mode.

### ⏱️ Number Configuration
* **Water Saver Duration (`number.*_water_saver_duration`):** Slider entity to adjust the active duration (1 – 30 minutes) for Water Saver mode directly from your dashboards.

### 🔴 Binary Sensors
* **Heating Active:** Engaged when heating elements are actively drawing power.
* **Cloud Connection:** Monitors connectivity status to the cloud backend.
* **Firmware Updating:** Alerts if an OTA update is running.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. In the **Repository** field, enter `https://github.com/vector-sec/essency-hacs`.
4. Set the **Category** to `Integration` and click **Add**.
5. Find **Essency Water Heater** in HACS and click **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/essency` directory into your Home Assistant configuration directory under `custom_components/` (e.g. `/config/custom_components/essency`).
2. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **Essency Water Heater**.
3. Enter your **MyEssency Account Email** and **Password**.
4. *(Optional)* Configure:
   * **Update Interval:** Default is `30` seconds (10 – 300 seconds).
   * **Heating Element Power:** Default is `4500` Watts (standard rating for Essency EXR 55-gallon dual element).
5. Click **Submit**. Your water heater device, entities, and sensors will be automatically created.

### Reconfiguration & Options
You can change integration options at any time without re-adding the device:
1. Navigate to **Settings** -> **Devices & Services** -> **Essency Water Heater**.
2. Click **Configure**.
3. Adjust **Update Interval**, **Heating Element Power Rating**, or the default **Water Saver Duration**.

---

## Adding to Home Assistant Energy Dashboard

1. Navigate to **Settings** -> **Dashboards** -> **Energy**.
2. Under **Individual devices**, click **Add Device**.
3. Select **Estimated Energy Usage** (`sensor.essency_water_heater_estimated_energy_usage`).
4. Click **Save**. 

Your water heater's energy consumption will now appear alongside your household electricity and HVAC metrics!

