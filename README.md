# dukteep-uwb-tracker

Tracks a UWB tag mounted inside a football on a small indoor pitch, using a handful of fixed UWB
base stations. Distances come in over serial, trilateration turns them into a ball position, and a
live 2D top-down pitch view shows where the ball is.

## What's in here

- `cli/` - a command line tool for the UWB hardware itself: configuring the chips, reading raw
  distances, and running the distance calibration.
- `tracker/` - the tracking application: it reads the serial stream, trilaterates the ball position,
  and draws the live 2D top-down pitch view with score and goal/out-of-play events.

## Running it

The CLI:

```sh
cd cli
uv run uwb          # main CLI (device, filter, info, test, config, monitor)
uv run chipconfig   # chip configuration
uv run distances    # raw distance readout
uv run calibrate    # distance calibration
```

The tracker:

```sh
cd tracker
uv run uwb-tracker
```

Both need the physical UWB hardware connected on a serial port; the anchor geometry and the field
size live in `tracker/uwb.toml`.
