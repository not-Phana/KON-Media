# Third-Party Licenses & Attributions

KON Media is developed as a clean-room, independently architected application. It utilizes well-maintained open-source libraries and engines in strict compliance with their respective licenses.

---

## 1. Upstream Media Engine

### yt-dlp
* **Source**: https://github.com/yt-dlp/yt-dlp
* **License**: The Unlicense (Public Domain Dedication)
* **Summary**: Permissive public domain dedication allowing any commercial or non-commercial use, modification, and distribution without restriction.

---

## 2. Python Backend Dependencies

### FastAPI
* **Source**: https://github.com/fastapi/fastapi
* **License**: MIT License
* **Copyright**: Copyright (c) 2018 Sebastián Ramírez

### Uvicorn
* **Source**: https://github.com/encode/uvicorn
* **License**: BSD 3-Clause License
* **Copyright**: Copyright (c) 2017-present, Encode OSS Ltd. All rights reserved.

### Pydantic
* **Source**: https://github.com/pydantic/pydantic
* **License**: MIT License
* **Copyright**: Copyright (c) 2017-present Samuel Colvin

### Pytest
* **Source**: https://github.com/pytest-dev/pytest
* **License**: MIT License
* **Copyright**: Copyright (c) 2004 Holger Krekel and others

---

## 3. Frontend Dependencies

### React & React DOM
* **Source**: https://github.com/facebook/react
* **License**: MIT License
* **Copyright**: Copyright (c) Meta Platforms, Inc. and affiliates.

### Vite
* **Source**: https://github.com/vitejs/vite
* **License**: MIT License
* **Copyright**: Copyright (c) 2019-present Evan You & Vite Contributors

### Tailwind CSS
* **Source**: https://github.com/tailwindlabs/tailwindcss
* **License**: MIT License
* **Copyright**: Copyright (c) Tailwind Labs, Inc.

### Lucide React
* **Source**: https://github.com/lucide-icons/lucide
* **License**: ISC License
* **Copyright**: Copyright (c) 2022 Lucide Contributors

---

## 4. Researched Projects (Clean-Room Assessment)

* **ReClip (`averygan/reclip`)**: Evaluated for single-file CLI patterns. Licensed under MIT. No source code was directly copied.
* **yt-dlp-web (`samrtulethtb/yt-dlp-web`)**: Evaluated for FastAPI concepts. Contained no license; strictly referenced as a conceptual model with zero code reuse.
* **MeTube (`alexta69/metube`)**: Evaluated for direct Python `yt_dlp` integration concepts and SSRF protection patterns. Licensed under AGPL-3.0. To prevent copyleft contamination, zero code from MeTube was copied or linked into KON Media. All security guards and managers are original clean-room implementations under the MIT License.
