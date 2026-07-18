#!/usr/bin/env python
"""
Query Growatt API to check what data they're receiving.
"""

import requests
import hashlib
import json
import os

# Load environment
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

ENV = load_env()

# Growatt API endpoints
API_URL = "https://server.growatt.com"

class GrowattAPI:
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False

    def login(self, username, password):
        """Login to Growatt portal."""
        # Try different password formats
        url = f"{API_URL}/login"

        # Try plain password first
        data = {
            "account": username,
            "password": password,
        }

        try:
            resp = self.session.post(url, data=data)
            result = resp.json()
            if result.get("result") == 1:
                print(f"Login successful (plain)")
                self.logged_in = True
                return True
        except:
            pass

        # Try MD5 hash
        pwd_hash = hashlib.md5(password.encode()).hexdigest()
        data = {
            "account": username,
            "password": pwd_hash,
        }

        try:
            resp = self.session.post(url, data=data)
            result = resp.json()
            if result.get("result") == 1:
                print(f"Login successful")
                self.logged_in = True
                return True
            else:
                print(f"Login failed: {result}")
                return False
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def get_plant_list(self):
        """Get list of plants/devices."""
        if not self.logged_in:
            print("Not logged in")
            return None

        url = f"{API_URL}/index/getPlantListTitle"
        try:
            resp = self.session.post(url)
            return resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_device_info(self, plant_id):
        """Get device info for a plant."""
        if not self.logged_in:
            return None

        url = f"{API_URL}/panel/getDevicesByPlantList"
        data = {"plantId": plant_id, "currPage": 1}
        try:
            resp = self.session.post(url, data=data)
            return resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_storage_status(self, serial):
        """Get storage/battery status."""
        if not self.logged_in:
            return None

        url = f"{API_URL}/panel/storage/getStorageStatusData"
        data = {"storageSn": serial}
        try:
            resp = self.session.post(url, data=data)
            return resp.json()
        except Exception as e:
            print(f"Error: {e}")
            return None

    def get_inverter_data(self, serial):
        """Get inverter real-time data."""
        if not self.logged_in:
            return None

        # Try different endpoints
        endpoints = [
            "/panel/inv/getInvRealTimeData",
            "/panel/getDeviceData",
            "/device/getDataByDeviceSn",
        ]

        for endpoint in endpoints:
            url = f"{API_URL}{endpoint}"
            data = {"deviceSn": serial, "sn": serial}
            try:
                resp = self.session.post(url, data=data)
                result = resp.json()
                if result.get("result") == 1 or "data" in result:
                    return result
            except:
                pass

        return None


def main():
    username = ENV.get('GROWATT_USERNAME', '')
    password = ENV.get('GROWATT_PASSWORD', '')

    if not username or not password:
        print("Please set GROWATT_USERNAME and GROWATT_PASSWORD in .env")
        print("These are your ShinePhone app login credentials.")
        return

    api = GrowattAPI()

    print("Logging in to Growatt portal...")
    if not api.login(username, password):
        return

    datalogger_serial = ENV.get('GROWATT_DATALOGGER_SERIAL', '')
    inverter_serial = ENV.get('GROWATT_INVERTER_SERIAL', '')

    print(f"\nDatalogger: {datalogger_serial}")
    print(f"Inverter: {inverter_serial}")

    # Get SPF real-time data - this is the main endpoint for SPF inverters
    print("\n" + "=" * 60)
    print("SPF REAL-TIME STATUS")
    print("=" * 60)

    # Try the SPF detail endpoint
    spf_detail_endpoints = [
        ("/panel/spf/getSPFDetailData", {"spfSn": inverter_serial}),
        ("/panel/spf/getSPFRealTimeData", {"spfSn": inverter_serial}),
        ("/panel/spf/getSPFStatusData", {"spfSn": inverter_serial}),
        ("/panel/spf/getSpfTotalData", {"spfSn": inverter_serial}),
        ("/panel/spf/getAllSPFStatus", {"spfSn": inverter_serial}),
    ]

    for endpoint, params in spf_detail_endpoints:
        try:
            url = f"{API_URL}{endpoint}"
            resp = api.session.post(url, data=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") == 1 or "obj" in data:
                    print(f"\n{endpoint}:")
                    print(json.dumps(data, indent=2))
        except Exception as e:
            pass

    # Try storage endpoints (SPF is classified as storage)
    print("\n" + "=" * 60)
    print("STORAGE STATUS DATA")
    print("=" * 60)

    storage_endpoints = [
        ("/panel/storage/getStorageStatusData", {"storageSn": inverter_serial}),
        ("/panel/storage/getStorageBatChart", {"storageSn": inverter_serial, "date": "2026-01-10"}),
        ("/panel/storage/getStorageTotalData", {"storageSn": inverter_serial}),
    ]

    for endpoint, params in storage_endpoints:
        try:
            url = f"{API_URL}{endpoint}"
            resp = api.session.post(url, data=params)
            if resp.status_code == 200:
                data = resp.json()
                print(f"\n{endpoint}:")
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"\n{endpoint}: ERROR - {e}")

    # Get device info
    print("\n" + "=" * 60)
    print("DEVICE INFO")
    print("=" * 60)

    plants = api.get_plant_list()
    if plants and len(plants) > 0:
        plant_id = plants[0].get('id')
        devices = api.get_device_info(plant_id)
        if devices and 'obj' in devices and 'datas' in devices['obj']:
            for dev in devices['obj']['datas']:
                print(f"\nDevice: {dev.get('sn')}")
                print(f"  Status: {dev.get('status')} (12=PV+Discharge, 2=Discharge, 5=PV Charge)")
                print(f"  Last Update: {dev.get('lastUpdateTime')}")
                print(f"  PAC: {dev.get('pac')} W")
                print(f"  Energy Today: {dev.get('eToday')} kWh")
                print(f"  Energy Total: {dev.get('eTotal')} kWh")


if __name__ == "__main__":
    main()
