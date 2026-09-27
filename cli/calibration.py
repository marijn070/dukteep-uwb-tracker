from datetime import datetime

import numpy as np


def main():
    bs_num = input("Which base station number are you calibrating? ")

    distances = [150, 200, 300, 500, 750, 1000, 1500, 2000, 2500]

    print(f"\nCalibrating base station {bs_num}")
    print("Place the tag at each distance and enter the reported value.")
    print()

    actual = []
    measured = []

    for dist in distances:
        while True:
            try:
                reported = float(input(f"Place tag at {dist}mm - enter reported distance (mm): "))
                actual.append(float(dist))
                measured.append(reported)
                break
            except ValueError:
                print("  Please enter a number.")

    a, b = np.polyfit(measured, actual, 1)
    r2 = np.corrcoef(measured, actual)[0, 1] ** 2

    outfile = f"base_station_{bs_num}_calibration.txt"
    with open(outfile, "w") as f:
        f.write(f"Base Station {bs_num} Calibration\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
        f.write(f"{'Actual (mm)':<15} {'Measured (mm)':<15} {'Error (mm)':<15}\n")
        f.write("-" * 45 + "\n")
        for act, meas in zip(actual, measured):
            corrected = a * meas + b
            error = corrected - act
            f.write(f"{act:<15.0f} {meas:<15.0f} {error:<+15.1f}\n")
        f.write("\n")
        f.write("Trendline parameters:\n")
        f.write(f"  slope  a = {a:.4f}\n")
        f.write(f"  intercept b  = {b:.2f}\n")
        f.write(f"  R²       = {r2:.4f}\n")
        f.write("\n")
        f.write("AT command (replace ... with your existing values):\n")
        f.write(f"  AT+SETDEV=...,{a:.4f},{b:.2f},...\n")

    print("\nResults:")
    print(f"  slope  a = {a:.4f}")
    print(f"  intercept b  = {b:.2f}")
    print(f"  R²       = {r2:.4f}")
    print("\nAT command:")
    print(f"  AT+SETDEV=...,{a:.4f},{b:.2f},...")
    print(f"\nSaved to: {outfile}")


if __name__ == "__main__":
    main()
