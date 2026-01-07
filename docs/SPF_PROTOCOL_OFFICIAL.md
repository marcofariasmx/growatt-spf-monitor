# Growatt OffGrid SPF5000 Modbus RS485 RTU Protocol

**Version:** V0.11  
**Date:** 2017-8-09  
**Author:** Growatt New Energy CO., LTD

---

## Version History

| No. | Version | Date       | Notice                                                                                                                           | Signature    |
|-----|---------|------------|----------------------------------------------------------------------------------------------------------------------------------|--------------|
| 1   | V0.01   | 2016-12-27 | The first version                                                                                                                | Zhenyuan.li  |
| 2   | V0.02   | 2017-1-12  | 1. Modify input reg 0, system status; 2. Add input reg 44 for send DTC to server to identify machine type                        | Zhenyuan.li  |
| 3   | V0.03   | 2017-2-6   | 1. Modify Holding reg 29, Model Low                                                                                              | Zhenyuan.li  |
| 4   | V0.04   | 2017-2-16  | 1. Add Holding reg 39, battery type; 2. Modify Holding reg 0, On/Off; 3. Modify Input reg 46, Production Line Mode               | Zhenyuan.li  |
| 5   | V0.05   | 2017-3-10  | 1. Modify Input reg 17, 28, 29, Battery Voltage                                                                                  | Zhenyuan.li  |
| 6   | V0.06   | 2017-3-15  | 1. Modify Holding reg 29, Model L; Add S bit for Aging Mode                                                                      | Zhenyuan.li  |
| 7   | V0.07   | 2017-5-25  | 1. Modify Hold reg 29; 2. Modify Input reg 36~39; 3. Add Input reg 68~82                                                         | Zhenyuan.li  |
| 8   | V0.08   | 2017-5-26  | 1. Add Input reg 90~131 for BMS information                                                                                      | Zhenyuan.li  |
| 9   | V0.09   | 2017-7-4   | 1. Add Input reg 135~179 for SolarCharger information                                                                            | Zhenyuan.li  |
| 10  | V0.10   | 2017-7-12  | 1. Add Input reg 83~86 for Machine Rate Power                                                                                    | Zhenyuan.li  |
| 11  | V0.11   | 2017-8-09  | 1. Change Machine Rate Power from Input Reg 83~86 to Holding Reg 76~79; 2. Adjust BMS info, add BMS2 info; 3. Add Solar Charger Info at Input Reg 180~224 | Zhenyuan.li  |

---

## Table of Contents

1. [Data Format](#1-data-format)
2. [Command Format](#2-command-format)
3. [Device Message Transmission Mode / Framing](#3-device-message-transmission-mode--framing)
4. [Register Map](#4-register-map)
5. [Set Address](#5-set-address)
6. [Notice](#6-notice)

---

## 1. Data Format

| Address | Function | Data    | CRC Check |
|---------|----------|---------|-----------|
| 8 bits  | 8 bits   | N×8bits | 16bits    |

- Valid slave device addresses are in the range of **0 – 247** decimal
- Individual slave devices are assigned addresses in the range of **1 – 247**
- **0** is the broadcast address
- It is **16 bits (two bytes) unsigned integer** for each holding and input register

---

## 2. Command Format

### Function 3: Read Holding Register

#### Query

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 03            |
| Starting Address Hi     | 00            |
| Starting Address Lo     | 6B            |
| No. of Points Hi        | 00            |
| No. of Points Lo        | 03            |
| Error Check (LRC or CRC)| —             |

#### Response

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 03            |
| Byte Count              | 06            |
| Data Hi (Register 40108)| 02            |
| Data Lo (Register 40108)| 2B            |
| Data Hi (Register 40109)| 00            |
| Data Lo (Register 40109)| 00            |
| Data Hi (Register 40110)| 00            |
| Data Lo (Register 40110)| 64            |
| Error Check (LRC or CRC)| —             |

#### Response Error
```
11 0x80|0x03 Errornum CRC    (Errornum as a byte)
```

---

### Function 4: Read Input Register

#### Query

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 04            |
| Starting Address Hi     | 00            |
| Starting Address Lo     | 08            |
| No. of Points Hi        | 00            |
| No. of Points Lo        | 01            |
| Error Check (LRC or CRC)| —             |

#### Response

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 04            |
| Byte Count              | 02            |
| Data Hi (Register 30009)| 00            |
| Data Lo (Register 30009)| 0A            |
| Error Check (LRC or CRC)| —             |

#### Response Error
```
11 0x80|0x04 Errornum CRC    (Errornum as a byte)
```

---

### Function 6: Preset Single Register

#### Query

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 06            |
| Register Address Hi     | 00            |
| Register Address Lo     | 01            |
| Preset Data Hi          | 00            |
| Preset Data Lo          | 03            |
| Error Check (LRC or CRC)| —             |

#### Response

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 06            |
| Register Address Hi     | 00            |
| Register Address Lo     | 01            |
| Preset Data Hi          | 00            |
| Preset Data Lo          | 03            |
| Error Check (LRC or CRC)| —             |

#### Response Error
```
11 0x80|0x06 Errornum CRC    (Errornum as a byte)
```

---

### Function 16: Preset Multiple Registers

#### Query

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 10            |
| Starting Address Hi     | 00            |
| Starting Address Lo     | 01            |
| No. of Registers Hi     | 00            |
| No. of Registers Lo     | 02            |
| Byte Count              | 04            |
| Data Hi                 | 00            |
| Data Lo                 | 0A            |
| Data Hi                 | 01            |
| Data Lo                 | 02            |
| Error Check (LRC or CRC)| —             |

#### Response

| Field Name              | Example (Hex) |
|-------------------------|---------------|
| Slave Address           | 11            |
| Function                | 10            |
| Starting Address Hi     | 00            |
| Starting Address Lo     | 01            |
| No. of Registers Hi     | 00            |
| No. of Registers Lo     | 02            |
| Error Check (LRC or CRC)| —             |

#### Response Error
```
11 0x80|0x10 Errornum CRC    (Errornum as a byte)
```

---

## 3. Device Message Transmission Mode / Framing

### RTU Mode

When controllers are setup to communicate on a Modbus network using RTU (Remote Terminal Unit) mode, each 8-bit byte in a message contains two 4-bit hexadecimal characters. Each message must be transmitted in a continuous stream.

### Format for Each Byte in RTU Mode

| Parameter              | Value                                            |
|------------------------|--------------------------------------------------|
| Coding System          | 8-bit binary, hexadecimal 0-9, A-F               |
| Bits per Byte          | 1 start bit, 8 data bits (LSB first), No parity, 1 stop bit |
| Error Check Field      | Cyclical Redundancy Check (CRC)                  |
| Baud Rate              | 9600 bps                                         |

### Timing Requirements

| Parameter                    | Value                                                    |
|------------------------------|----------------------------------------------------------|
| Minimum CMD period (RS485 Timeout) | 850ms (Suggestion: 1s)                              |
| Maximum read data length     | 45 words per read command                                |
| Maximum update data length   | 45 words per preset command                              |

### Register Range Rules

Read or update register numbers should be in the range of multiples of 45:
- ✅ `1~45` or `96~123` are OK
- ❌ `40~60` is **NOT** OK

> **Note:** Except the CEI0-21 and VDE-AR-N 4105 power management registers, you should refer to the manufacturer's suggestion when writing other registers.

---

## 4. Register Map

> **Note:** It is 16 bits (two bytes) unsigned integer for each holding and input register.

### 4.1 Holding Registers

| Reg No. | Variable Name      | Description                          | Write | Value                                                      | Unit    | Initial |
|---------|-------------------|--------------------------------------|-------|------------------------------------------------------------|---------|---------|
| 00      | On/Off            | Standby On/Off and AC output state   |       | 0x0000: Standby off, Output enable; 0x0001: Standby on, Output enable; 0x0100: Standby off, Output disable; 0x0101: Standby on, Output disable | | 0 |
| 01      | OutputConfig      | AC output set                        | W     | 0: BAT First; 1: PV First; 2: UTI First                    |         | 0       |
| 02      | ChargeConfig      | Charge source set                    | W     | 0: PV first; 1: PV&UTI; 2: PV Only                         |         | 0       |
| 03      | UtiOutStart       | Uti Output Start Time                | W     | 0-23                                                       | H(hour) | 0       |
| 04      | UtiOutEnd         | Uti Output End Time                  | W     | 0-23                                                       | H(hour) | 0       |
| 05      | UtiChargeStart    | Uti Charge Start Time                | W     | 0-23                                                       | H(hour) | 0       |
| 06      | UtiChargeEnd      | Uti Charge End Time                  | W     | 0-23                                                       | H(hour) | 0       |
| 07      | PVModel           | PV Input Mode                        | W     | 0: Independent; 1: Parallel                                |         | 0       |
| 08      | ACInModel         | AC Input Mode                        | W     | 0: APL, 90-280VAC; 1: UPS, 170-280VAC                      |         | 0       |
| 09      | Fw version H      | Firmware version (high)              |       |                                                            | ASCII   |         |
| 10      | Fw version M      | Firmware version (middle)            |       |                                                            |         |         |
| 11      | Fw version L      | Firmware version (low)               |       |                                                            |         |         |
| 12      | Fw version2 H     | Control Firmware version (high)      |       |                                                            | ASCII   |         |
| 13      | Fw version2 M     | Control Firmware version (middle)    |       |                                                            |         |         |
| 14      | Fw version2 L     | Control Firmware version (low)       |       |                                                            |         |         |
| 15      | LCD language      | LCD language                         | W     | 0-1                                                        |         | 1 (English) |
| 18      | OutputVoltType    | Output Volt Type                     | W     | 0: 208VAC; 1: 230VAC; 2: 240VAC                            |         | 1       |
| 19      | OutputFreqType    | Output Freq Type                     | W     | 0: 50Hz; 1: 60Hz                                           |         | 0       |
| 20      | OverLoadRestart   | Over Load Restart                    | W     | 0: Yes; 1: No; 2: Switch to UTI                            |         | 0       |
| 21      | OverTempRestart   | Over Temperature Restart             | W     | 0: Yes; 1: No                                              |         | 0       |
| 22      | BuzzerEN          | Buzzer on/off enable                 | W     | 1: Enable; 0: Disable                                      |         | 1       |
| 23-27   | Serial NO. 5-1    | Serial number                        | W     |                                                            | ASCII   |         |
| 28      | Module H          | Inverter Module (high)               | W     |                                                            |         |         |
| 29      | Module L          | Inverter Module (low)                | W     | P-battery type: 0: Lead_Acid, 1: Lithium, 2: CustomLead_Acid; U-user type: 0-3; M-power rate: 3: 3KW, 5: 5KW; S-Aging: 0: Normal, 1: Aging |  |  |
| 30      | Com Address       | Communicate address                  | W     | 1~254                                                      |         | 1       |
| 31      | FlashStart        | Update firmware                      | W     | 0x0001: own; 0x0100: control board                         |         |         |
| 32      | Reset User Info   | Reset User Information               | W     | 0x0001                                                     |         |         |
| 33      | Reset to factory  | Reset to factory                     | W     | 0x0001                                                     |         |         |
| 34      | MaxChargeCurr     | Max Charge Current                   | W     | 10~130                                                     | 1A      | 70      |
| 35      | BulkChargeVolt    | Bulk Charge Volt                     | W     | 500~580                                                    | 0.1V    | 564     |
| 36      | FloatChargeVolt   | Float Charge Volt                    | W     | 500~560                                                    | 0.1V    | 540     |
| 37      | BatLowToUtiVolt   | Bat Low Volt Switch To Uti           | W     | 444~514                                                    | 0.1V    | 464     |
| 38      | FloatChargeCurr   | Float Charge Current                 | W     | 0~80                                                       | 0.1A    |         |
| 39      | Battery Type      | Battery Type                         | W     | 0: Lead_Acid; 1: Lithium; 2: CustomLead_Acid               |         | 1       |
| 40      | Aging Mode        | Aging Mode                           | W     | 0: Normal Mode; 1: Aging Mode                              |         | 0       |
| 43      | DTC               | Device Type Code                     |       | See DTC table                                              |         |         |
| 45      | Sys Year          | System time - year                   | W     | Year offset is 2000                                        |         |         |
| 46      | Sys Month         | System time - Month                  | W     |                                                            |         |         |
| 47      | Sys Day           | System time - Day                    | W     |                                                            |         |         |
| 48      | Sys Hour          | System time - Hour                   | W     |                                                            |         |         |
| 49      | Sys Min           | System time - Min                    | W     |                                                            |         |         |
| 50      | Sys Sec           | System time - Second                 | W     |                                                            |         |         |
| 59-66   | Manufacturer Info | Manufacturer information             |       |                                                            | ASCII   |         |
| 67-70   | FW Build No.      | Firmware Build Numbers               |       |                                                            | ASCII   |         |
| 72      | Sys Weekly        | Sys Weekly                           | W     | 0-6                                                        |         |         |
| 73      | ModbusVersion     | Modbus Version                       |       | Eg: 207 is V2.07                                           | Int(16bits) |     |
| 76      | Rate Watt H       | Rate active power (high)             |       |                                                            | 0.1W    |         |
| 77      | Rate Watt L       | Rate active power (low)              |       |                                                            | 0.1W    |         |
| 78      | Rate VA H         | Rate apparent power (high)           |       |                                                            | 0.1VA   |         |
| 79      | Rate VA L         | Rate apparent power (low)            |       |                                                            | 0.1VA   |         |
| 80      | Factory           | The ODM Info code                    |       |                                                            |         |         |
| 162     | BLVersion2        | Boot loader version2                 | R     |                                                            |         |         |

---

### 4.2 Input Registers

> **Note:** Some of input registers can be written by manufacturer (write address offset is 0x1000, start at 0x1000). Cannot be written by customer.

| Reg No. | Variable Name        | Description                         | Value                                                                                              | Unit    |
|---------|---------------------|-------------------------------------|----------------------------------------------------------------------------------------------------|---------|
| 00      | System Status       | System run state                    | 0: Standby; 1: (No Use); 2: Discharge; 3: Fault; 4: Flash; 5: PV charge; 6: AC charge; 7: Combine charge; 8: Combine charge and Bypass; 9: PV charge and Bypass; 10: AC charge and Bypass; 11: Bypass; 12: PV charge and Discharge |         |
| 01      | Vpv1                | PV1 voltage                         |                                                                                                    | 0.1V    |
| 02      | Vpv2                | PV2 voltage                         |                                                                                                    | 0.1V    |
| 03      | Ppv1 H              | PV1 charge power (high)             |                                                                                                    | 0.1W    |
| 04      | Ppv1 L              | PV1 charge power (low)              |                                                                                                    | 0.1W    |
| 05      | Ppv2 H              | PV2 charge power (high)             |                                                                                                    | 0.1W    |
| 06      | Ppv2 L              | PV2 charge power (low)              |                                                                                                    | 0.1W    |
| 07      | Buck1Curr           | Buck1 current                       |                                                                                                    | 0.1A    |
| 08      | Buck2Curr           | Buck2 current                       |                                                                                                    | 0.1A    |
| 09      | OP_Watt H           | Output active power (high)          |                                                                                                    | 0.1W    |
| 10      | OP_Watt L           | Output active power (low)           |                                                                                                    | 0.1W    |
| 11      | OP_VA H             | Output apparent power (high)        |                                                                                                    | 0.1VA   |
| 12      | OP_VA L             | Output apparent power (low)         |                                                                                                    | 0.1VA   |
| 13      | ACChr_Watt H        | AC charge watt (high)               |                                                                                                    | 0.1W    |
| 14      | ACChr_Watt L        | AC charge watt (low)                |                                                                                                    | 0.1W    |
| 15      | ACChr_VA H          | AC charge apparent power (high)     |                                                                                                    | 0.1VA   |
| 16      | ACChr_VA L          | AC charge apparent power (low)      |                                                                                                    | 0.1VA   |
| 17      | Bat Volt            | Battery volt (M3)                   |                                                                                                    | 0.01V   |
| 18      | BatterySOC          | Battery SOC                         | 0~100                                                                                              | 1%      |
| 19      | Bus Volt            | Bus Voltage                         |                                                                                                    | 0.1V    |
| 20      | Grid Volt           | AC input Volt                       |                                                                                                    | 0.1V    |
| 21      | Line Freq           | AC input frequency                  |                                                                                                    | 0.01Hz  |
| 22      | OutputVolt          | AC output Volt                      |                                                                                                    | 0.1V    |
| 23      | OutputFreq          | AC output frequency                 |                                                                                                    | 0.01Hz  |
| 24      | Output DCV          | Output DC Volt                      |                                                                                                    | 0.1V    |
| 25      | InvTemp             | Inv Temperature                     |                                                                                                    | 0.1C    |
| 26      | DcDc Temp           | DC-DC Temperature                   |                                                                                                    | 0.1C    |
| 27      | LoadPercent         | Load Percent                        | 0~1000                                                                                             | 0.1%    |
| 28      | Bat_s_Volt          | Battery-port volt (DSP)             |                                                                                                    | 0.01V   |
| 29      | Bat_Volt_DSP        | Battery-bus volt (DSP)              |                                                                                                    | 0.01V   |
| 30      | Time total H        | Work time total (high)              |                                                                                                    | 0.5S    |
| 31      | Time total L        | Work time total (low)               |                                                                                                    | 0.5S    |
| 32      | Buck1_NTC           | Buck1 Temperature                   |                                                                                                    | 0.1C    |
| 33      | Buck2_NTC           | Buck2 Temperature                   |                                                                                                    | 0.1C    |
| 34      | OP_Curr             | Output Current                      |                                                                                                    | 0.1A    |
| 35      | Inv_Curr            | Inv Current                         |                                                                                                    | 0.1A    |
| 36      | AC_InWatt H         | AC input watt (high)                |                                                                                                    | 0.1W    |
| 37      | AC_InWatt L         | AC input watt (low)                 |                                                                                                    | 0.1W    |
| 38      | AC_InVA H           | AC input apparent power (high)      |                                                                                                    | 0.1VA   |
| 39      | AC_InVA L           | AC input apparent power (low)       |                                                                                                    | 0.1VA   |
| 40      | Fault bit           | Fault bit                           | See Fault Code Table                                                                               |         |
| 41      | Warning bit         | Warning bit                         | See Warning Code Table                                                                             |         |
| 42      | fault value         | Fault value                         |                                                                                                    |         |
| 43      | warning value       | Warning value                       |                                                                                                    |         |
| 44      | DTC                 | Device Type Code                    | See DTC Table                                                                                      |         |
| 45      | Check Step          | Product check step                  | 1: PV1 charge power check; 2: PV2 charge power check; 3: AC charge Power check                     |         |
| 46      | Production Line Mode| Production Line Mode                | 0: Not at Production Line Mode; 1: Production Line Mode; 2: Production Line Clear Fault Mode       |         |
| 47      | ConstantPowerOKFlag | Constant Power OK Flag              | 0: Not OK; 1: OK                                                                                   |         |
| 48      | Epv1_today H        | PV Energy today (high)              |                                                                                                    |         |
| 49      | Epv1_today L        | PV Energy today (low)               |                                                                                                    | 0.1kWh  |
| 50      | Epv1_total H        | PV Energy total (high)              |                                                                                                    |         |
| 51      | Epv1_total L        | PV Energy total (low)               |                                                                                                    | 0.1kWh  |
| 52      | Epv2_today H        | PV Energy today (high)              |                                                                                                    |         |
| 53      | Epv2_today L        | PV Energy today (low)               |                                                                                                    | 0.1kWh  |
| 54      | Epv2_total H        | PV Energy total (high)              |                                                                                                    |         |
| 55      | Epv2_total L        | PV Energy total (low)               |                                                                                                    | 0.1kWh  |
| 56      | Eac_chrToday H      | AC charge Energy today (high)       |                                                                                                    |         |
| 57      | Eac_chrToday L      | AC charge Energy today (low)        |                                                                                                    | 0.1kWh  |
| 58      | Eac_chrTotal H      | AC charge Energy total (high)       |                                                                                                    |         |
| 59      | Eac_chrTotal L      | AC charge Energy total (low)        |                                                                                                    | 0.1kWh  |
| 60      | Ebat_dischrToday H  | Bat discharge Energy today (high)   |                                                                                                    |         |
| 61      | Ebat_dischrToday L  | Bat discharge Energy today (low)    |                                                                                                    | 0.1kWh  |
| 62      | Ebat_dischrTotal H  | Bat discharge Energy total (high)   |                                                                                                    |         |
| 63      | Ebat_dischrTotal L  | Bat discharge Energy total (low)    |                                                                                                    | 0.1kWh  |
| 64      | Eac_dischrToday H   | AC discharge Energy today (high)    |                                                                                                    |         |
| 65      | Eac_dischrToday L   | AC discharge Energy today (low)     |                                                                                                    | 0.1kWh  |
| 66      | Eac_dischrTotal H   | AC discharge Energy total (high)    |                                                                                                    |         |
| 67      | Eac_dischrTotal L   | AC discharge Energy total (low)     |                                                                                                    | 0.1kWh  |
| 68      | ACChrCurr           | AC Charge Battery Current           |                                                                                                    | 0.1A    |
| 69      | AC_DisChrWatt H     | AC discharge watt (high)            |                                                                                                    | 0.1W    |
| 70      | AC_DisChrWatt L     | AC discharge watt (low)             |                                                                                                    | 0.1W    |
| 71      | AC_DisChrVA H       | AC discharge apparent power (high)  |                                                                                                    | 0.1VA   |
| 72      | AC_DisChrVA L       | AC discharge apparent power (low)   |                                                                                                    | 0.1VA   |
| 73      | Bat_DisChrWatt H    | Bat discharge watt (high)           |                                                                                                    | 0.1W    |
| 74      | Bat_DisChrWatt L    | Bat discharge watt (low)            |                                                                                                    | 0.1W    |
| 75      | Bat_DisChrVA H      | Bat discharge apparent power (high) |                                                                                                    | 0.1VA   |
| 76      | Bat_DisChrVA L      | Bat discharge apparent power (low)  |                                                                                                    | 0.1VA   |
| 77      | Bat_Watt H          | Bat watt (high)                     | (signed int 32) Positive: Battery Discharge Power; Negative: Battery Charge Power                  | 0.1W    |
| 78      | Bat_Watt L          | Bat watt (low)                      |                                                                                                    | 0.1W    |
| 79      | Reserved            | Not Used                            |                                                                                                    |         |
| 80      | BatOverCharge       | Battery Over Charge Flag            | 0: Battery not over charge; 1: Battery over charge                                                 |         |
| 81      | MpptFanSpeed        | Fan speed of MPPT Charger           | 0~100                                                                                              | 1%      |
| 82      | InvFanSpeed         | Fan speed of Inverter               | 0~100                                                                                              | 1%      |

---

### BMS Information Registers (90-145)

| Reg No. | Variable Name        | Description                           |
|---------|---------------------|---------------------------------------|
| 90      | BMS_Status          | Status from BMS                       |
| 91      | BMS_Error           | Error information from BMS            |
| 92      | BMS_WarnInfo        | Warning info from BMS                 |
| 93      | BMS_SOC             | SOC from BMS                          |
| 94      | BMS_BatteryVolt     | Battery voltage from BMS              |
| 95      | BMS_BatteryCurr     | Battery current from BMS              |
| 96      | BMS_BatteryTemp     | Battery temperature from BMS          |
| 97      | BMS_MaxCurr         | Max. charge/discharge current from BMS|
| 98      | BMS_ConstantVolt    | CV voltage from BMS                   |
| 99      | BMS_BMSInfo         | BMS Information from BMS              |
| 100     | BMS_PackInfo        | Pack Information from BMS             |
| 101     | BMS_UsingCap        | Using Cap from BMS                    |
| 102-117 | BMS_Cell1-16_Volt   | Cell 1-16 Voltage from BMS            |
| 118-145 | BMS2_*              | BMS2 information (same structure)     |

---

### Solar Charger Information Registers (180-224)

| Reg No. | Variable Name           | Description                          | Unit    |
|---------|------------------------|--------------------------------------|---------|
| 180     | Solar1_Status          | Solar Charger1 Status                |         |
| 181     | Solar1_FaultCode       | Solar Charger1 FaultCode             |         |
| 182     | Solar1_WarningCode     | Solar Charger1 WarningCode           |         |
| 183     | Solar1_BatVolt         | Solar Charger1 battery voltage       | 0.01V   |
| 184     | Solar1_PV1Volt         | Solar Charger1 PV1 voltage           | 0.1V    |
| 185     | Solar1_PV2Volt         | Solar Charger1 PV2 voltage           | 0.1V    |
| 186     | Solar1_Buck1Curr       | Solar Charger1 Buck1 current         | 0.1A    |
| 187     | Solar1_Buck2Curr       | Solar Charger1 Buck2 current         | 0.1A    |
| 188-189 | Solar1_PV1ChrPower H/L | Solar Charger1 PV1 charge Power      | 0.1W    |
| 190-191 | Solar1_PV2ChrPower H/L | Solar Charger1 PV2 charge Power      | 0.1W    |
| 192     | Solar1_HS1Temp         | Solar Charger1 Buck1 Temperature     | 0.1C    |
| 193     | Solar1_HS2Temp         | Solar Charger1 Buck2 Temperature     | 0.1C    |
| 194     | Solar1_Epv1_today      | Solar Charger1 PV1 Energy today      | 0.1kWh  |
| 195     | Solar1_Epv2_today      | Solar Charger1 PV2 Energy today      | 0.1kWh  |
| 196-197 | Solar1_Epv1_total H/L  | Solar Charger1 PV1 Energy total      | 0.1kWh  |
| 198-199 | Solar1_Epv2_total H/L  | Solar Charger1 PV2 Energy total      | 0.1kWh  |
| 200-219 | Solar2_*               | Solar Charger2 information (same structure) |   |
| 220     | Solar_ConnectOKFlag    | Slave Solar Connect OK Flag          |         |
| 221     | Solar_BatVoltConsistFlag| Check Slave Solar Battery Voltage Consist OK Flag |  |
| 222     | Solar_TypeSwState      | Solar Charger Type Switch State      | 0: Master; 1: Slave |
| 223     | Solar_ModeSwState      | Solar Charger Mode Switch State      | 0: Parallel; 1: Single |
| 224     | Solar_AddrSwState      | Solar Charger Addr Switch State      | 2~3     |

---

### Additional BMS Registers (360-381)

| Reg No. | Variable Name              | Description                    |
|---------|---------------------------|--------------------------------|
| 360     | BMS_GaugeRM               | Gauge RM from BMS              |
| 361     | BMS_GaugeFCC              | Gauge FCC from BMS             |
| 362     | BMS_FW                    | BMS FW                         |
| 363     | BMS_DeltaVolt             | Delta V from BMS               |
| 364     | BMS_CycleCnt              | Cycle Count from BMS           |
| 365     | BMS_SOH                   | SOH from BMS                   |
| 366     | BMS_GaugeICCurr           | Gauge IC current from BMS      |
| 367     | BMS_MCUVersion            | MCU Software version from BMS  |
| 368     | BMS_GaugeVersion          | Gauge Version from BMS         |
| 369     | BMS_wGaugeFRVersion_L     | Gauge FR Version L16 from BMS  |
| 370     | BMS_wGaugeFRVersion_H     | Gauge FR Version H16 from BMS  |
| 371-381 | BMS2_*                    | BMS2 information (same structure) |

---

## Fault Codes

| Fault Code   | Description                        |
|--------------|-----------------------------------|
| 0x00000002   | CPU A to B Communication error     |
| 0x00000004   | Battery sample inconsistent        |
| 0x00000008   | BUCK over current                  |
| 0x00000010   | BMS communication fault            |
| 0x00000020   | Battery abnormal                   |
| 0x00000080   | Battery voltage high               |
| 0x00000100   | Over temperature                   |
| 0x00000200   | Over load                          |
| 0x00010000   | Battery reverse connection         |
| 0x00020000   | BUS soft start fail                |
| 0x00040000   | DC-DC abnormal                     |
| 0x00080000   | DC voltage high                    |
| 0x00100000   | CT detect failed                   |
| 0x00200000   | CPU B to A Communication error     |
| 0x00400000   | BUS voltage high                   |
| 0x01000000   | MOV break                          |
| 0x02000000   | Output short circuit               |
| 0x04000000   | Li-Battery over load               |
| 0x08000000   | Output voltage high                |

---

## Warning Codes

| Warning Code | Description                        |
|--------------|-----------------------------------|
| 0x0001       | Battery voltage low warning        |
| 0x0002       | Over temperature warning           |
| 0x0004       | Over load warning                  |
| 0x0008       | Fail to read EEPROM                |
| 0x0010       | Firmware version mismatch          |
| 0x0020       | Fail to write EEPROM               |
| 0x0040       | BMS warning                        |
| 0x0080       | Li-Battery over load warning       |
| 0x0100       | Li-Battery aging warning           |
| 0x0200       | Fan lock warning                   |

---

## Fault Type Values (LCD Display)

| Fault Type Value | Message on Inverter              |
|------------------|----------------------------------|
| 1~7, 11~24, 28~32| "Error: 99+x"                    |
| 8                | Bat Voltage High                 |
| 9                | Over Temperature                 |
| 10               | Over Load                        |
| 25               | MOV Break                        |
| 26               | Over Current                     |
| 27               | Li-Bat Over Load                 |

---

## Device Type Code (DTC)

| Code No. | Device Type     | Note                                              |
|----------|----------------|---------------------------------------------------|
| 001xx    | Inverter       | 1 tracker and 1phase Grid connect PV inverter TL  |
| 002xx    | Inverter       | 2 tracker and 1phase Grid connect PV inverter TL  |
| 003xx    | Inverter       | 1 tracker and 1phase Grid connect PV inverter HF  |
| 004xx    | Inverter       | 2 tracker and 1phase Grid connect PV inverter HF  |
| 005xx    | Inverter       | 1 tracker and 1phase Grid connect PV inverter LF  |
| 006xx    | Inverter       | 2 tracker and 1phase Grid connect PV inverter LF  |
| 007xx    | Inverter       | 1 tracker and 3phase Grid connect PV inverter TL  |
| 008xx    | Inverter       | 2 tracker and 3phase Grid connect PV inverter TL  |
| 009xx    | Inverter       | 1 tracker and 3phase Grid connect PV inverter LF  |
| 010xx    | Inverter       | 2 tracker and 3phase Grid connect PV inverter LF  |
| 10001    | Data logger    | RF-ShineVersion                                   |
| 10002    | Data logger    | Web-ShinePano                                     |
| 10003    | Data logger    | Web-ShineWebBox                                   |
| 10004    | Data logger    | WL-WIFI Module                                    |
| 11001    | Confluence box | Confluence box 1                                  |
| 031xx    | PV Storage     | Front 1 tracker PV Storage                        |
| 034xx    | OffGrid        | OffGrid SPF 3-5K                                  |

---

## 5. Set Address

Refer to the Inverter user manual. The default address is typically **1**.

### Setting Procedure:

1. Knock the PV inverter to let the LCD display show "COM Addr: xxx"
2. Double knock - if it displays "Move", double knock again until it displays an address number
3. Single knock to change the address
4. The address will be remembered when the LCD backlight turns off

---

## 6. Notice

1. It can drive **mostly 32 PV inverters** for one RS485 COM port
2. There are only read input and hold registers commands even in the newest version
3. App users could only care about the **input register**
4. App users could not care about the holding registers
5. Except the CEI0-21 and VDE-AR-N 4105 power management registers, you should refer to the manufacturer's suggestion when writing other registers

---

## Contact Information

**GROWATT NEW ENERGY CO., LTD**  
No. 12 Building, Xicheng Industrial Zone, Bao'an District, Shenzhen 518102, China

- **Tel:** 86 755 27471063
- **Email:** info@ginverter.com
- **Website:** www.ginverter.com
