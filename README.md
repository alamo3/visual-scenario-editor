# Visual Scenario Editor

A graphical tool for creating and editing driving scenarios for the CARLA Simulator.

[![Watch the video](https://i.imgur.com/JQU4g6Z.jpeg)](https://www.youtube.com/watch?v=jaBjUwShg9Q)

## Features

- Top-down map viewer with panning and zooming
- Vehicle and pedestrian spawning and management
- Waypoint creation and editing for scenario paths
- Traffic light configuration and triggers
- Weather control
- Undo/redo system
- Scenario saving/loading to JSON files
- Integration with CARLA ScenarioRunner
- Export to OpenSCENARIO (.xosc)

## Compatibility

VSE runs on **CARLA 0.9.15 and 0.9.16**. The `carla` Python module you install must match the
version of the server you run against.

For scenario playback (the **Play** button and `vse_play.py`), VSE works with any of three
ScenarioRunners: the [UT-ADL ScenarioRunner fork](https://github.com/UT-ADL/scenario_runner)
or the **stock** CARLA ScenarioRunner shipped for 0.9.15 or 0.9.16. Point `SCENARIO_RUNNER_ROOT`
at whichever you have installed — VSE adapts automatically, no configuration needed.

The install steps below use 0.9.15 as a concrete example. For 0.9.16, follow the same steps,
substituting the version in the download and the `pip install` — the UT Lexus asset is the same
for both versions.

## Installation

### Prerequisites

- Python 3.8+
- CARLA Simulator 0.9.15 or 0.9.16
- CARLA ScenarioRunner (UT-ADL fork or stock 0.9.15 / 0.9.16 — see Compatibility above)
- CARLA UT Lexus


#### 1. Create a directory into which to install carla and export it as `CARLA_ROOT`. Also update `PYTHONPATH` to make Carla agents importable in Python.
   ```
   mkdir ~/CARLA_0.9.15
   export CARLA_ROOT=$HOME/CARLA_0.9.15
   export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
   ```
   **Note:** Putting the above exports in `~/.bashrc` will reduce the hassle of exporting them every time you open a terminal.
   ```
   echo "export CARLA_ROOT=$HOME/CARLA_0.9.15" >> ~/.bashrc
   echo "export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla" >> ~/.bashrc
   ```
#### 2. Change into the directory and download [Carla 0.9.15](https://tiny.carla.org/carla-0-9-15-linux).
   ```
   cd $CARLA_ROOT
   wget https://tiny.carla.org/carla-0-9-15-linux -O CARLA_0.9.15.tar.gz
   ```
#### 3. Extract the file
   ```
   tar xzvf CARLA_0.9.15.tar.gz
   ```
#### 4. Delete the downloaded carla archive file.
   ```
   rm CARLA_0.9.15.tar.gz
   ```
#### 5. Go to the `Import` directory
   ```
   cd Import
   ```
#### 6. Download [utlexus.tar.gz](https://github.com/UT-ADL/carla_lexus/releases/download/v0.9.15/utlexus.tar.gz).
   ```
   wget https://github.com/UT-ADL/carla_lexus/releases/download/v0.9.15/utlexus.tar.gz
   ```
#### 7. Move to the parent directory
   ```
   cd ..
   ```
#### 8. Import the UT Lexus vehicle model.
   ```
   ./ImportAssets.sh
   ```
#### 9. Delete the `utlexus.tar.gz` file from the `Import` directory
  ```
  rm Import/utlexus.tar.gz
  ```
#### 10. Now, install the Carla Python module
  ```
  pip install carla==0.9.15
  ```
#### 11. Install CARLA dependencies:
  ```
  sudo apt install libomp5
  ```
#### 12. Clone [Scenario Runner](https://scenario-runner.readthedocs.io/en/latest/) to a directory of your choice
   ```
   git clone https://github.com/UT-ADL/scenario_runner.git
   ```
   **Note:** The stock CARLA ScenarioRunner (0.9.15 or 0.9.16) works too — clone or download
   whichever you have and set `SCENARIO_RUNNER_ROOT` to it in step 14. You do not need the fork.
#### 13. Install Scenario Runner requirements
   ```
   pip install -r scenario_runner/requirements.txt
   ```
#### 14. Set SCENARIO_RUNNER_ROOT environment variable
   ```
   echo "export SCENARIO_RUNNER_ROOT=<path_to>/scenario_runner" >> ~/.bashrc
   ```
#### 15. Clone VSE to a directory of your choice
   ```
   git clone https://github.com/UT-ADL/visual-scenario-editor.git
   ```
#### 16. Install VSE requirements
   ```
   pip install -r visual-scenario-editor/requirements.txt
   ```

### Windows (experimental)

Windows support is new and has only been exercised on Linux so far, so expect rough edges. These steps
mirror the Linux ones; use PowerShell. You can also run CARLA on another machine and connect to it from the
editor (**Connect to remote server**), which avoids launching a local server entirely.

1. Download the Windows package of CARLA 0.9.15 (or 0.9.16) from the
   [CARLA releases page](https://github.com/carla-simulator/carla/releases) and extract it, e.g. to `C:\CARLA_0.9.15`.
2. Set the environment variables (persisted for your user):
   ```powershell
   setx CARLA_ROOT "C:\CARLA_0.9.15"
   setx PYTHONPATH "%PYTHONPATH%;C:\CARLA_0.9.15\PythonAPI\carla"
   ```
   Open a new terminal afterwards so they take effect.
3. Install the matching Python client: `pip install carla==0.9.15`. If there is no wheel for your Python
   version, install the one shipped in `PythonAPI\carla\dist` instead.
4. Import the UT Lexus asset from the [carla_lexus release](https://github.com/UT-ADL/carla_lexus/releases)
   using CARLA's asset import mechanism for the packaged Windows build (the Linux `ImportAssets.sh` step has no
   verified Windows equivalent here yet).
5. Install ScenarioRunner as in steps 12-14 above, setting `SCENARIO_RUNNER_ROOT` with `setx`.
6. Clone VSE and install its requirements (`psutil` is installed automatically on Windows):
   ```powershell
   git clone https://github.com/UT-ADL/visual-scenario-editor.git
   pip install -r visual-scenario-editor\requirements.txt
   ```
7. Run `python vse.py`. VSE finds `%CARLA_ROOT%\CarlaUE4.exe` automatically, or pass `--carla-path`.

Settings are stored in `%LOCALAPPDATA%\vse` (`~/.cache/vse` on Linux). The CARLA server log goes to your temp
directory (`carla_server.log`) unless `VSE_CARLA_SERVER_LOG` is set.

## Usage

[![Watch the video](https://i.imgur.com/FaeVRuc.png)](https://www.youtube.com/watch?v=kjzwnp27A2o)

Launch the editor:
```bash
python vse.py
```

Run a saved scenario using VSE:
```bash
Open scenario.json file in VSE and press Play button
```

Run a saved scenario on existing Carla server:
```bash
python vse_play.py path/to/scenario.json
```

Run a saved scenario on an existing Carla server whose ego is driven by an external stack:
```bash
python vse_play.py scenario.json
```

For further instructions check the [tutorial](tutorial.md) — the beginner walkthrough.


### External ego driven by your own stack

If your own stack (e.g. a Docker container running ROS 2) spawns and drives the ego, VSE does not need an
agent file. It adopts the ego by `role_name` and runs the scenario around it. To hand the scenario's ego
waypoints (e.g. for destination setting) to your stack, set a route sink:

```bash
export VSE_EGO_ROUTE_SINK=http://localhost:8080/route   # or file:/path/route.json, or none
python vse.py
```

VSE sends JSON events: `{"event": "route", "scenario", "map", "waypoints": [{x,y,z,yaw}...], "destination": {...}}`
when playback starts and `{"event": "cancel"}` when it stops. The same option exists on the CLI as
`--ego-route-sink`. Without a sink nothing is sent. VSE itself has no ROS dependency: it never loads an agent
file, so your stack (ROS 1, ROS 2, anything) is entirely on your side of the sink.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
