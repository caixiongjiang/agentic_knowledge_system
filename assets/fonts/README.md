# AKS 中文字体与跨平台渲染配置

本模块用于彻底解决 Linux / Docker 环境下 LibreOffice 将 Word / PPT 转换为 PDF 时**中文变成方块（豆腐块 `□`）以及跨平台排版跑版（页数不一致、换行错位）**的问题。

项目采用 **“12个核心权威字体内置 (Dockerfile 直接打包, ~95MB) + Fontconfig 智能别名映射与开源兜底”** 的完备方案。

---

## 目录结构

```
agentic_knowledge_system/
└── assets/
    └── fonts/                   # [Git 追踪] 核心高频字体 (~95MB) + fonts.conf
        ├── FZXBSJW.TTF          # 1. 方正小标宋简体 (党政公文红头文件大标题法定标准)
        ├── FZFSJW.TTF           # 2. 方正仿宋简体 (党政公文正文法定标准)
        ├── Simsun.ttc           # 3. 宋体 / 新宋体
        ├── SimHei.ttf           # 4. 黑体
        ├── msyh.ttc             # 5. 微软雅黑
        ├── Kaiti.ttf            # 6. 楷体
        ├── Fangsong.ttf         # 7. 仿宋
        ├── Deng.ttf             # 8. 等线 (现代 Office 默认)
        ├── Calibri.ttf          # 9. Calibri (Office 默认西文)
        ├── times.ttf            # 10. Times New Roman (论文标准)
        ├── arial.ttf            # 11. Arial (标准无衬线)
        ├── Cambria.ttc          # 12. Cambria (Word 公式 & 论文)
        ├── fonts.conf           # Fontconfig 智能映射配置文件
        └── README.md
```

---

## 核心工作机制

1. **Docker 内置层（Dockerfile 自动构建）**：
   - 自动安装 Linux 开源基础字体：`fonts-noto-cjk`（思源黑体/宋体）、`fonts-wqy-zenhei`（文泉驿）、`fonts-liberation`。
   - 自动将 `assets/fonts/` 中的 **12 个核心权威字体** 复制到容器 `/usr/share/fonts/truetype/custom/`。
   - 自动将 `fonts.conf` 应用为 `/etc/fonts/local.conf` 并刷新缓存（`fc-cache -fv`）。

2. **Fontconfig 智能别名与回退机制（`fonts.conf`）**：
   - **macOS 专有字体等价映射**：Word 中引用的 `PingFang SC`（苹方）自动映射为 `Microsoft YaHei`（微软雅黑）或思源黑体；`Songti SC` 自动映射为 `SimSun`；`STHeiti` 自动映射为 `SimHei`。
   - **方正公文字体名称映射**：`方正小标宋简体` / `FZXiaoBiaoSong-B05S` 自动识别映射到 `FZXBSJW`，`方正仿宋简体` 自动识别映射到 `FZFSJW`。
   - **中英文名称对齐**：中文名称（如“宋体”、“楷体”）与 PostScript 英文标识无缝对齐。
   - **开源字体终极兜底**：遇到极其罕见的未安装字体时，自动 fallback 到思源黑体/思源宋体/文泉驿，**确保 100% 不出现方块乱码**。

---

## 内置 12 大核心字体清单 (共 ~95MB)

| 字体文件 | 字体名称 | 适用场景与权威性 |
|---|---|---|
| `FZXBSJW.TTF` | **方正小标宋简体** (FZXiaoBiaoSong) | **党政机关/企事业单位红头文件、公文大标题法定首选** (GB/T 9704-2012) |
| `FZFSJW.TTF` | **方正仿宋简体** (FZFangSong) | **党政机关国标公文正文最高标准规范字体** |
| `Simsun.ttc` | 宋体 / 新宋体 (SimSun) | **最高频**。毕业论文正文、学术期刊、合同协议、标准报告正文 |
| `SimHei.ttf` | 黑体 (SimHei) | **最高频**。各级大标题、表头、重点强调 |
| `msyh.ttc` | 微软雅黑 (Microsoft YaHei) | **最高频**。商务报告、现代企划案、PPT 演示文稿 |
| `Kaiti.ttf` | 楷体 (KaiTi) | 论文摘要、引言、通知、公文签发 |
| `Fangsong.ttf` | 仿宋 (FangSong) | 系统通用仿宋标准字体 |
| `Deng.ttf` | 等线 (DengXian) | **微软 Office 2016+ 默认中文正文字体** |
| `Calibri.ttf` | Calibri | 微软 Office 默认英文正文字体 |
| `times.ttf` | Times New Roman | 国际学术期刊 (IEEE/Nature 等)、学术论文英文标准 |
| `arial.ttf` | Arial | 国际标准无衬线英文字体 |
| `Cambria.ttc` | Cambria | Word 自带公式编辑器专用字体、论文标准衬线体 |
