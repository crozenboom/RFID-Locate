# RFID Data Processing Scripts

## Overview
This repository contains three Python scripts designed for processing and analyzing RFID data:
- `average_RSSI.py`
- `Locate.py`
- `check_headers.py`

Each script serves a specific purpose in handling RFID-related data, from computing RSSI averages to determining tag locations.

## Scripts Description

### 1. `average_RSSI.py`
**Purpose:**
- Reads an RFID data CSV file containing power levels, distances, and RSSI values.
- Computes the average RSSI for each power level and outputs the results.

**Usage:**
```sh
python average_RSSI.py
```
- The script will prompt for a file path.
- It processes the CSV file and calculates the average RSSI.
- Outputs the cleaned and processed data.

### 2. `Locate.py`
**Purpose:**
- Uses CSV file with RSSI values from multiple antennas to estimate the location of an RFID tag.
- Applies distance estimation formulas to determine the position in 3D space.

**Usage:**
```sh
python Locate.py
```
- The script processes input RSSI values and calculates the approximate location of the RFID tag.
- Outputs estimated coordinates `(x, y, z)`.

### 3. `check_headers.py`
**Purpose:**
- Verifies that an input CSV file contains the required headers for processing.
- Ensures data integrity before further analysis.

**Usage:**
```sh
python check_headers.py
```
- The script will prompt for a file path.
- It checks if the required columns (e.g., Power, Distance, Avg RSSI) are present.
- Displays a success message if headers match or an error message if they are incorrect.

## Requirements
- Python 3.x
- Pandas (for CSV processing)
- NumPy (for calculations)

Install dependencies using:
```sh
pip install pandas numpy
```

## Notes
- Ensure that input CSV files are properly formatted before running the scripts.
- Modify file paths or input handling if necessary to match your directory structure.

## Author
Created by Caleb for RFID data analysis and location estimation.

---

