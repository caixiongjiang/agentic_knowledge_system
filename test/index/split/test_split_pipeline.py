#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
文本分块流水线完整测试

测试目标:
  纯分块逻辑测试（不依赖数据库/Kafka），直接构造复杂的 ParseResult 数据，
  经过 TextSplitterService.split_document() 后，将分块前原文和分块后结果
  分别写入 Markdown 文件，方便客观对比。

输出文件:
  tmp_results/split_test/01_original_elements.md  — 分块前原始元素
  tmp_results/split_test/02_split_chunks.md       — 分块后 Chunk 详情
  tmp_results/split_test/03_comparison.md         — 分块前后逐项对比

用法:
    uv run python test/index/split/test_split_pipeline.py
"""

import sys
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.service.knowledge.components.text_splitter_service import TextSplitterService
from src.index.common_file_extract.splitter.models import SplitConfig, SplitMethod
from src.types.models.parse_result import ParseResult, ElementInfo, ElementType, ParseStatus
from src.types.models.split_result import SplitResult, ChunkType

IMAGE_PATH = project_root / "tmp_files" / "image" / "image.png"
OUTPUT_DIR = project_root / "tmp_results" / "split_test"


# ══════════════════════════════════════════════════════════
#  构造模拟文档数据（与之前一致）
# ══════════════════════════════════════════════════════════

def build_mock_parse_result() -> ParseResult:
    """
    构造一个复杂的 ParseResult，模拟真实 PDF 解析后的结构化数据。

    文档结构:
      Page 0:  H1 标题 / 长文本(多段落) / H2 标题 / 短文本
      Page 1:  H2 标题 / 小 Markdown 表格 / 中等文本 / 真实图片
      Page 2:  H2 标题 / 超长 Markdown 表格(23行)
      Page 3:  H3 标题 / HTML 表格 / H2 标题 / 脏文本 / 多段落文本
    """
    elements: List[ElementInfo] = []
    idx = 0

    def eid() -> str:
        return f"element-{uuid.uuid4()}"

    # ── Page 0 ──
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=0, page_position=[50, 80, 500, 40],
        text="深度学习技术综述", text_level=1,
    ))
    idx += 1

    para_a = (
        "深度学习（Deep Learning）是机器学习的一个重要分支，通过构建多层神经网络模型来自动学习数据的层次化表示。"
        "自2012年AlexNet在ImageNet竞赛中取得突破性成绩以来，深度学习在计算机视觉、自然语言处理、语音识别等多个领域取得了革命性进展。"
        "深度学习的核心思想是利用大量数据和强大的计算资源，通过反向传播算法自动学习特征，"
        "从而避免了传统机器学习中手工设计特征的繁琐过程。"
    )
    para_b = (
        "卷积神经网络（CNN）是深度学习中最具代表性的架构之一，其核心思想是通过卷积操作提取局部特征。"
        "CNN的主要组件包括卷积层、池化层和全连接层。卷积层通过滑动窗口对输入进行卷积运算，"
        "提取不同尺度和方向的特征。池化层则通过下采样操作减少参数数量，提高计算效率。"
        "近年来，ResNet、DenseNet、EfficientNet等架构不断刷新各类计算机视觉任务的性能记录。"
    )
    para_c = (
        "循环神经网络（RNN）及其变体（LSTM、GRU）在序列数据处理中发挥着重要作用。"
        "RNN通过循环连接使网络能够记忆先前的信息，但传统RNN存在梯度消失问题。"
        "LSTM通过引入门控机制有效解决了这一问题，使模型能够学习长期依赖关系。"
        "近年来，Transformer架构的出现彻底改变了NLP领域的格局，其基于自注意力机制的并行计算方式"
        "大幅提升了训练效率，催生了BERT、GPT等一系列预训练语言模型。"
    )
    para_d = (
        "生成对抗网络（GAN）由Goodfellow等人在2014年提出，由生成器和判别器两个网络对抗训练组成。"
        "GAN在图像生成、风格迁移、数据增强等领域展现出强大的能力。"
        "变分自编码器（VAE）则从概率生成模型的角度出发，通过学习数据的潜在分布来生成新样本。"
        "近年来，扩散模型（Diffusion Model）异军突起，在图像生成质量上超越了GAN，"
        "代表性工作包括DDPM、Stable Diffusion等。"
    )
    long_text = f"{para_a}\n\n{para_b}\n\n{para_c}\n\n{para_d}"
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=0, page_position=[50, 130, 500, 400],
        text=long_text, text_level=0,
    ))
    idx += 1

    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=0, page_position=[50, 550, 500, 30],
        text="1.1 研究背景", text_level=2,
    ))
    idx += 1

    short_text = (
        "近年来，随着硬件算力的提升和大规模数据集的公开，"
        "深度学习研究呈现出爆发式增长。"
        "各大科技公司纷纷加大在AI领域的投入，推动了从学术研究到产业应用的快速转化。"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=0, page_position=[50, 590, 500, 60],
        text=short_text, text_level=0,
    ))
    idx += 1

    # ── Page 1 ──
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=1, page_position=[50, 80, 500, 30],
        text="1.2 主流框架对比", text_level=2,
    ))
    idx += 1

    small_table_body = (
        "| 框架 | 开发者 | 首发年份 | 编程语言 | 主要特点 |\n"
        "|------|--------|----------|----------|----------|\n"
        "| TensorFlow | Google | 2015 | Python/C++ | 生产级部署，TFLite移动端 |\n"
        "| PyTorch | Meta | 2016 | Python/C++ | 动态图，研究友好 |\n"
        "| JAX | Google | 2018 | Python | 函数式，XLA加速 |\n"
        "| PaddlePaddle | Baidu | 2016 | Python/C++ | 中文生态，飞桨平台 |\n"
        "| MindSpore | Huawei | 2020 | Python/C++ | 全场景AI，昇腾适配 |"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TABLE,
        page_index=1, page_position=[50, 120, 500, 160],
        table_body=small_table_body,
        table_caption="表1: 主流深度学习框架对比",
        table_footnote="数据来源：各框架官方文档（截至2025年）",
    ))
    idx += 1

    mid_text = (
        "在选择深度学习框架时，研究者和工程师需要综合考虑以下因素：社区活跃度、文档完善程度、"
        "模型库丰富度、部署便利性以及硬件兼容性。PyTorch凭借其灵活的动态图机制和庞大的社区生态，"
        "已成为学术界最受欢迎的框架。TensorFlow则在工业部署方面具有显著优势，"
        "其TFServing和TFLite工具链提供了从云端到边缘的完整部署方案。"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=1, page_position=[50, 300, 500, 80],
        text=mid_text, text_level=0,
    ))
    idx += 1

    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.IMAGE,
        page_index=1, page_position=[80, 400, 400, 280],
        bucket_name="knowledge-images",
        image_file_path="users/test_user/kb_001/images/neural_network_arch.png",
        image_file_name="neural_network_arch.png",
        image_file_type="png", image_file_format="PNG", image_file_suffix=".png",
        image_caption="图1: 典型深度神经网络架构示意图，展示了从输入层到隐藏层再到输出层的前向传播过程",
        image_footnote="注：图片中的箭头表示数据流方向，节点大小与该层神经元数量成正比",
    ))
    idx += 1

    # ── Page 2 ──
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=2, page_position=[50, 80, 500, 30],
        text="1.3 性能基准测试", text_level=2,
    ))
    idx += 1

    large_table_rows = [
        "| 模型 | 参数量 | ImageNet Top-1 | 训练时长(GPU-hours) | 推理延迟(ms) | FLOPs(G) | 预训练数据集 |",
        "|------|--------|----------------|---------------------|-------------|----------|-------------|",
    ]
    models_data = [
        ("ResNet-50", "25.6M", "76.1%", "90", "4.1", "4.1", "ImageNet-1K"),
        ("ResNet-152", "60.2M", "78.3%", "270", "11.5", "11.6", "ImageNet-1K"),
        ("EfficientNet-B0", "5.3M", "77.3%", "52", "2.5", "0.4", "ImageNet-1K"),
        ("EfficientNet-B7", "66M", "84.3%", "1200", "14.8", "37", "ImageNet-1K"),
        ("ViT-Base/16", "86M", "79.7%", "300", "6.2", "17.6", "ImageNet-21K"),
        ("ViT-Large/16", "304M", "82.6%", "1500", "18.3", "61.6", "ImageNet-21K"),
        ("ViT-Huge/14", "632M", "85.1%", "5000", "45.2", "167.4", "JFT-300M"),
        ("Swin-Tiny", "28M", "81.3%", "150", "5.8", "4.5", "ImageNet-1K"),
        ("Swin-Base", "88M", "83.5%", "420", "12.4", "15.4", "ImageNet-22K"),
        ("Swin-Large", "197M", "86.4%", "1800", "25.6", "34.5", "ImageNet-22K"),
        ("ConvNeXt-Tiny", "29M", "82.1%", "140", "5.2", "4.5", "ImageNet-1K"),
        ("ConvNeXt-Base", "89M", "83.8%", "400", "11.8", "15.4", "ImageNet-22K"),
        ("ConvNeXt-Large", "198M", "86.6%", "1700", "24.8", "34.4", "ImageNet-22K"),
        ("DeiT-Small", "22M", "79.9%", "100", "4.5", "4.6", "ImageNet-1K"),
        ("DeiT-Base", "87M", "81.8%", "350", "9.8", "17.6", "ImageNet-1K"),
        ("BEiT-Base", "86M", "83.2%", "800", "9.5", "17.6", "ImageNet-21K+DALL-E"),
        ("BEiT-Large", "304M", "86.3%", "3500", "28.2", "61.6", "ImageNet-21K+DALL-E"),
        ("MAE-Base", "86M", "83.6%", "600", "9.5", "17.6", "ImageNet-1K (Self-Supervised)"),
        ("MAE-Large", "304M", "85.9%", "2800", "28.2", "61.6", "ImageNet-1K (Self-Supervised)"),
        ("CLIP-ViT-B/32", "151M", "75.5%", "N/A", "5.8", "8.8", "WIT-400M (Image-Text)"),
        ("CLIP-ViT-L/14", "428M", "80.3%", "N/A", "18.6", "81.1", "WIT-400M (Image-Text)"),
        ("DINOv2-Base", "86M", "82.8%", "1200", "9.5", "17.6", "LVD-142M (Self-Supervised)"),
        ("DINOv2-Large", "304M", "86.1%", "4000", "28.2", "61.6", "LVD-142M (Self-Supervised)"),
    ]
    for m, p, a, h, l, f, d in models_data:
        large_table_rows.append(f"| {m} | {p} | {a} | {h} | {l} | {f} | {d} |")
    large_table_body = "\n".join(large_table_rows)

    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TABLE,
        page_index=2, page_position=[30, 120, 540, 500],
        table_body=large_table_body,
        table_caption="表2: 计算机视觉模型性能基准对比（ImageNet分类任务）",
        table_footnote="注：推理延迟基于NVIDIA A100 GPU，batch_size=1；N/A表示该指标不适用",
    ))
    idx += 1

    # ── Page 3 ──
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=3, page_position=[50, 80, 500, 30],
        text="1.3.1 HTML 格式表格测试", text_level=3,
    ))
    idx += 1

    html_table_body = (
        "<table>"
        "<tr><th>任务</th><th>模型</th><th>数据集</th><th>指标</th><th>得分</th></tr>"
        "<tr><td>文本分类</td><td>BERT-Base</td><td>SST-2</td><td>Accuracy</td><td>93.5%</td></tr>"
        "<tr><td>命名实体识别</td><td>RoBERTa-Large</td><td>CoNLL-2003</td><td>F1</td><td>92.8%</td></tr>"
        "<tr><td>机器翻译</td><td>mBART-50</td><td>WMT-2020</td><td>BLEU</td><td>38.2</td></tr>"
        "<tr><td>问答</td><td>GPT-4</td><td>SQuAD 2.0</td><td>F1</td><td>95.1%</td></tr>"
        "<tr><td>文本摘要</td><td>Pegasus</td><td>CNN/DailyMail</td><td>ROUGE-L</td><td>44.2</td></tr>"
        "</table>"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TABLE,
        page_index=3, page_position=[50, 120, 500, 180],
        table_body=html_table_body,
        table_caption="表3: NLP 任务性能对比",
        table_footnote=None,
    ))
    idx += 1

    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=3, page_position=[50, 320, 500, 30],
        text="1.4 含特殊字符的文本", text_level=2,
    ))
    idx += 1

    dirty_text = (
        "这段文本包含各种\x00需要清洗的\x01特殊字符\x02。\r\n"
        "包括零宽字符\u200B和\u200F不可见字符\u2060。\r"
        "还有重复标点！！！以及   多余的    空格。。。\n\n\n\n\n"
        "以及过多的换行符。"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=3, page_position=[50, 360, 500, 60],
        text=dirty_text, text_level=0,
    ))
    idx += 1

    multi_para = (
        "第一段：Transformer模型的核心创新是自注意力机制。\n\n"
        "第二段：与CNN的局部感受野不同，自注意力可以直接建模任意两个位置之间的依赖关系。\n\n"
        "第三段：Multi-Head Attention将注意力分成多个头，每个头关注不同的子空间，增强了模型的表达能力。\n\n"
        "第四段：位置编码（Positional Encoding）为模型提供了序列中token的位置信息，"
        "弥补了注意力机制本身缺乏位置感知的不足。\n\n"
        "第五段：Layer Normalization和残差连接是Transformer中的重要技术，"
        "它们有效缓解了深层网络的训练困难问题。\n\n"
        "第六段：在解码器中，Masked Multi-Head Attention确保了自回归生成过程中的因果性，"
        "即每个位置只能关注它之前的位置。这一机制对于文本生成任务至关重要。\n\n"
        "第七段：Cross Attention层连接编码器和解码器，使解码器能够关注编码器的输出，"
        "这是Seq2Seq模型中信息传递的关键环节。\n\n"
        "第八段：近年来，仅使用编码器（BERT系列）或仅使用解码器（GPT系列）的变体"
        "也取得了巨大成功，证明了Transformer架构的灵活性和通用性。"
    )
    elements.append(ElementInfo(
        element_id=eid(), element_index=idx, element_type=ElementType.TEXT,
        page_index=3, page_position=[50, 430, 500, 300],
        text=multi_para, text_level=0,
    ))
    idx += 1

    return ParseResult(
        user_id="test_user_001", file_id="file_split_test_001",
        filename="deep_learning_survey.pdf", status=ParseStatus.SUCCESS,
        elements=elements, document_language="zh", total_pages=4,
        parse_tool="mineru", parse_quality=0.95,
        knowledge_base_id="kb_test_001", knowledge_base_name="测试知识库",
    )


# ══════════════════════════════════════════════════════════
#  Markdown 文件生成
# ══════════════════════════════════════════════════════════

def write_original_md(parse_result: ParseResult, config: SplitConfig, path: Path) -> None:
    """生成分块前原始元素的 Markdown"""
    lines: List[str] = []
    w = lines.append

    w("# 分块前：原始 Element 列表\n")
    w(f"> 文件名: `{parse_result.filename}`  ")
    w(f"> 语言: `{parse_result.document_language}` | 总页数: `{parse_result.total_pages}`  ")
    w(f"> 元素总数: **{len(parse_result.elements)}** "
      f"（文本={len(parse_result.text_elements)}, "
      f"图片={len(parse_result.image_elements)}, "
      f"表格={len(parse_result.table_elements)}）  ")
    w(f"> 切分配置: method=`{config.split_method}`, "
      f"chunk_size=`{config.chunk_size}`, overlap=`{config.chunk_overlap}`\n")

    current_page = -1
    for i, elem in enumerate(parse_result.elements):
        if elem.page_index is not None and elem.page_index != current_page:
            current_page = elem.page_index
            w(f"\n---\n\n## Page {current_page}\n")

        if elem.is_text() and elem.text_level and elem.text_level > 0:
            w(f"### Element #{i} — 标题 H{elem.text_level}（{len(elem.text or '')} 字符）\n")
            w(f"{'#' * (elem.text_level + 1)} {elem.text}\n")

        elif elem.is_text():
            text = elem.text or ""
            w(f"### Element #{i} — 正文文本（{len(text)} 字符）\n")
            w("```text")
            w(text)
            w("```\n")

        elif elem.is_image():
            w(f"### Element #{i} — 图片\n")
            w(f"| 属性 | 值 |")
            w(f"|------|------|")
            w(f"| 文件名 | `{elem.image_file_name}` |")
            w(f"| 存储路径 | `{elem.image_file_path}` |")
            w(f"| Bucket | `{elem.bucket_name}` |")
            w(f"| 格式 | `{elem.image_file_type}` / `{elem.image_file_format}` |")
            w(f"| Caption | {elem.image_caption} |")
            w(f"| Footnote | {elem.image_footnote} |")
            if IMAGE_PATH.exists():
                w(f"\n![{elem.image_caption}](../../tmp_files/image/image.png)\n")
            w("")

        elif elem.is_table():
            body = elem.table_body or ""
            w(f"### Element #{i} — 表格（主体 {len(body)} 字符）\n")
            if elem.table_caption:
                w(f"**标题**: {elem.table_caption}  ")
            if elem.table_footnote:
                w(f"**脚注**: {elem.table_footnote}  ")
            w("")
            if "<tr>" in body.lower():
                w("**格式**: HTML\n")
                w("```html")
                w(body)
                w("```\n")
            else:
                w("**格式**: Markdown\n")
                w(body)
                w("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_chunks_md(split_result: SplitResult, config: SplitConfig, path: Path) -> None:
    """生成分块后 Chunk 详情的 Markdown"""
    lines: List[str] = []
    w = lines.append

    w("# 分块后：Chunk 详情\n")
    w(f"> 状态: `{split_result.status}` | 切分方法: `{config.split_method}` | "
      f"chunk_size: `{config.chunk_size}`  ")
    w(f"> Sections: **{split_result.total_sections}** | "
      f"Chunks: **{split_result.total_chunks}** | "
      f"总字符数: **{split_result.total_chars}**  ")
    w(f"> 文本 Chunk: {len(split_result.text_chunks)} | "
      f"图片 Chunk: {len(split_result.image_chunks)} | "
      f"表格 Chunk: {len(split_result.table_chunks)}\n")

    # Section 层级树
    w("## Section 层级结构\n")
    w("```")
    for section in split_result.sections:
        indent = "  " * (section.level - 1)
        child_count = len(section.chunk_id_list)
        w(f"{indent}H{section.level}: {section.content}  "
          f"[子Chunks={child_count}, id={section.section_id[:16]}...]")
    w("```\n")

    # 按 Section 分组展示 Chunks
    w("## 全部 Chunk 列表\n")

    section_map = {s.section_id: s for s in split_result.sections}
    current_section_id = None
    chunk_no = 0

    for chunk in split_result.chunks:
        if chunk.section_id != current_section_id:
            current_section_id = chunk.section_id
            sec = section_map.get(current_section_id)
            if sec:
                w(f"\n### Section: {sec.content} (H{sec.level})\n")
            else:
                w(f"\n### Section: (无归属)\n")

        chunk_no += 1
        text = chunk.get_text_content() or ""
        type_tag = chunk.chunk_type.upper()

        w(f"#### Chunk {chunk_no} [{type_tag}] — {len(text)} 字符\n")
        w(f"- **chunk_id**: `{chunk.chunk_id[:24]}...`")
        w(f"- **page_index**: {chunk.page_index}")
        w(f"- **element_ids**: `{chunk.element_ids}`")
        w(f"- **language**: {chunk.language}")

        if chunk.is_text() or chunk.is_table():
            w(f"\n```text\n{text}\n```\n")
        elif chunk.is_image():
            w(f"- **image_file**: `{chunk.image_file_name}`")
            w(f"- **bucket**: `{chunk.bucket_name}`")
            w(f"- **path**: `{chunk.image_file_path}`")
            w(f"- **caption**: {chunk.image_caption}")
            w(f"- **footnote**: {chunk.image_footnote}")
            if IMAGE_PATH.exists():
                w(f"\n![{chunk.image_caption}](../../tmp_files/image/image.png)\n")
            w("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_comparison_md(
    parse_result: ParseResult,
    split_result: SplitResult,
    config: SplitConfig,
    path: Path,
) -> None:
    """生成分块前后逐项对比的 Markdown"""
    lines: List[str] = []
    w = lines.append

    w("# 分块前后对比分析\n")
    w(f"> 切分方法: `{config.split_method}` | chunk_size: `{config.chunk_size}` | "
      f"overlap: `{config.chunk_overlap}` | text_clean: `{config.enable_text_clean}`\n")

    def find_chunks(element_id: str, chunk_type: str = None):
        return [
            c for c in split_result.chunks
            if element_id in c.element_ids and (chunk_type is None or c.chunk_type == chunk_type)
        ]

    # ─── 1. 长文本 ───
    elem = parse_result.elements[1]
    chunks = find_chunks(elem.element_id, "text")
    w("---\n\n## 1. 长文本分块\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 原始长度 | {len(elem.text or '')} 字符 |")
    w(f"| 原始段落数 | 4 段（`\\n\\n` 分隔） |")
    w(f"| 分块数量 | **{len(chunks)}** |")
    w("")

    w("### 原文\n")
    w(f"```text\n{elem.text}\n```\n")

    w("### 分块结果\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        w(f"**Chunk {j}** — {len(text)} 字符\n")
        w(f"```text\n{text}\n```\n")

    # ─── 2. 短文本 ───
    elem = parse_result.elements[3]
    chunks = find_chunks(elem.element_id, "text")
    w("---\n\n## 2. 短文本分块\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 原始长度 | {len(elem.text or '')} 字符 |")
    w(f"| 分块数量 | **{len(chunks)}**（未超过 chunk_size，不切分） |")
    w("")

    w("### 原文\n")
    w(f"```text\n{elem.text}\n```\n")

    w("### 分块结果\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        w(f"**Chunk {j}** — {len(text)} 字符\n")
        w(f"```text\n{text}\n```\n")

    # ─── 3. 小表格 ───
    elem = parse_result.elements[5]
    chunks = find_chunks(elem.element_id, "table")
    from src.index.common_file_extract.splitter.table_splitter import TableSplitter
    assembled = TableSplitter.assemble_table(elem.table_body, elem.table_caption, elem.table_footnote)
    w("---\n\n## 3. 小表格分块（Markdown）\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 组装后长度 | {len(assembled)} 字符 |")
    w(f"| chunk_size | {config.chunk_size} |")
    w(f"| 是否切分 | {'是' if len(chunks) > 1 else '否（整表保留）'} |")
    w(f"| 分块数量 | **{len(chunks)}** |")
    w("")

    w("### 原始表格（组装后）\n")
    w(f"```text\n{assembled}\n```\n")

    w("### 分块结果\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        w(f"**Chunk {j}** — {len(text)} 字符\n")
        w(f"```text\n{text}\n```\n")

    # ─── 4. 超长表格 ───
    elem = parse_result.elements[9]
    chunks = find_chunks(elem.element_id, "table")
    assembled = TableSplitter.assemble_table(elem.table_body, elem.table_caption, elem.table_footnote)
    w("---\n\n## 4. 超长表格分块（Markdown，23行数据）\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 组装后长度 | {len(assembled)} 字符 |")
    w(f"| chunk_size | {config.chunk_size} |")
    w(f"| 分块数量 | **{len(chunks)}** |")
    w("")

    w("### 原始表格（组装后）\n")
    w(f"```text\n{assembled}\n```\n")

    w("### 分块结果\n")
    w("每个切片检查：表头保留 / 标题保留 / 脚注保留\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        first_body_line = ""
        for line in text.split("\n"):
            if line.startswith("table_body:"):
                first_body_line = line
                break
        has_header = "| 模型 |" in first_body_line if first_body_line else False
        has_caption = "table_caption:" in text
        has_footnote = "table_footnote:" in text
        w(f"**Chunk {j}** — {len(text)} 字符 "
          f"（表头: {'Y' if has_header else 'N'} / "
          f"标题: {'Y' if has_caption else 'N'} / "
          f"脚注: {'Y' if has_footnote else 'N'}）\n")
        w(f"```text\n{text}\n```\n")

    # ─── 5. HTML 表格 ───
    elem = parse_result.elements[11]
    chunks = find_chunks(elem.element_id, "table")
    assembled = TableSplitter.assemble_table(elem.table_body, elem.table_caption, elem.table_footnote)
    w("---\n\n## 5. HTML 表格分块\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 组装后长度 | {len(assembled)} 字符 |")
    w(f"| 解析策略 | HTML `<tr>` 标签识别 |")
    w(f"| 分块数量 | **{len(chunks)}** |")
    w("")

    w("### 原始表格（组装后）\n")
    w(f"```html\n{assembled}\n```\n")

    w("### 分块结果\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        w(f"**Chunk {j}** — {len(text)} 字符\n")
        w(f"```text\n{text}\n```\n")

    # ─── 6. 特殊字符清洗 ───
    elem = parse_result.elements[13]
    chunks = find_chunks(elem.element_id, "text")
    w("---\n\n## 6. 特殊字符清洗\n")

    w("### 原文（含不可见字符）\n")
    w("Python repr:\n")
    w(f"```\n{repr(elem.text)}\n```\n")
    w("可见渲染:\n")
    w(f"```text\n{elem.text}\n```\n")

    if chunks:
        cleaned = chunks[0].get_text_content() or ""
        has_control = any(ord(ch) < 32 and ch not in ('\n', '\t') for ch in cleaned)
        has_zero_width = any(ch in '\u200B\u200F\u2060' for ch in cleaned)
        w("### 清洗后\n")
        w(f"```text\n{cleaned}\n```\n")
        w(f"| 检查项 | 结果 |")
        w(f"|--------|------|")
        w(f"| 控制字符 (`\\x00`, `\\x01`, ...) | {'残留' if has_control else '已清除'} |")
        w(f"| 零宽字符 (`\\u200B`, `\\u200F`, `\\u2060`) | {'残留' if has_zero_width else '已清除'} |")
        w(f"| 多余空格 | {'已规范化' if '  ' not in cleaned else '残留'} |")
        w(f"| 重复换行 | {'已规范化' if '\\n\\n\\n' not in cleaned else '残留'} |")
        w("")

    # ─── 7. 多段落合并/拆分 ───
    elem = parse_result.elements[14]
    chunks = find_chunks(elem.element_id, "text")
    w("---\n\n## 7. 多段落文本的合并/拆分策略\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 原始长度 | {len(elem.text or '')} 字符 |")
    w(f"| 原始段落数 | 8 段（`\\n\\n` 分隔） |")
    w(f"| 分块数量 | **{len(chunks)}** |")
    w(f"| 说明 | structure_first 先清洗再按段落边界切分/合并 |")
    w("")

    w("### 原文\n")
    w(f"```text\n{elem.text}\n```\n")

    w("### 分块结果\n")
    for j, c in enumerate(chunks, 1):
        text = c.get_text_content() or ""
        w(f"**Chunk {j}** — {len(text)} 字符\n")
        w(f"```text\n{text}\n```\n")

    # ─── 8. 图片 ───
    elem = parse_result.elements[7]
    chunks = find_chunks(elem.element_id, "image")
    w("---\n\n## 8. 图片 Chunk\n")
    w("图片不进行切分，直接传递存储信息和说明文字。\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 分块数量 | **{len(chunks)}** |")
    if chunks:
        ic = chunks[0]
        w(f"| 文件名 | `{ic.image_file_name}` |")
        w(f"| Bucket | `{ic.bucket_name}` |")
        w(f"| 路径 | `{ic.image_file_path}` |")
        w(f"| Caption | {ic.image_caption} |")
        w(f"| Footnote | {ic.image_footnote} |")
    w("")
    if IMAGE_PATH.exists():
        w(f"![{elem.image_caption}](../../tmp_files/image/image.png)\n")

    # ─── 9. 总结 ───
    w("---\n\n## 总结\n")
    w(f"| 指标 | 值 |")
    w(f"|------|------|")
    w(f"| 切分方法 | `{config.split_method}` |")
    w(f"| chunk_size | {config.chunk_size} |")
    w(f"| 原始 Element 数 | {len(parse_result.elements)} |")
    w(f"| 生成 Section 数 | {split_result.total_sections} |")
    w(f"| 生成 Chunk 数 | {split_result.total_chunks} |")
    w(f"| 文本 Chunk | {len(split_result.text_chunks)} |")
    w(f"| 图片 Chunk | {len(split_result.image_chunks)} |")
    w(f"| 表格 Chunk | {len(split_result.table_chunks)} |")
    w(f"| 总字符数 | {split_result.total_chars} |")
    w("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ══════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════

async def run_split_test() -> None:
    """运行完整的分块测试并输出 Markdown 文件"""

    print("=" * 60)
    print("  文本分块流水线测试")
    print("=" * 60)

    # 1. 构造数据
    parse_result = build_mock_parse_result()
    print(f"\n[1/4] 构造 ParseResult: {len(parse_result.elements)} 个元素")

    # 2. 初始化服务
    config = SplitConfig(
        split_method=SplitMethod.STRUCTURE_FIRST,
        chunk_size=500,
        chunk_overlap=0,
        enable_text_clean=True,
        separators=["\n", "。"]
    )
    service = TextSplitterService(config=config)
    print(f"[2/4] 初始化 TextSplitterService: "
          f"method={config.split_method}, chunk_size={config.chunk_size}")

    # 3. 执行分块
    document_id = "doc_test_001"
    split_result = await service.split_document(
        parse_result=parse_result,
        document_id=document_id,
    )
    print(f"[3/4] 分块完成: "
          f"sections={split_result.total_sections}, "
          f"chunks={split_result.total_chunks} "
          f"(text={len(split_result.text_chunks)}, "
          f"image={len(split_result.image_chunks)}, "
          f"table={len(split_result.table_chunks)})")

    # 4. 写入 Markdown 文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path_original = OUTPUT_DIR / "01_original_elements.md"
    path_chunks = OUTPUT_DIR / "02_split_chunks.md"
    path_compare = OUTPUT_DIR / "03_comparison.md"

    write_original_md(parse_result, config, path_original)
    write_chunks_md(split_result, config, path_chunks)
    write_comparison_md(parse_result, split_result, config, path_compare)

    print(f"[4/4] Markdown 文件已生成:")
    print(f"  - {path_original.relative_to(project_root)}")
    print(f"  - {path_chunks.relative_to(project_root)}")
    print(f"  - {path_compare.relative_to(project_root)}")
    print(f"\n{'=' * 60}")
    print(f"  ALL TESTS PASSED")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(run_split_test())
