# Third-Party Notices

This project uses, depends on, or is designed to work with third-party software and assets.

## 1. KataGo Engine

- Project: `KataGo`
- Upstream: [https://github.com/lightvector/KataGo](https://github.com/lightvector/KataGo)
- Author: David J Wu (`lightvector`) and contributors
- Purpose in this project: Go AI engine backend

The GoAI project is not affiliated with or endorsed by the KataGo project.

The official KataGo repository states that, aside from certain bundled external libraries and noted exceptions, the remaining repository content is available under an MIT-style license. A copy of the upstream license text used for attribution in this repository is included below.

### KataGo upstream license notice

```text
Copyright 2025 David J Wu ("lightvector") and/or other authors of the content in this repository.
(See 'CONTRIBUTORS' file for a list of authors as well as other indirect contributors).

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

For full and current upstream license details, please consult the official KataGo repository directly.

## 2. KataGo Neural Network Weights

- Source: [https://katagotraining.org/networks/](https://katagotraining.org/networks/)
- License page: [https://katagotraining.org/network_license/](https://katagotraining.org/network_license/)
- Author: David J Wu (`lightvector`), unless otherwise stated upstream
- Purpose in this project: neural network model files used by KataGo

The `katagotraining.org` network license states that the neural network files and training weight files are available under a permissive license and requires the copyright notice and permission notice to be included in copies or substantial portions of the software.

### KataGo network license notice

```text
Copyright 2022 David J Wu ("lightvector").

Permission is hereby granted, free of charge, to any person obtaining a copy of the neural net files
or training weight files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## 3. Python And Build Tooling

This project also uses common Python and packaging tools, including but not limited to:

- FastAPI
- Uvicorn
- websockets
- PyInstaller
- Inno Setup

These components remain under their own respective licenses. Please consult their official project pages for the latest license terms.

## 4. NVIDIA / CUDA / cuDNN Note

If a packaged Windows release includes NVIDIA-related runtime files, those files are third-party components and remain under NVIDIA's applicable terms.

For the GitHub source repository, it is recommended to keep large NVIDIA runtime binaries, engine binaries, and model files out of Git whenever possible, and instead provide them through release assets or user-side download steps.
