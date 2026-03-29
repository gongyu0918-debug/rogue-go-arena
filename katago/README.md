# KataGo Directory Notes

This folder is used for third-party engine files and model files required at runtime.

For a clean GitHub source repository, it is recommended that the following files are **not** committed into Git:

- KataGo engine binaries
- CUDA / cuDNN runtime DLLs
- OpenCL / CPU binaries
- neural network weight files such as `model.bin.gz` or `model_b18.bin.gz`
- OpenCL tuning cache files

Typical files expected by this project include:

- `katago_cuda.exe`
- `katago_opencl.exe`
- `katago_cpu.exe`
- `config.cfg`
- `config_cpu.cfg`
- `model.bin.gz`
- `model_b18.bin.gz`
- optional stronger model files such as `model_large.bin.gz`

Official sources:

- KataGo engine releases: [https://github.com/lightvector/KataGo/releases](https://github.com/lightvector/KataGo/releases)
- KataGo networks: [https://katagotraining.org/networks/](https://katagotraining.org/networks/)

This project is built on top of KataGo, but it is not an official KataGo project.
