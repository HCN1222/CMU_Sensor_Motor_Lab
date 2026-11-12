# Team Setup: Development Environment

Every teammate follows these steps once to get the same development environment.

## 1. Install software (Windows)

| Software | Purpose | Notes |
|---|---|---|
| [Miniforge](https://github.com/conda-forge/miniforge) or Miniconda | Python + ROS 2 Humble + rqt | ROS 2 is provided as conda packages (RoboStack); **no separate ROS install is needed** |
| [Arduino IDE 2.x](https://www.arduino.cc/en/software) | Uploading firmware to the Uno | Bundles arduino-cli; on first launch let it install **Arduino AVR Boards** |
| Git | Version control | Needed to clone the repository and open PRs |
| VS Code (optional) | Editing | |

Linux (Ubuntu 22.04) can also use conda, or an apt install of ROS 2 Humble.

## 2. Clone the repository

Clone to a location **outside OneDrive sync with a short path**, for example `C:\lab\CMU_Sensor_Motor_Lab`. colcon generates many files, and OneDrive syncing slows things down or even locks files.

```bat
cd C:\lab
git clone https://github.com/HCN1222/CMU_Sensor_Motor_Lab.git
cd CMU_Sensor_Motor_Lab
```

## 3. Create the environment

Open **Anaconda Prompt / Miniforge Prompt** (or a PowerShell where `conda init powershell` has been run):

```bat
conda env create -f environment.yml
conda activate sensorMotorLab
```

- Creating the environment the first time downloads about 1–2 GB and takes from a few minutes to over ten minutes.
- Run `conda activate sensorMotorLab` first in every new terminal.
- Quick check: `ros2 --help` prints the ROS 2 command list.

## 4. Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [BRANCH_NAMING.md](BRANCH_NAMING.md) before your first branch. Work on a personal branch, open a PR to `main`, and get an approval from another teammate before merging.

## Common issues

| Symptom | Cause / fix |
|---|---|
| `conda activate` does nothing in PowerShell | Run `conda init powershell` once, then reopen the terminal |
| `ros2` command not found | `conda activate sensorMotorLab` was not run in this terminal |
