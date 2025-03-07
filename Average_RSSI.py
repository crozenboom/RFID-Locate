import pandas as pd

# Load data from CSV
file_path = input("file path: ")
file_path = file_path.strip('"')
file_path = file_path.replace("\\", "/")
df = pd.read_csv(file_path, skiprows=2)

# Remove leading/trailing spaces from column names
df.columns = df.columns.str.strip()

# Display columns to check if RSSI is present
print("Columns found in CSV:", df.columns.tolist())

# Ensure 'Antenna' and 'RSSI' columns exist
if 'Antenna' not in df.columns or 'RSSI' not in df.columns:
    print("Error: Missing required columns in CSV file.")
else:
    # Group by 'Antenna' and calculate the mean of 'RSSI'
    avg_rssi = df.groupby('Antenna')['RSSI'].mean().reset_index()

    # Print average RSSI per antenna
    print("Average RSSI per antenna:")
    print(avg_rssi)
