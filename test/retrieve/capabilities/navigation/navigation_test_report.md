# 结构化导航与上下文游走能力 — 测试报告

- **生成时间**: 2026-03-06 15:05:22
- **说明**: 所有文本内容均为完整输出，可与原始 PDF 逐项对比。image 类型 Chunk 会标注类型和图片存储路径。

---

## 测试数据概览

- **document_id**: `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`
- **test_section_id**: `section-0d1df367-e998-4cf3-b27b-103b4e8ecb6e`
- **test_chunk_id**: `chunk-03e812b7-f087-478f-903c-642002f8c97c`
- **test_element_id**: `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`
- **总 Section 数**: 34
- **总 Chunk 数**: 113

---

## 1. Skeleton — 文档骨架/目录树提取

- **文档标题**: (无)
- **总 Section 数**: 34
- **总 Chunk 数**: 112
- **耗时**: 185.9ms

### 文档目录树

- **[L1]** FastSegFormer: A knowledge distillation-based method for real-time semantic segmentation of surface defects in navel oranges   _(chunks: 1, id: `section-617f792b-ea49-4752-b002-7dca2cd9a39e`)_
- **[L1]** ARTICLEINFO   _(chunks: 0, id: `section-fe5386dd-d655-4ef7-8bb6-bc7410bae54a`)_
- **[L1]** ABSTRACT   _(chunks: 4, id: `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`)_
- **[L1]** 1.Introduction   _(chunks: 12, id: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`)_
- **[L1]** 2.Materials and methods   _(chunks: 0, id: `section-3281156a-4d3e-4f27-9db9-f27fd05a9233`)_
- **[L1]** 2.1.Image acquisition and dataset construction   _(chunks: 6, id: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`)_
- **[L1]** 2.2.UNet model   _(chunks: 1, id: `section-2db880b8-4571-423a-ac82-0c44a1909bc2`)_
- **[L1]** 2.3.FastSegFormer model   _(chunks: 8, id: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`)_
- **[L1]** 2.3.1.Backbone network   _(chunks: 3, id: `section-655c8782-ad75-4055-b653-ded79d73dca2`)_
- **[L1]** 2.3.2.Feature extraction   _(chunks: 3, id: `section-8f778125-8ee2-40ac-ad65-084d97732606`)_
- **[L1]** 2.3.3.Image reconstruction branch   _(chunks: 6, id: `section-6da38ecb-56a3-46ba-b139-c6473484a550`)_
- **[L1]** 2.4.Knowledge distillation   _(chunks: 1, id: `section-e2e0f765-01a7-46af-85b6-37ede7f8dbed`)_
- **[L1]** 2.4.1.Multi-resolution input distillation method   _(chunks: 3, id: `section-4987636c-b976-41d6-90d7-d4262b19a8d3`)_
- **[L1]** 2.5. Loss function   _(chunks: 6, id: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`)_
- **[L1]** 2.6. Training and test   _(chunks: 0, id: `section-0d1df367-e998-4cf3-b27b-103b4e8ecb6e`)_
- **[L1]** 2.6.1.Network structures   _(chunks: 2, id: `section-dce0f68c-2752-4bf0-b8c5-de19a263abae`)_
- **[L1]** 2.6.2. Training setup   _(chunks: 2, id: `section-bc4f66cc-d829-4c6a-959b-69e8b63d4b44`)_
- **[L1]** 2.6.3.Model evaluation metrics   _(chunks: 4, id: `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`)_
- **[L1]** 3. Results and analysis   _(chunks: 0, id: `section-bb3fcabe-5bdf-4dc1-935f-f8be8a1bbb7b`)_
- **[L1]** 3.1．Ablation studies   _(chunks: 12, id: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`)_
- **[L1]** 3.2.Performance comparison of FastSegFormer and other segmentation models   _(chunks: 5, id: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`)_
- **[L1]** 3.3.Segmentation results of diferent models on the test set   _(chunks: 1, id: `section-1f7ff486-5798-4a27-867d-e2e3f8ffbb55`)_
- **[L1]** 3.4.Defect detection system deployment   _(chunks: 1, id: `section-cbae53f4-03e8-4cd1-8bdb-c7f9732fe679`)_
- **[L1]** 3.4.1. Deployment setup   _(chunks: 3, id: `section-30c66884-4443-4260-9f2f-e27680b7f3b5`)_
- **[L1]** 3.4.2. Detection speed   _(chunks: 3, id: `section-95ba5683-8c9f-4209-9f58-df611b13b2b7`)_
- **[L1]** 4.Discussion   _(chunks: 0, id: `section-4a6cbbd5-77ae-4e49-a504-4c3922a0a82d`)_
- **[L1]** 4.1. Comparison with related work   _(chunks: 5, id: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`)_
- **[L1]** 4.2.Future research   _(chunks: 4, id: `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`)_
- **[L1]** 5.Conclusion   _(chunks: 3, id: `section-682d3ee7-4ea5-41f2-ba67-367372d63649`)_
- **[L1]** CRediT authorship contribution statement   _(chunks: 1, id: `section-e75b119c-edbc-401a-a947-7876b775ef42`)_
- **[L1]** Declaration of competing interest   _(chunks: 1, id: `section-e4a68ef4-1e13-4816-938f-a010ffa10296`)_
- **[L1]** Data availability   _(chunks: 1, id: `section-fecf5047-8c16-4f3b-9026-307bf14d887d`)_
- **[L1]** Acknowledgments   _(chunks: 1, id: `section-4f9fddec-e769-4684-867a-81dc7f7c4ae5`)_
- **[L1]** References   _(chunks: 9, id: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`)_

---

## 2. DrillDown — 跨粒度下钻

### 2.1 Document → Section（按阅读顺序）

- **返回数量**: 34
- **耗时**: 140.6ms

#### Section #1 — `section-617f792b-ea49-4752-b002-7dca2cd9a39e`

- **score**: 1.000
- **text_level**: 1

**Section 标题/内容**

```
FastSegFormer: A knowledge distillation-based method for real-time semantic segmentation of surface defects in navel oranges 
```

#### Section #2 — `section-fe5386dd-d655-4ef7-8bb6-bc7410bae54a`

- **score**: 0.971
- **text_level**: 1

**Section 标题/内容**

```
ARTICLEINFO 
```

#### Section #3 — `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`

- **score**: 0.941
- **text_level**: 1

**Section 标题/内容**

```
ABSTRACT 
```

#### Section #4 — `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`

- **score**: 0.912
- **text_level**: 1

**Section 标题/内容**

```
1.Introduction 
```

#### Section #5 — `section-3281156a-4d3e-4f27-9db9-f27fd05a9233`

- **score**: 0.882
- **text_level**: 1

**Section 标题/内容**

```
2.Materials and methods 
```

#### Section #6 — `section-dd8fcae1-b4df-4764-af5a-a0358307f200`

- **score**: 0.853
- **text_level**: 1

**Section 标题/内容**

```
2.1.Image acquisition and dataset construction 
```

#### Section #7 — `section-2db880b8-4571-423a-ac82-0c44a1909bc2`

- **score**: 0.824
- **text_level**: 1

**Section 标题/内容**

```
2.2.UNet model 
```

#### Section #8 — `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`

- **score**: 0.794
- **text_level**: 1

**Section 标题/内容**

```
2.3.FastSegFormer model 
```

#### Section #9 — `section-655c8782-ad75-4055-b653-ded79d73dca2`

- **score**: 0.765
- **text_level**: 1

**Section 标题/内容**

```
2.3.1.Backbone network 
```

#### Section #10 — `section-8f778125-8ee2-40ac-ad65-084d97732606`

- **score**: 0.735
- **text_level**: 1

**Section 标题/内容**

```
2.3.2.Feature extraction 
```

#### Section #11 — `section-6da38ecb-56a3-46ba-b139-c6473484a550`

- **score**: 0.706
- **text_level**: 1

**Section 标题/内容**

```
2.3.3.Image reconstruction branch 
```

#### Section #12 — `section-e2e0f765-01a7-46af-85b6-37ede7f8dbed`

- **score**: 0.676
- **text_level**: 1

**Section 标题/内容**

```
2.4.Knowledge distillation 
```

#### Section #13 — `section-4987636c-b976-41d6-90d7-d4262b19a8d3`

- **score**: 0.647
- **text_level**: 1

**Section 标题/内容**

```
2.4.1.Multi-resolution input distillation method 
```

#### Section #14 — `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`

- **score**: 0.618
- **text_level**: 1

**Section 标题/内容**

```
2.5. Loss function 
```

#### Section #15 — `section-0d1df367-e998-4cf3-b27b-103b4e8ecb6e`

- **score**: 0.588
- **text_level**: 1

**Section 标题/内容**

```
2.6. Training and test 
```

#### Section #16 — `section-dce0f68c-2752-4bf0-b8c5-de19a263abae`

- **score**: 0.559
- **text_level**: 1

**Section 标题/内容**

```
2.6.1.Network structures 
```

#### Section #17 — `section-bc4f66cc-d829-4c6a-959b-69e8b63d4b44`

- **score**: 0.529
- **text_level**: 1

**Section 标题/内容**

```
2.6.2. Training setup 
```

#### Section #18 — `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`

- **score**: 0.500
- **text_level**: 1

**Section 标题/内容**

```
2.6.3.Model evaluation metrics 
```

#### Section #19 — `section-bb3fcabe-5bdf-4dc1-935f-f8be8a1bbb7b`

- **score**: 0.471
- **text_level**: 1

**Section 标题/内容**

```
3. Results and analysis 
```

#### Section #20 — `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`

- **score**: 0.441
- **text_level**: 1

**Section 标题/内容**

```
3.1．Ablation studies 
```

#### Section #21 — `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`

- **score**: 0.412
- **text_level**: 1

**Section 标题/内容**

```
3.2.Performance comparison of FastSegFormer and other segmentation models 
```

#### Section #22 — `section-1f7ff486-5798-4a27-867d-e2e3f8ffbb55`

- **score**: 0.382
- **text_level**: 1

**Section 标题/内容**

```
3.3.Segmentation results of diferent models on the test set 
```

#### Section #23 — `section-cbae53f4-03e8-4cd1-8bdb-c7f9732fe679`

- **score**: 0.353
- **text_level**: 1

**Section 标题/内容**

```
3.4.Defect detection system deployment 
```

#### Section #24 — `section-30c66884-4443-4260-9f2f-e27680b7f3b5`

- **score**: 0.324
- **text_level**: 1

**Section 标题/内容**

```
3.4.1. Deployment setup 
```

#### Section #25 — `section-95ba5683-8c9f-4209-9f58-df611b13b2b7`

- **score**: 0.294
- **text_level**: 1

**Section 标题/内容**

```
3.4.2. Detection speed 
```

#### Section #26 — `section-4a6cbbd5-77ae-4e49-a504-4c3922a0a82d`

- **score**: 0.265
- **text_level**: 1

**Section 标题/内容**

```
4.Discussion 
```

#### Section #27 — `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`

- **score**: 0.235
- **text_level**: 1

**Section 标题/内容**

```
4.1. Comparison with related work 
```

#### Section #28 — `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`

- **score**: 0.206
- **text_level**: 1

**Section 标题/内容**

```
4.2.Future research 
```

#### Section #29 — `section-682d3ee7-4ea5-41f2-ba67-367372d63649`

- **score**: 0.176
- **text_level**: 1

**Section 标题/内容**

```
5.Conclusion 
```

#### Section #30 — `section-e75b119c-edbc-401a-a947-7876b775ef42`

- **score**: 0.147
- **text_level**: 1

**Section 标题/内容**

```
CRediT authorship contribution statement 
```

#### Section #31 — `section-e4a68ef4-1e13-4816-938f-a010ffa10296`

- **score**: 0.118
- **text_level**: 1

**Section 标题/内容**

```
Declaration of competing interest 
```

#### Section #32 — `section-fecf5047-8c16-4f3b-9026-307bf14d887d`

- **score**: 0.088
- **text_level**: 1

**Section 标题/内容**

```
Data availability 
```

#### Section #33 — `section-4f9fddec-e769-4684-867a-81dc7f7c4ae5`

- **score**: 0.059
- **text_level**: 1

**Section 标题/内容**

```
Acknowledgments 
```

#### Section #34 — `section-7fec891d-4040-4f16-b87d-0d71f371f80c`

- **score**: 0.029
- **text_level**: 1

**Section 标题/内容**

```
References 
```

### 2.2 Document → Chunk（按阅读顺序，完整文本）

- **返回数量**: 113
- **耗时**: 364.2ms

#### Chunk #1 — `chunk-f02fe099-2093-47e8-8139-286b8472ab3c`

- **score**: 1.000
- **chunk_type**: text

**Chunk 完整文本**

```
Original papers
```

#### Chunk #2 — `chunk-62812e80-c5df-4b6b-a0ca-fcddd55379dc`

- **score**: 0.991
- **section_id**: `section-617f792b-ea49-4752-b002-7dca2cd9a39e`
- **chunk_type**: text

**Chunk 完整文本**

```
Xiongjiang Caia,b, Yun Zhua,b,\*, Shuwen Liuab, Zhiyue $\mathrm { Y u ^ { a , b } }$ , Youyun Xu c

aSchool of Physicsand Electronic Information, Gannan Normal University,Ganzhou,341ooo,China
b National Navel Orange Enginering Research Center,China
NationdlEgctdofeocs
```

#### Chunk #3 — `chunk-3c7bf392-cb4e-462e-82eb-eca9eeddc5c0`

- **score**: 0.982
- **section_id**: `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`
- **chunk_type**: text

**Chunk 完整文本**

```
Dataset link: https://github.com/caixiongjiang /FastSegFormer, https://github.com/caixiongji ang/FastSegFormer-pyqt

Keywords:
Semantic segmentation
FastSegFomer
Lightweight model
Navel orange
Defect detection
```

#### Chunk #4 — `chunk-9a9ec0d8-76f8-4fe4-8438-926c4fd63d05`

- **score**: 0.973
- **section_id**: `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`
- **chunk_type**: text

**Chunk 完整文本**

```
Navel oranges are valued citrus fruits with a strong market presence,and detecting defects is crucial in their sorting due to common diseases and abnormalities during growth and transport.Deep learning,particularly semantic segmentation,is revolutionizing the fruit sorting industry by overcoming the limitations of traditional defect detection and enhancing the accuracy of clasifying complex defects in navel oranges.The FastSegFormer network,enabling real-time fruit defect detection,addresss this challnge with our introduced Multi-scale Pyramid (MSP)module for its architecture and a semi-resolution reconstruction branch post-feature fusion. We suggested a multi-resolution knowledge distillation strategy to further increase the network's segmentation accuracy.We developed a navel orange defectsegmentationdataset,trained,and evaluated our FastSegFormer-E model, designed for memory-constrained devices.It outperforms ENet by $3 . 1 5 \%$ ,achievinga mIoU of $8 8 . 7 8 \%$ on the test
```

#### Chunk #5 — `chunk-635225ce-4c7a-4d4a-80ed-8dd48aa95118`

- **score**: 0.965
- **section_id**: `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`
- **chunk_type**: text

**Chunk 完整文本**

```
defectsegmentationdataset,trained,and evaluated our FastSegFormer-E model, designed for memory-constrained devices.It outperforms ENet by $3 . 1 5 \%$ ,achievinga mIoU of $8 8 . 7 8 \%$ on the test set.The FastSegFormer-P model,tailored for high-speed detection,was tested on the mid-range RTX3060 graphics card, surpassing ENet by $3 . 7 \%$ with a mIoU of $8 9 . 3 3 \%$ and reaching 108 frames/s. The results demonstrate that the FastSegFormer-E model atains enhanced detection accuracy with reduced memory usage,whereas the FastSegFormer-P model stands out by striking an optimal balance between top-tierdetection accuracy and rapid processing speed.Deploying the algorithm system on the same platform as pipeline sorting, 20 frame/s was achieved ona Jetson Nano with very low computational power.The model significantly improves the detection of subtle and intricate edge defects,achieving real-time speeds. Our proposed algorithm enhances thefineness offruit sorting,resolves the limitation of
```

#### Chunk #6 — `chunk-2856b76a-d39c-4d46-b4c2-3e730ae52b02`

- **score**: 0.956
- **section_id**: `section-5ab5fc10-a2d7-4c36-b309-844ea26d52e8`
- **chunk_type**: text

**Chunk 完整文本**

```
model significantly improves the detection of subtle and intricate edge defects,achieving real-time speeds. Our proposed algorithm enhances thefineness offruit sorting,resolves the limitation of existing algorithms that apply to a narrow range of fruit sorting scenarios,and provides an efficient and accurate solution for large-scale navel orange defect detection.
```

#### Chunk #7 — `chunk-76dd468c-e85f-49b3-9536-9285c27598ef`

- **score**: 0.947
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
Grading fruits and vegetables by size,weight,shape,color,and maturity is essential for quality sorting,differentiating product grades, setting prices,and adding value for consumers (Allwood et al., 2021). Efficient fruit quality assessment and sorting ensure consumer satisfaction,reduce food waste,and streamline marketing for these fresh, tasty products.Navel oranges,identifiable by their distinct navel,are sweet, juicy,and rich in fiber and vitamin C (Hou et al., 2O2O; Xiang et al., 2020).Production of navel oranges includes sorting,which is moving from conventional machine learning to deep learning.Fruit sorting has gone from being mechanically operated to being automated thanks to the creation and marketing of the traditional vision system (Tripathi and Maktedar, 2O2O).With heightened fruit quality standards, better living conditions,and increased expectations,modern visual sorting systems are now honed for precise sorting.
```

#### Chunk #8 — `chunk-759dacbc-8108-4684-8881-6add0ca29285`

- **score**: 0.938
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
Fruit undergoes picking,handling, storage,and transportation from harvest to market,processes that entail considerable losses.As a perishable commodity, fruit faces challenges in post-harvest loss reduction, which currently constitutes the majority $( 8 6 \% )$ of overall fruit losses globally (Soltani Firouz and Sardari, 2O22). Fruit quality mainly declines due to diseases,defects,and decay,with navel oranges often suffering from ulcers,sunburn
```

#### Chunk #9 — `chunk-3fa506ec-9b6b-48fa-8405-59f335159d70`

- **score**: 0.929
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
，wind scarring,and oil cell damage, each with unique and complex traits. Initially,separating defective from healthy fruit relied on combining classic image segmentation with traditional machine learning techniques. The morphology and appearance aspects of fruits are used to manually create feature extraction techniques,which are subsequently used to distinguish fruits using conventional classification algorithms (Rong et al., 2Ol7a). This kind of feature extraction approach necessitates in-depth prior knowledge, has low generalization and extraction accuracy,and frequently manifests as missed detection.However,deep learning,especially convolutional neural networks (CNNs),has overcome these drawbacks,providing substantially higher accuracy than traditional machine learning approaches.
```

#### Chunk #10 — `chunk-e85fef9e-e924-4f74-ad31-965dfb2ac4c5`

- **score**: 0.920
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: image
- **image_file**: `df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #11 — `chunk-437c6137-40b1-4839-a942-9449a0134f5f`

- **score**: 0.912
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
With the continuous advancement in computer computational capabilities,deep learning has emerged as the prevailing approach for fruit defect detection.Currently,systems for detecting fruit defects mostly use image classification methods based on deep learning.Azizah et al.(2Ol7) utilized a digital camera to take pictures of mangosteens and used a simple convolutional neural network (CNN) to identify defective fruits. De Luna et al. (2O19) classified tomato defects using the traditional networks VGG16,InceptionV3,and ResNet50,with the VGGl6 model achieving the maximum classification accuracy of $9 8 . 7 5 \%$ .With an accuracy of $9 8 . 5 \%$ ,Nithya et al. (2022) developed a deep learning vision system to identify mango defects.The empirical findings demonstrated that deep learning-based vision systems exhibit significantly superior accuracy compared to conventional machine vision methods.However,the image classification technology is unable to distinguish between different kinds of
```

#### Chunk #12 — `chunk-55f28f03-8104-4679-b515-2f3028d9890b`

- **score**: 0.903
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
vision systems exhibit significantly superior accuracy compared to conventional machine vision methods.However,the image classification technology is unable to distinguish between different kinds of defects in a single image, pinpoint where defects are located,or otherwise meet the demands of fine sorting (Ismail and Malik, 2022)
```

#### Chunk #13 — `chunk-4f09143d-e18f-4a83-9bf5-67e0dfb4cb94`

- **score**: 0.894
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
Target detection models and semantic segmentation models with a higher number of parameters compared to classification models are gradually being employed in fruit defect detection as graphics cards' processing capacity increases.The problem of the variety of defects in a single image that is difficult to recognize is resolved by the target detection approach,which locates faults and classifies them using rectangular boxes.Wang et al. (2O2O) strengthened the fusion of horizontal features,enhanced the feature pyramid module (FPM) based on the Mask R-CNN network,and performed defect detection for apples,oranges,peaches,and pears,respectively. The mean average accuracy (mAP) of detection reached $9 6 . 1 4 \%$ ， $9 5 . 9 5 \%$ ， $9 6 . 6 8 \%$
```

#### Chunk #14 — `chunk-80330422-0810-40ae-8350-48b9345a4176`

- **score**: 0.885
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
， $9 5 . 9 5 \%$ ， $9 6 . 6 8 \%$ ，and $9 5 . 8 4 \%$ ．A strong generalizability model was established for defect detection of round fruits.In addition to identifying and classifying the defects, the semantic segmentation method separates each pixel in the image,which makes it easier to discover complicated edge features. With a mloU of 86.6 percent, Roy et al. (202l) presented an improved UNet architecture for distinguishing between fresh and rotting fruits. These studies broaden fruit defect detection to more scenarios,but none of them take into account how well the models function when deployed in large-scale applications.
```

#### Chunk #15 — `chunk-20369e89-0c71-4269-a0c8-35e2273a0429`

- **score**: 0.876
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
A critical factor enabling the broad implementation of defect detection models is their capacity to consistently achieve real-time detection performance while maintaining a high level of detection accuracy. Studies on target detection and semantic segmentation-based real-time detection of fruit defects are scarce.To enable real-time detection of kiwi fruit, Yao et al.(2O2l) integrated the Squeeze-and-Excitation (SE) layer into YOLOv5.Fan et al. (2022) reduced the number of channels and network depth in the YOLOv4 network while capturing photos of Apple-defective objects with the NIR camera.The network model is 8.82 megabytes (MB) in size,and it only takes $8 . 3 6 \mathrm { m } s$ to detect a single image,while mAP grows by $1 . 9 2 \%$ Liang et al. (2022) used a pallet apple defect detection scenario to introduce the small segmentation network BiSeNetV2 and used the pruned YOLOv4 to help with the issue of the segmentation network erroneously segmenting fruit stems. Despite using two
```

#### Chunk #16 — `chunk-963e9255-912a-4053-9ba2-41fb14443885`

- **score**: 0.867
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
scenario to introduce the small segmentation network BiSeNetV2 and used the pruned YOLOv4 to help with the issue of the segmentation network erroneously segmenting fruit stems. Despite using two networks,the strategy of merging the two ways for detection still offers a high detection speed that surpasses most segmentation networks.
```

#### Chunk #17 — `chunk-71f4a24a-6744-4d62-afe4-0c7ec611bc42`

- **score**: 0.858
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
Combining the results of the aforementioned investigations, existing fruit defect detection techniques face challenges in their adaptability to fine-sorting requirements.Furthermore,a majority of the target detection and semantic segmentation methods,despite fulfilling the necessary criteria, lack scalability for large-scale deployment. We proposed the real-time segmentation network FastSegFormer for navel orange defect detection.We made some changes to the PPM structure (Zhao et al.,2017),suggested adding the MSP module to the feature extraction stage,and created a branch for semi-resolution input images that performs edge feature recovery after feature fusion.Finally,it was suggested to use a multi-resolution knowledge distillation strategy to improve the fruit defect segmentation model's segmentation performance while keeping the model's size and inference speed constant.Deploying the model in a very low computational power edge computing device,the Jetson Nano,reached 2O fps,which
```

#### Chunk #18 — `chunk-9f5b8f5b-540e-4d48-aad1-939bda523151`

- **score**: 0.850
- **section_id**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **chunk_type**: text

**Chunk 完整文本**

```
segmentation performance while keeping the model's size and inference speed constant.Deploying the model in a very low computational power edge computing device,the Jetson Nano,reached 2O fps,which has great potential for real detection speed.The proposed model offers aremarkable capability for accurately detecting fruit defects within intricate scenarios while simultaneously enhancing the detection speed of the inspection system.Consequently,it exhibits adaptability for widespread deployment in large-scale navel orange sorting lines.
```

#### Chunk #19 — `chunk-dfb9b2d8-a250-4deb-9524-d20bb8e28c50`

- **score**: 0.841
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
In fruit sorting operations prioritizing security，scalability,and portability,edge computing stands out. To align with the assembly line's velocity,the segmentation model is required to process a minimum of 30 images per second. The Jetson Xavier NX is a top choice for such tasks,offering robust 21 TOPS of INT8 computing power and 16 GB of memory,which ensures quick and reliable image processing capabilities.Therefore,model optimization should be implemented to improve inference speed and reduce resource consumption.Additionally,efficient data management strategies are also crucial for handling large volumes of training and test data effectively.
```

#### Chunk #20 — `chunk-d6211d26-702c-4081-a427-b4a03ebc8f6a`

- **score**: 0.832
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
As seen in Fig.1(a),we created a straightforward navel orange image acquisition device. The system comprises an autonomous rotating display stand and an industrial camera model UC3o,with the camera connected to a computer for some automated functions.Consistent and stable white LED light sources are positioned on the camera side, as well as on the left and right sides of the navel orange.The light source is positioned at the same height as the camera,ensuring that they are aligned flush with each other. The following is the image acquisition procedure: (i) A navel orange fruit is placed on a rotating display stand with a rotation speed of 4 s per revolution. (ii) A script on the computer directs the camera to take 30 photographs evenly spaced throughout the following 4 s. (ii) Replace the navel orange and repeat the aforementioned procedures after choosing 5 images at uniform intervals.
```

#### Chunk #21 — `chunk-c50ad5ed-8f2c-44b0-9806-8517b35746f9`

- **score**: 0.823
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
In Ganzhou City, Jiangxi Province, China's Xinfeng Town, we gathered pictures of navel oranges with defects during October and November 2022.All of our fruit comes from orchard picking,and navel oranges are currently in the middle of their harvest.With a resolution of $2 5 9 2 \times 1 9 4 4 ~ \mathrm { p x }$ ,1448 photos of the three defects of wind scarring, ulcers,and sunburn were collected to simultaneously detect several defects.As seen in Fig.1(b),after batch cropping every image and setting the resolution back to $5 1 2 \times 5 1 2 \ \mathrm { p x }$ ,the Labelme tool is used to begin labeling the pictures.
```

#### Chunk #22 — `chunk-c7227fb1-2dfa-489c-b544-e33a18df5958`

- **score**: 0.814
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
In a 6:2:2 division of the 1448 labeled navel orange defect photos, 868 were used as the training set,29O as the validation set,and 290 as the test set. To identify defects in navel oranges,we employed data augmentation to imitate conditions like uneven lighting and highspeed motion blur in an industrial assembly line.The following are the strategies for data enhancement: (i) Geometric transformations, including random rotation, random cropping, horizontal specular flip, and vertical specular flip.(ii) Modifications to the pixel distribution, such as brightness modification, Gaussian blur, and image sharpening. We used the Imgaug toolbox to automatically construct the mask for the added photos to reduce the burden associated with annotating defect masks.Fig.2 displays the modifications to the image and mask caused by some of the image-enhancing techniques.The extended navel orange defect dataset comprises a total of 4344 photos,comprising 2604 images in the training set, 87O images in
```

#### Chunk #23 — `chunk-ca3ae746-8e9d-4b15-91b9-1c96da31fc3a`

- **score**: 0.805
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
the image and mask caused by some of the image-enhancing techniques.The extended navel orange defect dataset comprises a total of 4344 photos,comprising 2604 images in the training set, 87O images in the validation set, and 870 images in the test set.We randomly applied a single technique to each image twice.
```

#### Chunk #24 — `chunk-207ed262-7197-41f7-a5cf-231a4992a268`

- **score**: 0.796
- **section_id**: `section-dd8fcae1-b4df-4764-af5a-a0358307f200`
- **chunk_type**: text

**Chunk 完整文本**

```
The pixel ratios of the three defects in the dataset of 4344 images are approximately equal,which effectively addresses feature imbalance and enhances the model's ability to capture detailed information and global features across different-scale images. It also mitigates training bias and ensures consistent performance across varied scales.
```

#### Chunk #25 — `chunk-1b85485f-425f-425b-ac18-deab16706151`

- **score**: 0.788
- **section_id**: `section-2db880b8-4571-423a-ac82-0c44a1909bc2`
- **chunk_type**: text

**Chunk 完整文本**

```
UNet was created to enhance the ability to segment intricate features at the borders of medical picture segmentation.With a distinctive hierarchical structure,it is a symmetric encoder and decoder design that retains more spatial features of the image (Ronneberger et al., 2015). The encoder includes some convolutional filters and some maximum pooling layers,starting from the input image and downsampling 2 times at a time,and increasing the number of convolutional filters to 2 times the original,the decoder process is the opposite,with upsampling accomplished by bilinear interpolation.UNet's network architecture is deep,and its highly distinctive skip connection both prevents overfitting and preserves image details well.
```

#### Chunk #26 — `chunk-be144466-995a-424e-aa45-f590402e980b`

- **score**: 0.779
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
Sunburn,ulcers,and wind scarring are the three most prevalent defects in navel oranges.According to Fig.1(c),each of the three defects has unique characteristics. Large dark patches are seen in sunburn, round black and brown cavities are visible inulcers,and diverse colors and different shapes with intricate edge characteristics are visible in wind scars.The UNet architecture is more suited for reconstructing complex and variable defect characteristics,but the arduous process of upsampling recovered images adds more parameters and lengthens inference time,making deployment much more challenging.A critical question is how to simplify the model while maintaining its capacity to recognize intricate characteristics.
```

#### Chunk #27 — `chunk-7ea4157e-54f7-4f01-a11c-573dce816539`

- **score**: 0.770
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
Holder and Shafique (2022) studied some well-known real-time segmentation networks,and found that there are primarily two methods for achieving real-time network inference: one involves pairing high-resolution images with very small network models,and the other involves pairing lower image resolution with more intricate network structures.Low-resolution, fast industrial cameras are frequently purchased to save money since fruit assembly lines demand exceptionally high defect detection efficiencies.We used a lower-resolution network structure model to account for this circumstance,bringing down the input resolution of the photos to $2 2 4 \times 2 2 4 \ : \mathrm { p x }$
```

#### Chunk #28 — `chunk-4f56a1d1-185c-4b74-ab2d-8a654d2e8334`

- **score**: 0.761
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
Researchers frequently employ convolutions with low channel counts or less computationally intensive structures to develop lightweight segmentation networks.ENet (Paszke et al.,2O16) comprises a relatively large encoder and a simple decoder.The network utilizes standard $3 \times 3$ convolutions,asymmetric $5 \times 5$ convolutions,and similar techniques.However,the compact network structure and a limited number of convolutional channels enable a reduced parameter count.Fast-SCNN (Poudel et al., 2O19) takes advantage of depthwise separable convolution (Ds Conv） and utilizes standard convolutions witha reduced number of channels.This strategy enables the network to increase its depth and capture global information efficiently,without compromising computational resources. BiSeNet (Yu et al., 2O18) and SwiftNet (Orsic et al.,2O19) utilize a two-branch structure for feature extraction: one branch extracts contextual information,while the other focuses on spatial information.The features
```

#### Chunk #29 — `chunk-63b643be-ab9d-4557-a75c-6db76d06fac0`

- **score**: 0.752
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
2O18) and SwiftNet (Orsic et al.,2O19) utilize a two-branch structure for feature extraction: one branch extracts contextual information,while the other focuses on spatial information.The features from both branches are subsequently fused.Our network combines two features: the first branch extracts features and incorporates earlier representations for feature fusion,while the second branch performs simple image sampling for eficient image reconstruction,preserving details without excessive parameters.
```

#### Chunk #30 — `chunk-a2b3f0ad-13ae-43c6-9f4c-88d01dd314c6`

- **score**: 0.743
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: image
- **image_file**: `e5ccb286582a4e67044b5badf585d7bd40151d65ad4fe37b811099e402856e48.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/e5ccb286582a4e67044b5badf585d7bd40151d65ad4fe37b811099e402856e48.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #31 — `chunk-2cca78b7-d9d5-4514-8cca-e4fce8f7edd1`

- **score**: 0.735
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
Fig.3 depicts the FastSegFormer network design. First,we performed image downsampling during the encoding stage using the Pool-Former and EfficientFormerV2 backbone networks.The network moves on to feature extraction after the backbone network.We presented the Linear Bottleneck (LB) module from the MobileNetV2 network (Sandler et al.,2O18) and designed the Multi-scale Pyramid (MSP) module,a multi-scale information extractor,in its place.The LB module achieves feature map compression or condensation by reducing the number of channels through dimensionality reduction.This operation effectively filters out redundant information and low-level features,preserving important and high-level feature information. The MSP module captures contextual information by employing multi-scale convolutions to enhance the model's ability to perceive objects at various scales. The high-level features are then combined with the low-level features from the intermediate output of the backbone network's shallow
```

#### Chunk #32 — `chunk-2bb752ef-c3a9-44ec-856a-110c2b06ebe9`

- **score**: 0.726
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
enhance the model's ability to perceive objects at various scales. The high-level features are then combined with the low-level features from the intermediate output of the backbone network's shallow output during the decoding stage,and we employ some DS Conv modules (Sifre and Mallat, 2Ol4) to lessen the computing burden of the model.Finally,we added an image reconstruction branch,which takes the semi-resolution image input, adds fusion features by convolution, and then upsamples the image.This branch is primarily designed to compensate for the loss of early high-resolution detailed features in the deeper feature extraction phase of the network.This guarantees the model's small weight while maintaining the properties of UNet employing skip connections.With only a little increase in the number of parameters,it has been demonstrated that the image reconstruction branch can significantly improve the model's performance,particularly when it comes to the detection of fine-grained complex
```

#### Chunk #33 — `chunk-a3424788-3890-4c80-971a-489b368273a4`

- **score**: 0.717
- **section_id**: `section-3a18d7a6-cf1a-4f14-b33f-96c8d04dbe1f`
- **chunk_type**: text

**Chunk 完整文本**

```
of parameters,it has been demonstrated that the image reconstruction branch can significantly improve the model's performance,particularly when it comes to the detection of fine-grained complex features.Batch Normalization and Rectified Linear Unit (ReLU) are performed after all convolutions to speed up model training.
```

#### Chunk #34 — `chunk-5e0dc887-30b7-4d22-b50c-fc75eb546a14`

- **score**: 0.708
- **section_id**: `section-655c8782-ad75-4055-b653-ded79d73dca2`
- **chunk_type**: text

**Chunk 完整文本**

```
A backbone network can be used for feature extraction and finetuning,and it usually has two options at present,one is a CNN network, and the other is the Transformer network.For the lightweight segmentation model, the parameters and computation of the backbone network determine the overall size of the network.The traditional CNN lightweight backbone network has a small number of parameters but weak feature extraction capability,and many special convolutions are not conducive to hardware implementation, such as DS Conv (Sandler et al.,2O18).For tasks with certain requirements of detailed information,multi-scale information extraction is important,but using multi-scale convolution in the early period of the network when the feature map is large will greatly increase the number of parameters.Transformer differs from CNN in that it processes the whole image at the same time,focusing more on global information and having better feature extraction capability (Dosovitskiy et al.,2020). For
```

#### Chunk #35 — `chunk-9c3575d8-af38-4756-9e92-2cc964a230e0`

- **score**: 0.699
- **section_id**: `section-655c8782-ad75-4055-b653-ded79d73dca2`
- **chunk_type**: text

**Chunk 完整文本**

```
differs from CNN in that it processes the whole image at the same time,focusing more on global information and having better feature extraction capability (Dosovitskiy et al.,2020). For hardware,Transformer's internal self-attention mechanism is very time-consuming and Transformer's lightweight can make a huge difference.Yu et al.(2O22） replaces the self-attentive mechanism in Transformer with a simple multi-layer perceptron (MLP)and found that it also worked,and they called this module PoolFormer.Li etal.(2022) replaces Transformer with Pool mixer in the early stages of the network, which greatly reduces the number of parameters and maintains good performance.
```

#### Chunk #36 — `chunk-328df3aa-8e7f-476a-9382-2bfeafd347eb`

- **score**: 0.690
- **section_id**: `section-655c8782-ad75-4055-b653-ded79d73dca2`
- **chunk_type**: text

**Chunk 完整文本**

```
The transformer structure-based lightweight backbones PoolFormer and EfficientFormerV2 both better collect global contextual data. PoolFormer-S12 and EfficientFormerV2-SO are the two minimal versions of the series network that we have selected.
```

#### Chunk #37 — `chunk-29a9cac0-a6d7-4e56-bbf4-0e4d95dbf641`

- **score**: 0.681
- **section_id**: `section-8f778125-8ee2-40ac-ad65-084d97732606`
- **chunk_type**: text

**Chunk 完整文本**

```
We initially reduced the number of picture channels to 256 using point-by-point convolution to decrease the overhead in the feature extraction stage.MobileNetV2 introduced the inverted residual block LB,which expands the feature map before compressing it,reversing the common practice of reducing and then expanding features (Sandler et al.,2O18). The LB module,depicted in Fig.4, first increases the number of channels in the feature map by three times,then passes them through a second depthwise (DW) convolution and ReLU, before compressing the number of channels and adds a residual connection.
```

#### Chunk #38 — `chunk-ad127c7f-3e2b-453d-b5d9-896ce0eade65`

- **score**: 0.673
- **section_id**: `section-8f778125-8ee2-40ac-ad65-084d97732606`
- **chunk_type**: text

**Chunk 完整文本**

```
The pyramid pooling module (PPM) is an efficient multicore pooling layer,and the output feature maps of these pooling layers are connected along the channel dimension to form a multiscale representation of the input feature maps (Zhao et al., 2Ol7). Pooling is computationally simple,but more information is lost,based on which an MSP module is designed. Fig.5 depicts the MSP module's structural layout. In the MSP module, the $_ \mathrm { ~ 1 ~ \times ~ 1 ~ }$ ， $3 \times 3$ ， $5 \times 5$
```

#### Chunk #39 — `chunk-3db86e6f-0e78-442f-b2b4-0623342835cb`

- **score**: 0.664
- **section_id**: `section-8f778125-8ee2-40ac-ad65-084d97732606`
- **chunk_type**: text

**Chunk 完整文本**

```
， $3 \times 3$ ， $5 \times 5$ ，and $7 \times 7$ convolutions are employed,with each one being followed by a ${ \bf 1 } \times { \bf 1 }$ convolution, feature map stitching,and a $1 \times 1$ convolution to turn back the number of channels of the input picture.We perform padding in the feature map's multi-scale convolution to better preserve the edge information at low resolution.This makes sure that the feature maps are the same size both before and after input,and it reduces computation by changing the number of channels after multi-scale convolution to 1/4 of the original size.
```

#### Chunk #40 — `chunk-baf01be2-9385-43f0-8fba-0ec1b4e3b261`

- **score**: 0.655
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: text

**Chunk 完整文本**

```
The detailed features of the image steadily disappear as the number of network levels increases.Wang et al. (2O22) used an experiment to show that the lost spatial resolution of downsampling can be recovered by using a skip connection at the start of UNet. To employ this feature, an image reconstruction branch from the input image with a halfresolution resolution is first added to the network,then the feature
```

#### Chunk #41 — `chunk-61649eea-e64e-41d6-b45e-81aa944e91d5`

- **score**: 0.646
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: image
- **image_file**: `ac604caf981504521c0c073efc6ce7fff7e455a79b118053eb6477b653477511.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/ac604caf981504521c0c073efc6ce7fff7e455a79b118053eb6477b653477511.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #42 — `chunk-a58c19ec-cab6-4b18-b326-8edc79eed0aa`

- **score**: 0.637
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: image
- **image_file**: `50f9bc5ec26646cb3effdb91959f648b335b53a67c2932f991bbc1a227e2ae8e.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/50f9bc5ec26646cb3effdb91959f648b335b53a67c2932f991bbc1a227e2ae8e.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #43 — `chunk-f1be069c-5392-402a-ae1b-a4d76414fa82`

- **score**: 0.628
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: image
- **image_file**: `98374e7e5299df72731d9f78242af18cf4e409d5e162e8279d554ce9ff18e958.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/98374e7e5299df72731d9f78242af18cf4e409d5e162e8279d554ce9ff18e958.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #44 — `chunk-04f60bd8-5365-4cd9-a661-75e14d0fbe79`

- **score**: 0.619
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: image
- **image_file**: `ecf393d19d6dd752fcdbf4d9d8a228a1c2300bc598438255527468f8d8869482.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/ecf393d19d6dd752fcdbf4d9d8a228a1c2300bc598438255527468f8d8869482.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #45 — `chunk-e329d9bf-011a-4090-9608-a47b4821bb0f`

- **score**: 0.611
- **section_id**: `section-6da38ecb-56a3-46ba-b139-c6473484a550`
- **chunk_type**: text

**Chunk 完整文本**

```
fusion results are added,and finally,the resolution of the input image is restored using convolution and upsampling.We find it amazing that increasing the amount of computing very litle improves the ability to recognize details.
```

#### Chunk #46 — `chunk-9dfead86-cf5c-4827-aeeb-ef0b7ef0ca7b`

- **score**: 0.602
- **section_id**: `section-e2e0f765-01a7-46af-85b6-37ede7f8dbed`
- **chunk_type**: text

**Chunk 完整文本**

```
Larger,more capable models can act as teachers thanks to a novel transfer learning strategy called knowledge distillation,which enables student models to independently learn the data distribution of the teacher's network.Without adding to the computational load,models can learn richer feature representation,and with the correct methodology,student models may even outperform teacher models (Heo et al., 2019).The overall approach to knowledge distillation is shown in Fig.6.We employed offline distillation,the parameters of the teacher model are trained in advance and are not changed throughout the distillation process.We learned the feature maps of the intermediate output of the teacher model in addition to distilling the model's output results.
```

#### Chunk #47 — `chunk-49f0e339-adee-4d30-be1e-a31768e3d46c`

- **score**: 0.593
- **section_id**: `section-4987636c-b976-41d6-90d7-d4262b19a8d3`
- **chunk_type**: text

**Chunk 完整文本**

```
The teacher model in the general knowledge distillation approach is an extended version of the student model with the same input resolution to facilitate teaching (Heo et al., 2O19; Liu et al., 2019). We think that the data distribution or“knowledge”obtained from the teacher model,not the teacher model itself,is what knowledge distillation learns.The teacher model's input resolution was increased to improve distillation,as shown in Fig.6,and the top-performing UNet series model was chosen for the teacher model. The overall design of the teacher model replaces the feature extraction of the UNet model with Swin-Tiny's backbone network (Liu et al.,2021) and adds a potent cascading attention mechanism called Attention Gate (AG) (Oktay et al., 2018) before skipping connections.By sampling all of the instructor model's outputs,the issue of a non-uniform feature map size caused by varying input resolutions is resolved. Using pointby-point convolution,the student model is also converted to
```

#### Chunk #48 — `chunk-f7367ee4-8597-473e-9687-603352a75df8`

- **score**: 0.584
- **section_id**: `section-4987636c-b976-41d6-90d7-d4262b19a8d3`
- **chunk_type**: text

**Chunk 完整文本**

```
of the instructor model's outputs,the issue of a non-uniform feature map size caused by varying input resolutions is resolved. Using pointby-point convolution,the student model is also converted to have the same amount of channels as the teacher model.The following is the distillation procedure:
```

#### Chunk #49 — `chunk-8617914d-320b-4711-be80-5123abc62747`

- **score**: 0.575
- **section_id**: `section-4987636c-b976-41d6-90d7-d4262b19a8d3`
- **chunk_type**: text

**Chunk 完整文本**

```
(i) After achieving the best accuracy when training the complex model using $5 1 2 \times 5 1 2 \ \mathrm { p x }$ images,store the parameters. (ii) To avoid backpropagation,the instructor model loads the previously saved parameters and locks them.The $2 2 4 \times 2 2 4$ px images are used to train the student model,which is then iterated through the segmentation loss function and the distillation loss function. (ii) Take note that the backbone network's pre-trained parameters must be locked for 5O training epochs before being unlocked if distillation and fine-tuning are carried out simultaneously to maintain the fine-tuning effect.
```

#### Chunk #50 — `chunk-19cda2a2-2e5e-450c-b0fe-4933a8c79c1a`

- **score**: 0.566
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
The Cross entropy (CE) loss function is used between the predicted results of the model and the labels and is calculated as follows:

where $q _ { i }$ represents the probability of the ith category of pixels, $y _ { i }$ represents the true label of the ith category of pixels,and $c$ represents the number of categories.

After adding the knowledge distillation method,we introduce the feature distillation loss function for the intermediate feature maps and use the logits distillation loss function for the model output results. As in the method described in Section 2.4.1,the size and number of channels of the feature maps of the complex and simple networks have been transformed to be the same before performing the calculations.
```

#### Chunk #51 — `chunk-4b8d6ff5-88c8-4587-acd8-29a5753d81c1`

- **score**: 0.558
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
Logits distillation.The logits distillation takes a common approach (Hinton et al.,2O15):using the category probability of the output results of the complex model as a soft target. To this,we add the calculation of the mean square error of the output pixels between the complex and simple networks.

The logits distillation loss function is given as follows:
```

#### Chunk #52 — `chunk-78f58ebd-8dbd-4037-9a13-71691a7ca375`

- **score**: 0.549
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
where $q _ { i } ^ { s }$ represents the class probability of the ith pixel output from the simple network S, $q _ { i } ^ { t }$ represents the class probability of the ith pixel output from the complex network T,KL(-) represents Kullback-Leibler divergence, $p _ { i } ^ { s }$ represents the ith pixel output from the simple network S, $p _ { i } ^ { t }$ represents the ith pixel output from the complex network T,MSE(-) represents the mean square error calculation, $\boldsymbol { R } = \{ 1 , 2 , \dots , W _ { s } \times H _ { s } \}$ represents all pixels,and $t$ represents the temperature coefficient. In this experiment, $t = 2$ ， $k _ { 1 } = 0 . 5$
```

#### Chunk #53 — `chunk-9b97997b-ef10-4c3d-ae22-f3f64fdac160`

- **score**: 0.540
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
Normalized feature distillation.Feature distillation transfers knowledge by minimizing the distance between complex and simple networks in the feature space.Before calculating the distance,it is usually necessary to convert the hidden features of complex and simple networks into a form that can be easily transferred (Heo et al.,2019). We introduce a streamlined approach to distillation, termed normalized distillation.This technique involves standardizing the width and height dimensions as part of a feature transformation between intricate and straightforward network architectures (Liu et al.,2022).We then compute the Euclidean distance between these normalized features to formulate a loss function expressly for normalized feature distillation (NFD).

The NFD loss function is given as follows:
```

#### Chunk #54 — `chunk-a4a7c134-9454-4d95-910d-bbe2c9b50277`

- **score**: 0.531
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
where $n$ represents the number of intermediate feature maps, $W _ { s }$ and $H _ { s }$ represent the height and width of the simple model feature map, $L _ { 2 } ( \cdot )$ represents the Euclidean calculation of the feature maps, $F _ { i } ^ { t }$ represents the ith feature map generated by the complex network T, $F _ { i } ^ { s }$ represents the ith feature map generated by the simple network S, Normal represents the normalization of the feature maps on $( W , H )$ the Normal(·) in Eq. (3) is given as follows:

where $F$ represents the original feature map, $\bar { F }$ represents the feature transform,and $\boldsymbol { u }$ and $\sigma$ represent the mean and standard deviation of the features.

Using knowledge distillation for training,the following is our total loss function:
```

#### Chunk #55 — `chunk-a8eabb33-e334-481c-ad3f-dafcf0bc62b1`

- **score**: 0.522
- **section_id**: `section-6f0c74ca-f433-4791-82a5-98b9636a3de0`
- **chunk_type**: text

**Chunk 完整文本**

```
where $\lambda _ { 1 }$ is set to $0 . 5 , \ \lambda _ { 2 }$ is set to 5.When $\lambda _ { 1 }$ is equal to O.5 and $\lambda _ { 2 }$ is equal to 5,the values of the feature distillation loss and logits distillation loss are comparable to $L _ { c e }$
```

#### Chunk #56 — `chunk-78f37913-bdac-452b-afdd-b03f30118a77`

- **score**: 0.513
- **section_id**: `section-dce0f68c-2752-4bf0-b8c5-de19a263abae`
- **chunk_type**: text

**Chunk 完整文本**

```
In this paper,we built the FastSegFormer model and created two models,dubbed FastSegFormer-P and FastSegFormer-E,based on the PoolFormer-S12 backbone and EfcientFormerV2-S0 backbone,respectively,to uncover two detection strategies with high detection speed and low memory.Both models were put through ablation studies to examine the impact of the MSP module and the image reconstruction branch: (i) Baseline model: The MSP module is replaced with PPM and the image reconstruction branch is eliminated based on the FastSeg-Former model.(ii) The MSP module is used in place of the PPMbased on the baseline model.(iii) The article's FastSegFormer model. Some additional tests on image enhancement were also added to the ablation experiments of the model structures.
```

#### Chunk #57 — `chunk-0b500778-d0a0-41b2-b499-c9a940111851`

- **score**: 0.504
- **section_id**: `section-dce0f68c-2752-4bf0-b8c5-de19a263abae`
- **chunk_type**: text

**Chunk 完整文本**

```
We also contrasted the benefit of distillation in FastSegFomer with the impact of fine-tuning.Different weights were applied to feature distillation and logits distillation for both models,aiming to explore the roles of distillation strategies.

We used several well-nown lightweight models (ENet, BiSeNet, Fast-SCNN, SwiftNet,FANet, and PIDNet) for training and testing at an input resolution of $2 2 4 \times 2 2 4$ to assess the functionality and inference speed of FastSegFormer.The distillation-boosted FastSegFormer model is employed here,and the training setup is the same as FastSegFormer, see Section 2.6.2 for more information.
```

#### Chunk #58 — `chunk-32e39a63-faa0-490c-bfe1-8eba6ec7bfca`

- **score**: 0.496
- **section_id**: `section-bc4f66cc-d829-4c6a-959b-69e8b63d4b44`
- **chunk_type**: text

**Chunk 完整文本**

```
Using Pytorch 1.12.1 and CUDA 10.2,all models in this study were trained in a 64-bit Windows 1O environment. For training,we choose the Adam optimizer,and its internal momentum parameter is set to O.9.The learning rate was managed using a warm-up and the cosine annealing process.For model training and model inference speed testing,a computer equipped with an Intel Core i5-10500 $@ 3 . 1 0$ GHz processor,16 GB of RAM,and a GeForce RTX306O graphics card was employed. For normal training, the input image resolution is $2 2 4 \times 2 2 4$ ， and the batch size is 32.For distillation training,the image resolution is $5 1 2 \times 5 1 2$ ,and the batch size is 6.All model training times were set to 1000 epochs,and the maximum baseline learning rate $( B L R _ { m a x } )$ was set to O.oool.To adapt the network to different mini-batches,we set the adaptive adjustment of the learning rate,Eq.(6) is its definition.
```

#### Chunk #59 — `chunk-48ebd40f-2ec2-4dac-83d0-7d6f985d6746`

- **score**: 0.487
- **section_id**: `section-bc4f66cc-d829-4c6a-959b-69e8b63d4b44`
- **chunk_type**: text

**Chunk 完整文本**

```
where $M a x L R$ and MinLR denote adaptive maximum learning rate and adaptive minimum learning rate，respectively.BS denotes the batch size,and $B L R$ denotes the benchmark learning rate.
```

#### Chunk #60 — `chunk-808bc681-168c-4324-97ff-34e7413a1b72`

- **score**: 0.478
- **section_id**: `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`
- **chunk_type**: text

**Chunk 完整文本**

```
In this paper, the model performance is evaluated comprehensively in terms of both detection performance and deployment performance. The metrics of detection performance are mean pixel accuracy (mPA), mean precision (mPrecision),intersection over union (IoU),and mean intersection over union (mIoU).The metrics that reflect the deployment performance are model parameters (Params/M),computation (GFLOPs),and model segmentation speed (Speed/FPS).The model metrics are given as follows:

where $T P$ means True Positive,which is the number of pixels correctly classified, $F P$ means False Positive,which is the number of pixels incorrectly classified, $T N$ means True Negative,which is the number of pixels correctly classified as other classes,and $F N$ means False Negative,the number of pixels incorrectly classified as other classes. $c$ means the number of pixel categories except for the background.
```

#### Chunk #61 — `chunk-541db947-18e8-4c34-bc01-b917d45b4bf4`

- **score**: 0.469
- **section_id**: `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`
- **chunk_type**: text

**Chunk 完整文本**

```
Every five epochs during training,the model calculates the mIoU of the validation set and saves the parameters to better assess its segmentation capabilities.The parameters with the highest mIoU after training are utilized to evaluate the test set and to determine the model's performance.
```

#### Chunk #62 — `chunk-a728dd21-9dac-4d39-9252-e79de14af211`

- **score**: 0.460
- **section_id**: `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`
- **chunk_type**: image
- **image_file**: `c7ec19f5225efb43b0951f7a0874fed5a62e21b118cbb420c7d046743f6aff11.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/c7ec19f5225efb43b0951f7a0874fed5a62e21b118cbb420c7d046743f6aff11.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #63 — `chunk-7a37b1af-8afc-452b-9408-fe3a5363a1e5`

- **score**: 0.451
- **section_id**: `section-f0ed8efc-6857-4689-8690-bd2c16e7df75`
- **chunk_type**: image
- **image_file**: `07c510f12925ab42a36835d8c36c41a16c055bb300ca06a65932c7482fc52bce.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/07c510f12925ab42a36835d8c36c41a16c055bb300ca06a65932c7482fc52bce.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #64 — `chunk-8b978b84-20c0-48b2-96fb-204f5d7134e5`

- **score**: 0.442
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
On the self-created navel orange dataset,ablation studies and additional testing of data enhancement using FastSegFormer models with various structures.Data enhancement techniques,the addition of MSP and the inclusion of image reconstruction branches can all significantly improve accuracy compared to the validation set in Fig.7.Due to less convolutional computation being done for up-sampling following the fusing of semi-resolution picture inputs, the accuracy rise for the FastSegFormer model with image reconstruction branching is a little slower.While adding image details,this branch also disrupts the original global data,which must be fixed in later upsampling.We include a portion of the training time as a cost to lessen the rise in computation. It should be highlighted that the EfficientFormerV2-SO's architecture is considerably more complex than that of the PoolFormer-S12, featuring an intricate network of dense branch connections and sophisticated fusion structures. These elements
```

#### Chunk #65 — `chunk-6f1dd3c3-931f-49ff-bbff-04dc7e5e4980`

- **score**: 0.434
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
architecture is considerably more complex than that of the PoolFormer-S12, featuring an intricate network of dense branch connections and sophisticated fusion structures. These elements are central to the training volatility encountered with the FastSegFormer-E model.
```

#### Chunk #66 — `chunk-89ef7677-9596-4f20-9dd5-2f753b4f5f70`

- **score**: 0.425
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
Tables 1 and 2 display the segmentation performance and deployment performance of several models used in the ablation investigation, respectively. Both image enhancement and fine-tuning techniques delivered significant segmentation performance gains.The mIoU and mPA of the model with the image reconstruction branches eliminated for the FastSegFormer-E model with the PPM module are $8 3 . 0 1 \%$ and $8 9 . 9 7 \%$ ， respectively. The model parameters and computation only increase by
```

#### Chunk #67 — `chunk-5b24a267-1c29-4007-b49d-b97cbb0c6725`

- **score**: 0.416
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
$0 . 5 2 \mathrm { ~ M ~ }$ and O.03 GFLOPs once the PPM is replaced with MSP,while the mIoU and mPA are improved by $0 . 8 7 \%$ and $0 . 7 6 \%$ ,respectively. The model parameters and computation only go up by $0 . 0 1 \mathrm { ~ M ~ }$ and 0.06 GFLOPs once the image reconstruction branch is included,and mIoU and mPA go up by $4 . 6 1 \%$ and $3 . 4 3 \%$ ,respectively.The mIoU and mPA of the model with the image reconstruction branches eliminated for the FastSegFormer-P model with the PPM module were $8 4 . 2 9 \%$ and $8 9 . 9 1 \%$ ,respectively.The model parameters and computation only increase by $1 . 3 2 \mathrm { ~ M ~ }$ and 0.O7 GFLOPs once PPMis replaced with MSP, while the mIoU and mPA are improved by $0 . 6 7 \%$ and $0 . 8 9 \%$
```

#### Chunk #68 — `chunk-200c7390-4bd5-40e4-997b-65fe8d3d050f`

- **score**: 0.407
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
，respectively. The model parameters and computation only go up by $0 . 0 2 \mathrm { ~ M ~ }$ and O.O7 GFLOPs once the image reconstruction branch is included, and the mIoU and mPA go up by $3 . 6 1 \%$ and $2 . 3 5 \%$ ,respectively.The addition of the image reconstruction branch considerably improves the IoU metrics of wound scarring defects and ulcer defects with complex edge features,demonstrating how effective this branch is at enhancing the model's recognition of complicated features.
```

#### Chunk #69 — `chunk-30eaee97-44c1-4ef7-80b2-a4ca3ebcf927`

- **score**: 0.398
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
Fig.8 illustrates the changes in segmentation accuracy of the model with different weights assigned to the distillation loss.The FastSegFormer-E model achieved peak segmentation performance, with the highest accuracy,at settings $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ .Notably,the model's segmentation accuracy falls below that of the no-distillation baseline when the individual distillation losses are excessively high or low.The FastSegFormer-P model attained its peak accuracy at the settings of $\lambda _ { 1 } = 0 . 5$ ， $\lambda _ { 2 } = 5$ ,and also at $\lambda _ { 1 } = 0 . 7 5$ ， $\lambda _ { 2 } = 7 . 5$ .Contrasting with FastSegFormer-E,the distillation process yielded predominantly beneficial outcomes for this model.The results from both models
```

#### Chunk #70 — `chunk-ca3f1c16-a401-4854-bcc2-993fd94f9b72`

- **score**: 0.389
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 1 Segmentic performance of different models in the model structure ablation study. 
table_body: <table><tr><td rowspan="2">Model</td><td rowspan="2">mIoU (%)</td><td rowspan="2">mPA (%)</td><td colspan="4">IoU (%)</td></tr><tr><td>Background</td><td>Sunburn</td><td>Ulcer</td><td>Wind scarring</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB +W/PPM OD</td><td>79.84</td><td>85.12</td><td>98.93</td><td>83.19</td><td>77.28</td><td>60.34</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM ED</td><td>81.93</td><td>87.34</td><td>99.00</td><td>86.09</td><td>79.30</td><td>63.32</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† OD</td><td>82.74</td><td>88.32</td><td>99.03</td><td>87.76</td><td>79.88</td><td>65.43</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† ED</td><td>83.01</td><td>88.97</td><td>98.99</td><td>88.05</td><td>79.91</td><td>65.10</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>83.88</td><td>89.73</td><td>99.05</td><td>88.17</td><td>80.11</td><td>68.17</td></tr><tr><td>FastSegFormer-E(ours) †ED</td><td>88.49</td><td>93.16</td><td>99.35</td><td>89.29</td><td>87.40</td><td></td></tr><tr><td>FastSegFormer-P+</td><td></td><td></td><td></td><td></td><td></td><td>77.94</td></tr><tr><td>W/o IRB+W/ PPM OD</td><td>79.21</td><td>84.88</td><td>98.89</td><td>82.37</td><td>74.53</td><td></td></tr><tr><td>FastSegFormer-P +</td><td></td><td></td><td></td><td></td><td></td><td>59.89</td></tr><tr><td>W/o IRB+W/PPM ED</td><td>80.03</td><td>86.25</td><td>98.96</td><td>82.26</td><td>78.16</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>60.74</td></tr><tr><td>FastSegFormer-P + W/o IRB+W/PPM†OD</td><td>82.46</td><td>88.01</td><td>99.00</td><td>85.77</td><td>79.35</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.18</td></tr><tr><td>FastSegFormer-P + W/o IRB+ W/ PPM†ED</td><td>84.29</td><td>89.91</td><td>99.07</td><td>88.34</td><td>81.07</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.67</td></tr><tr><td>FastSegFormer-P+</td><td></td><td>90.80</td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>84.96</td><td></td><td>99.11</td><td>88.53</td><td>81.98</td><td>70.22</td></tr><tr><td>FastSegFormer-P(ours) † ED</td><td>88.57</td><td>93.15</td><td>99.35</td><td>89.34</td><td>87.50</td><td>78.09</td></tr></table>
table_footnote: w/o:without.w/:with. IRB: Image reconstruction branch. †:Backbone network was pretrained in ImageNet-1K. OD: Original Datasets.ED:Enhanced Datasets. 
```

#### Chunk #71 — `chunk-1abb8ed6-a5f1-4302-924a-6b91b61c4ce1`

- **score**: 0.381
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 2 Deployment performance of different models in the model structure ablation study. 
table_body: <table><tr><td>Model</td><td>Params(M)</td><td>GFLOPs</td><td>RTX3060 Speed(FPS)</td></tr><tr><td>FastSegFormer-E+W/o IRB+W/PPM</td><td>4.48</td><td>0.71</td><td>64</td></tr><tr><td>FastSegFormer-E +W/o IRB+W/MSP</td><td>5.00</td><td>0.74</td><td>62</td></tr><tr><td>FastSegFormer-E(ours)</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/PPM</td><td>13.53</td><td>2.56</td><td>117</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/MSP</td><td>14.85</td><td>2.63</td><td>112</td></tr><tr><td>FastSegFormer-P(ours)</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
table_footnote: w/o:without. w/: with. IRB:Image reconstruction branch. 
```

#### Chunk #72 — `chunk-8a302e8b-9a24-41b4-a71c-bd4d00e10734`

- **score**: 0.372
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
demonstrate that overly high NFD distillation losses substantially diminish accuracy,whereas the impact of excessive logits distillation losses appears to be less detrimental. This discrepancy arises because a distillation loss that is too large for intermediate feature maps can rapidly deteriorate the representational information derived from the pre-training weights.On the other hand,logits positioned at the output of the model have a relatively lesser impact in this regard.For the FastSegFormer-E model,when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5 .$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 7 5$ ,as indicated by the red broken line.For the FastSegFormer-P model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at
```

#### Chunk #73 — `chunk-03e812b7-f087-478f-903c-642002f8c97c`

- **score**: 0.363
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 5$ ,as indicated by the green broken line.In conclusion,after careful evaluation,we have selected $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ as the definitive weights for our model.
```

#### Chunk #74 — `chunk-455a7204-5abf-44ca-b299-9a961580c6e5`

- **score**: 0.354
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
The model's performance in the knowledge distillation ablation research is shown in Table 3.The suggested knowledge distillation strategy enhances the mIoU metrics on the FastSegFormer-E and FastSegFormer-P models by $0 . 7 3 \%$ and $1 . 2 8 \%$ ,respectively when the models are trained from scratch.The suggested knowledge distillation increases the mIoU metrics on the FastSegFormer-E and FastSegFormer-P models by $0 . 2 9 \%$ and $0 . 7 6 \%$
```

#### Chunk #75 — `chunk-3aeb4d09-f170-4d70-a026-c6166d8dda58`

- **score**: 0.345
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
，respectively,when the models are fine-tuned utilizing the parameters of the backbone network after ImageNet-1K pre-training.We find that multi-resolution knowledge distillation performs better than same-resolution knowledge distillation in a variety of situations.Larger resolutions retain more image detail,teacher models perform better,and more knowledge about the details is extracted.After knowledge distillation,FastSegFormer-E and FastSegFormer-P respectively reached $8 8 . 7 8 \%$ and $8 9 . 3 3 \%$ of mIoU,which is close to the mloU value of $9 0 . 5 3 \%$ of the teacher network despite the student network having a much smaller number of parameters and requiring less computation.
```

#### Chunk #76 — `chunk-8aa3f765-01a1-47f2-8dae-866a4fadf30b`

- **score**: 0.336
- **section_id**: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`
- **chunk_type**: text

**Chunk 完整文本**

```
The segmentation and inference performance of the FastSegFormer model is thoroughly compared to those of other lightweight segmentation methods in Table 4.All models were tested in the same environment using the GeForce RTX3o6O training graphics card for inference. The model we created performed the best out of all models.Our FastSegFormer-P reaches real-time segmentation speed (1o8FPS) in terms of inference speed.Despite having minimal theoretical computations,ENet and FastSegFormer-E both have lengthy actual computation times.
```

#### Chunk #77 — `chunk-1fdabff8-a729-484a-9d7b-a0c44ec6e404`

- **score**: 0.327
- **section_id**: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`
- **chunk_type**: text

**Chunk 完整文本**

```
Fig.9 displays mIoU with the inference speed of models with mloU larger than 70,and Fig.1O plots mloU with the number of parameters for models with mIoU greater than 7O,both on the navel orange dataset (test set).Different series of models are plotted using various icons,and straight lines are used to connect models that are related.As depicted in Fig. 9,models located in the upper right quadrant of the graph outperform others.The proposed FastSegFormer-E model achieves a high accuracy rate,but its inference speed is on the slow side.On the other hand,the FastSegFormer-P model offers a better solution,providing both respectable speeds and high segmentation precision.Compared to our models,alternative lightweight options may operate faster but with significantly reduced accuracy in segmentation tasks.Fig.1O indicates that optimal models are positioned in the upper left corner,signifying lower parameter counts with high performance.FastSegFormer-P, although it attains the best
```

#### Chunk #78 — `chunk-076baaa3-29ee-4906-b9f0-b9c632904db3`

- **score**: 0.319
- **section_id**: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`
- **chunk_type**: text

**Chunk 完整文本**

```
segmentation tasks.Fig.1O indicates that optimal models are positioned in the upper left corner,signifying lower parameter counts with high performance.FastSegFormer-P, although it attains the best segmentation performance,is hampered by its substantial parameter size.In contrast, FastSegFormer-E demonstrates high accuracy while being more memory-efficient, a significant advantage in memory-constrained environments. ENet, despite having the smallest number of parameters,still delivers robust segmentation performance,also making it an impressively efficient choice in this scenario.In conclusion,the proposed FastSegFormer-E model achieves excellent segmentation accuracy with memory constraints,and the FastSegFormer-P model achieves in the highest segmentation accuracy while ensuring detection speed.
```

#### Chunk #79 — `chunk-a4ffde60-9c49-4523-8b81-42537b6db5f2`

- **score**: 0.310
- **section_id**: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 3 Knowledge distillation and fine-tuning for ablation study. 
table_body: <table><tr><td>Model</td><td>mIoU (%)</td><td>mPA (%)</td><td>mPrecison (%)</td><td>Params(M)</td><td>GFLOPs</td></tr><tr><td>Swin-T-Att-UNet (T-224) †</td><td>89.73</td><td>94.08</td><td>94.85</td><td>49.21</td><td>14.52</td></tr><tr><td>Swin-T-Att-UNet (T-512) †</td><td>90.53</td><td>94.65</td><td>95.20</td><td>49.21</td><td>77.80</td></tr><tr><td>FastSegFormer-E</td><td>86.51</td><td>91.63</td><td>93.53</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD</td><td>87.24</td><td>92.20</td><td>93.82</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2</td><td>87.38</td><td>92.35</td><td>93.83</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E†</td><td>88.49</td><td>93.16</td><td>94.32</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD†</td><td>88.68</td><td>92.97</td><td>94.75</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2†</td><td>88.78</td><td>93.33</td><td>94.48</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-P</td><td>84.15</td><td>89.44</td><td>92.84</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/ KD</td><td>84.77</td><td>90.12</td><td>92.91</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/KD2</td><td>85.43</td><td>90.64</td><td>93.20</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P†</td><td>88.57</td><td>93.15</td><td>94.42</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD†</td><td>88.94</td><td>93.25</td><td>94.77</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD2†</td><td>89.33</td><td>93.78</td><td>94.68</td><td>14.87</td><td>2.70</td></tr></table>
table_footnote: T-224:Teacher model with $2 2 4 \times 2 2 4$ input size. T-512: Teacher model with $5 1 2 \times 5 1 2$ input size. w/:with. $\mathrm { K D } _ { 1 }$ :Knowledge distillation from T-224. $\mathrm { K D } _ { 2 }$ ：Knowledge distillation from T-512. $^ \dagger$ ：Backbone network was pretrained in ImageNet-1K. 
```

#### Chunk #80 — `chunk-e4a61223-ada6-4d20-be1d-9fdaa685d250`

- **score**: 0.301
- **section_id**: `section-b5f49764-e6b6-4ea2-b7af-ca79fdf7a613`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 4 Performance comparison between FastSegFormer and other lightweight models. 
table_body: <table><tr><td>Model</td><td>Backbone</td><td>mIoU (%)</td><td>Params(M)</td><td>GFLOPs</td><td>FPS (RTX 3060)</td></tr><tr><td>FANet-18 †</td><td>ResNet-18</td><td>67.41</td><td>13.65</td><td>1.16</td><td>168</td></tr><tr><td>FANet-34†</td><td>ResNet-34</td><td>69.22</td><td>23.75</td><td>1.64</td><td>120</td></tr><tr><td>PIDNet-S Seg†</td><td>PIDNet-S</td><td>75.09</td><td>7.62</td><td>1.15</td><td>84</td></tr><tr><td>PIDNet-M Seg †</td><td>PIDNet-M</td><td>75.97</td><td>28.54</td><td>4.30</td><td>82</td></tr><tr><td>PIDNet-L Seg †</td><td>PIDNet-L</td><td>75.13</td><td>36.93</td><td>6.63</td><td>69</td></tr><tr><td>SwiftNet †</td><td>ResNet-18</td><td>78.69</td><td>11.79</td><td>2.49</td><td>242</td></tr><tr><td>Fast-SCNN</td><td>~</td><td>79.15</td><td>1.14</td><td>0.17</td><td>189</td></tr><tr><td>BiSeNet †</td><td>ResNet-18</td><td>82.37</td><td>13.23</td><td>2.84</td><td>193</td></tr><tr><td>ENet</td><td>~</td><td>85.63</td><td>0.36</td><td>0.46</td><td>71</td></tr><tr><td>FastSegFormer-E(ours) †</td><td>EfficientFormerV2-S0</td><td>88.78</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P(ours) †</td><td>PoolFormer-S12</td><td>89.33</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
table_footnote: +: Backbone network pretrained in ImageNet-1K. 
```

#### Chunk #81 — `chunk-f53db249-7d0e-462b-be93-14d2baa2c495`

- **score**: 0.292
- **section_id**: `section-1f7ff486-5798-4a27-867d-e2e3f8ffbb55`
- **chunk_type**: text

**Chunk 完整文本**

```
Results of the partial model for segmenting partial navel orange picture defects on the test set are shown in Fig.11.As seen in Fig.11, the FastSegFormer model can successfully segment defects in the challenging scenario of a simulated picking line scene.The segmentation outcome is quite similar to the label and recovers some label information. The results of Image I-III show that, in comparison to other models,the FastSegFormer model can differentiate the margins of small defects,more precisely segment wind scarring defects with complicated geometries,and distinguish similar defects.FastSegFormer still distinguishes minor defects better in Figure IV's blurred image.Figure V shows that all models have a similar capacity for segmenting defects for larger targets.
```

#### Chunk #82 — `chunk-658785d8-63d8-483c-b82c-2250a2c0fc27`

- **score**: 0.283
- **section_id**: `section-cbae53f4-03e8-4cd1-8bdb-c7f9732fe679`
- **chunk_type**: text

**Chunk 完整文本**

```
To simulate the environment of an industrial picking line,which is expensive to deploy algorithms in,we used an edge computing device similar to it. Through Jiangxi Reemoon Technology Company, we learned that NVIDIA's Jetson platform is used for fruit industrial pipeline defect detection while using TensorRT hardware acceleration and DeepStream video stream processing framework.We used the platform's entry-level device,the Jetson Nano (4G),to deploy the navel orange defect detection system and tested the speed of detection,and we also deployed the system on the device used for training as a comparison.
```

#### Chunk #83 — `chunk-decd44e8-4245-4ae7-a81c-30bb5121037d`

- **score**: 0.274
- **section_id**: `section-30c66884-4443-4260-9f2f-e27680b7f3b5`
- **chunk_type**: text

**Chunk 完整文本**

```
The system is deployed in the Ubuntu 18.04 environment using CUDA10.2, TensorRT 8.2,and DeepStream 6.0.1. Jetson Nano (4G) is equipped with an NVIDIA Maxwell GPU and ARM Cortex-A57MPCore processor with 4 GB of shared CPU and GPU memory.We converted the trained model files into ONNX files usingPython scripts and built TensorRT model serialization files for accelerated inference based on the Jetson Nano's hardware.The system additionally used the DeepStream video processing framework, which is paired with TensorRT technology and can only be used on NVIDIA's Jetson platform.As a comparison, the system is also deployed on the PC used for training the model,and the configuration information is given in Section 2.6.2.
```

#### Chunk #84 — `chunk-165ae551-0c25-451b-813d-69620bdef780`

- **score**: 0.265
- **section_id**: `section-30c66884-4443-4260-9f2f-e27680b7f3b5`
- **chunk_type**: image
- **image_file**: `af4b906f688d0ddf56aaeb35fd3838274e4d43301ed2419aad903cd61c376ce7.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/af4b906f688d0ddf56aaeb35fd3838274e4d43301ed2419aad903cd61c376ce7.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #85 — `chunk-9828c913-fb68-4235-96fb-7636880fde8c`

- **score**: 0.257
- **section_id**: `section-30c66884-4443-4260-9f2f-e27680b7f3b5`
- **chunk_type**: image
- **image_file**: `fe8f4c4aff79790c8cdad1f2ff0b8927ffa50fbd3b872545246e2b444ab56e01.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/fe8f4c4aff79790c8cdad1f2ff0b8927ffa50fbd3b872545246e2b444ab56e01.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #86 — `chunk-0d64a7aa-c86f-4fff-a513-5107fb8f09aa`

- **score**: 0.248
- **section_id**: `section-95ba5683-8c9f-4209-9f58-df611b13b2b7`
- **chunk_type**: text

**Chunk 完整文本**

```
The detection latency of a single image determines the detection speed of the system，which includes pre-processing latency,model inference latency,and post-processing latency. Pre-processing includes image size conversion，image type conversion
```

#### Chunk #87 — `chunk-a0b67b58-1682-4352-b375-bb5efaffd1c1`

- **score**: 0.239
- **section_id**: `section-95ba5683-8c9f-4209-9f58-df611b13b2b7`
- **chunk_type**: text

**Chunk 完整文本**

```
，etc. Post-processing time delay includes marking defect location,image size conversion, image stitching,etc.Therefore,the actual detection speed of the system is much smaller than the inference speed alone.Table 5 shows the detection speed of the system under different platforms. Using Deep-Stream,TensorRT,and semi-precision quantization techniques on a Jetson Nano device,our algorithmic detection system achieves nearly half the detection speed on a PC using only 1/27 of the PC computing power. The Jetson platform's uniform deployment framework has greatly amplified scalability, harnessing the robust capabilities of advanced Jetson devices to deliver remarkable detection rates.Within the commercial sector, the Jetson lineup,particularly the acclaimed Jetson Xavier NX,is the go-to for its extraordinary computational power.Furthermore,this highlights the adaptability and eficiency of the proposed algorithm,capable of facilitating real-time detection across diverse assembly line sorting
```

#### Chunk #88 — `chunk-8561e242-2c54-4fe6-8b1f-110948c50dc3`

- **score**: 0.230
- **section_id**: `section-95ba5683-8c9f-4209-9f58-df611b13b2b7`
- **chunk_type**: text

**Chunk 完整文本**

```
extraordinary computational power.Furthermore,this highlights the adaptability and eficiency of the proposed algorithm,capable of facilitating real-time detection across diverse assembly line sorting operations.
```

#### Chunk #89 — `chunk-6e95d827-3a8c-44b2-90d2-7ec1b1cf2709`

- **score**: 0.221
- **section_id**: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`
- **chunk_type**: text

**Chunk 完整文本**

```
Table 6 compares our work with some already existing research work on fruit defect segmentation.Please take note that we retested portions of the work's speed using the RTX3o6O graphics card,and the details are consistent with the original paper.While the classification accuracy of traditional picture segmentation algorithms is quite high, the segmentation accuracy is low and the processing time delay is considerable (Rong et al., 2017a,b). Sun et al. (2020) only takes into account the segmentation performance of the model, and it is challenging to use the study's findings for extensive navel orange defect identification. To balance segmentation performance and inference speed, Liang et al.(2022) employs a lightweight detection network to assist with the lightweight segmentation network. Compared to conventional segmentation methods,the current study's scene application versatility is better,and its segmentation capability is more powerful and quick. It
```

#### Chunk #90 — `chunk-57c8e00e-59ed-4c2f-9954-111018af1e81`

- **score**: 0.212
- **section_id**: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`
- **chunk_type**: image
- **image_file**: `f4e5339defbc6985d8a6f9d7203c860147c7e6cf527be37fb22c5021586b36fd.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/f4e5339defbc6985d8a6f9d7203c860147c7e6cf527be37fb22c5021586b36fd.jpg`

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #91 — `chunk-84f952f3-80ea-40c3-8de9-eef9d2a7f27c`

- **score**: 0.204
- **section_id**: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 5 Comparison of the detection speed of Jetson Nano and RTX3060. 
table_body: <table><tr><td>Device</td><td>Video input</td><td>Inference input</td><td>Acceleration</td><td>Data type</td><td>Compute (TFLOPs)</td><td>Speed (FPS)</td></tr><tr><td>RTX3060</td><td>1920 × 1080</td><td>224× 224</td><td>~</td><td>FP32</td><td>12.74</td><td>33</td></tr><tr><td>RTX3060</td><td>1920×1080</td><td>224× 224</td><td>Multithreading</td><td>FP32</td><td>12.74</td><td>47</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>~</td><td>FP16</td><td>0.47</td><td>8</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>TensorRT</td><td>FP16</td><td>0.47</td><td>12</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224×224</td><td>DeepStream</td><td>FP16</td><td>0.47</td><td>20</td></tr></table>
table_footnote: FP32:Inference with single-precision floating-point number. FP16:Inference with half-precision floating-point number. $\sim$ Inference with ONNXRuntime and do not use accelerations. Note:DeepStream includes TensorRT acceleration. 
```

#### Chunk #92 — `chunk-2412fdd9-578f-4f36-9c18-1af9b025fb5e`

- **score**: 0.195
- **section_id**: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`
- **chunk_type**: table

**Chunk 完整文本**

```
table_caption: Table 6 Performance of FastSegFormer and related works. 
table_body: <table><tr><td rowspan="2">Work</td><td rowspan="2">Task</td><td rowspan="2">Detailed description</td><td colspan="3">Metrics</td></tr><tr><td>Accuracy (%)</td><td>mIoU (%)</td><td>Inference time (ms)</td></tr><tr><td>Rong et al. (2017a)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using means of sliding window local segmentation algorithm.</td><td>97</td><td>~</td><td>~</td></tr><tr><td>Rong et al. (2017b)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using fast adaptive lightness correction algorithm.</td><td>95.7</td><td>~</td><td>30</td></tr><tr><td rowspan="3">Sun et al. (2020)</td><td rowspan="3">Semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3">~</td><td rowspan="3">70.38</td><td rowspan="3">~</td></tr><tr><td>using FA-Net Input: 288 × 288</td></tr><tr><td>Number of pixel classification categories: 5</td></tr><tr><td rowspan="3">Liang et al. (2022)</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on apples using</td><td rowspan="3"></td><td rowspan="3">80.46</td><td rowspan="3">16.99(RTX3060)*</td></tr><tr><td>BiSeNetV2 with pruned YOLOv4 assisted.</td></tr><tr><td>Input: 416 × 416 Number of pixel classification categories: 3</td></tr><tr><td rowspan="3">Current work</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3"></td><td rowspan="3">89.33</td><td rowspan="3">9.26(RTX3060)</td></tr><tr><td>using FastSegFormer-P.</td></tr><tr><td>Input: 224× 224 Number of pixel classification categories: 4</td></tr></table>
table_footnote: \~:Not applicable or not mentioned in the original paper. \*:Results of testing on our equipment according to the original details. 
```

#### Chunk #93 — `chunk-f4c4ca45-3b5c-4971-9516-eaf4f93944a5`

- **score**: 0.186
- **section_id**: `section-743bdc66-27bb-4135-a3cb-f9f34f4e320c`
- **chunk_type**: text

**Chunk 完整文本**

```
provides advantages in terms of the combination of accuracy and speed compared to other segmentation models.
```

#### Chunk #94 — `chunk-2a3713c5-461f-486f-994c-6600e0e959f7`

- **score**: 0.177
- **section_id**: `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`
- **chunk_type**: text

**Chunk 完整文本**

```
Real-time defect identification is made possible by the FastSeg-Former model's precise defect detection capabilities and a good balance of accuracy and speed.The model is highly generalizable and has good adaptability when mimicking the intricate circumstances of a mock sorting line.Our model was able to achieve 1o8 frames/s at the mid-end GPU RTX306O with the present input resolution.The bloated backbone network is the reason why,as the image resolution gradually rises,the calculation of the model increases.We will think about either constructing a more effective backbone network or trimming the backbone network in terms of channels and depth to accommodate high-resolution inputs. This will speed up inference and save training resources by eliminating the dependence on pre-training resources of the ImageNet-1K dataset.
```

#### Chunk #95 — `chunk-86048396-0f81-4400-8fd3-de113a09546d`

- **score**: 0.168
- **section_id**: `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`
- **chunk_type**: text

**Chunk 完整文本**

```
The advantage of a defect detection session taking place after harvesting is that it allows for quick identification in big volumes.However
```

#### Chunk #96 — `chunk-6acc745c-f72f-4d06-b03c-1b0d39d499f2`

- **score**: 0.159
- **section_id**: `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`
- **chunk_type**: text

**Chunk 完整文本**

```
，when intelligent picking robots advance,the defect detection and picking segments will be merged.Future research will focus on segmenting and categorizing whole fruits with defects and whole fruits without defects in the orchard scene map,which is currently quite challenging. However,when new deep-learning training techniques, such as prompt engineering,are suggested, this challenge will gradually be addressed.The SAM model presents two innovative strategies for enhancing our approach to dataset annotation and model training (Kirillov et al., 2023). The first strategy focuses on streamlining the segmentation dataset annotation process through point cueing techniques,which are designed to guarantee precision and richness in the dataset details.The second strategy involves the integration of textual cues during the training process,enabling the model to dynamically adjust to the fluctuating lighting and climatic conditions encountered within orchard environments.These textual cues serve
```

#### Chunk #97 — `chunk-f9348135-3a5d-4cec-8a9a-755e7213abd1`

- **score**: 0.150
- **section_id**: `section-4531cda2-2634-4281-b3dd-fa3ba062ad4e`
- **chunk_type**: text

**Chunk 完整文本**

```
textual cues during the training process,enabling the model to dynamically adjust to the fluctuating lighting and climatic conditions encountered within orchard environments.These textual cues serve as a guide for the model, fostering an adaptable classification system responsive to a spectrum of environmental inputs.
```

#### Chunk #98 — `chunk-9c81fff4-a060-4589-85b6-782a56b26f68`

- **score**: 0.142
- **section_id**: `section-682d3ee7-4ea5-41f2-ba67-367372d63649`
- **chunk_type**: text

**Chunk 完整文本**

```
In this paper
```

#### Chunk #99 — `chunk-65a09c5e-bf58-446b-a2bd-192ce11bfad9`

- **score**: 0.133
- **section_id**: `section-682d3ee7-4ea5-41f2-ba67-367372d63649`
- **chunk_type**: text

**Chunk 完整文本**

```
，we developed two segmentation models called FastSegFormer-E and FastSegFormer-P to quickly identify defects in big batches of navel oranges.To rebuild image detail for the deep network,we created the MSP module and added a semi-resolution image reconstruction branch following feature fusion.Our models are effective in identifying lesser defects and precisely segmenting complex edge defects in real-world complex settings.The segmentation accuracy of the model was further enhanced by the suggested multi-resolution knowledge distillation strategy without increasing model size and inference time.The proposed FastSegFormer-E achieves superior defect detection accuracy while maintaining low memory consumption, while the proposed FastSegFormer-P achieves the highest defect detection accuracy with high inference speed.The FastSegFormer-P model achieves a detection speed of 2O fps on a very low computing power device under the Jetson platform, suggesting that deploying the algorithm is very
```

#### Chunk #100 — `chunk-25a25e27-70d8-463a-99ce-0105cf8ce6e8`

- **score**: 0.124
- **section_id**: `section-682d3ee7-4ea5-41f2-ba67-367372d63649`
- **chunk_type**: text

**Chunk 完整文本**

```
high inference speed.The FastSegFormer-P model achieves a detection speed of 2O fps on a very low computing power device under the Jetson platform, suggesting that deploying the algorithm is very easy to achieve real-time detection.The proposed algorithm effectively overcomes the limitations of current commonly used methods in meeting the demands of precise sorting.Additionally,it successfully addresses the crucial requirement of real-time detection,an aspect where many existing segmentation algorithms for fruit defect detection fall short.Incorporating a smaller and faster backbone into the proposed network will enhance its ability to handle image inputs of various resolutions. Defect detection will be performed at the harvesting stage in the future,where the algorithm's adaptation to partial leaf occlusion becomes crucial.
```

#### Chunk #101 — `chunk-620ccb87-7305-43df-94e7-dffb95cff89e`

- **score**: 0.115
- **section_id**: `section-e75b119c-edbc-401a-a947-7876b775ef42`
- **chunk_type**: text

**Chunk 完整文本**

```
Xiongjiang Cai: Writing-review& editing,Writing-original draft, Visualization，Validation,Software,Project administration,Methodology,Investigation,Formal analysis,Data curation,Conceptualization. Yun Zhu: Supervision, Resources, Project administration, Funding acquisition,Formal analysis,Data curation.Shuwen Liu: Supervision,Software,Resources,Project administration, Investigation,Data curation.Zhiyue Yu: Supervision,Software,Project administration, Data curation. Youyun Xu: Resources, Project administration, Funding acquisition, Conceptualization.
```

#### Chunk #102 — `chunk-be3ac238-0379-4809-b5d4-edd293aa9bf2`

- **score**: 0.106
- **section_id**: `section-e4a68ef4-1e13-4816-938f-a010ffa10296`
- **chunk_type**: text

**Chunk 完整文本**

```
The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.
```

#### Chunk #103 — `chunk-86e1eb7a-98b5-4129-899b-2173604f01bd`

- **score**: 0.097
- **section_id**: `section-fecf5047-8c16-4f3b-9026-307bf14d887d`
- **chunk_type**: text

**Chunk 完整文本**

```
The data and code can be available in https://github.com/caix iongjiang/FastSegFormer. Code on edge computing device deployment and detection systems on PCs is available in https://github.com/ caixiongjiang/FastSegFormer-pyqt.
```

#### Chunk #104 — `chunk-9fe0fec3-2dc2-485c-8ec5-1ae81d2a45f3`

- **score**: 0.088
- **section_id**: `section-4f9fddec-e769-4684-867a-81dc7f7c4ae5`
- **chunk_type**: text

**Chunk 完整文本**

```
This work was financially supported by the Key Research and Development Programs of Jiangxi Province (No.006124253059 and No. 006124252054).
```

#### Chunk #105 — `chunk-9acaa6da-f180-4393-9bbc-9be80804f560`

- **score**: 0.080
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Allwood，J.W.，Gibon，Y.，Osorio，S.，Araujo，W.L.，Valarino，J.G.，Pétriacq，P., Moing, A., 2021. Developmental metabolomics to decipher and improve fleshy fruit quality. In: Advances in Botanical Research. Vol. 98. Elsevier, pp. 3-34.
Azizah,L.M.， Umayah，S.F.，Riyadi， S.， Damarjati， C.， Utama, N.A.， 2017.Deep learning implementation using convolutional neural network in mangosteen surface defect detection. In: 2017 7th IEEE International Conference on Control System, Computing and Engineering. ICCSCE, IEEE, pp. 242-246.
De Luna，R.G.，Dadios，E.P.，Bandala,A.A.，Vicerra，R.R.P.，2019. Tomato fruit image dataset for deep transfer learning-based defect detection. In: 2O19 IEEE International Conference on Cybernetics and Intelligent Systems (CIS) and IEEE Conference on Robotics, Automation and Mechatronics (RAM). IEEE, pp. 356-361.
```

#### Chunk #106 — `chunk-34e0e41b-a532-49e7-99ed-dd20513618ef`

- **score**: 0.071
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Dosovitskiy,A.,Beyer,L.,Kolesnikov,A.,Weissenborn,D., Zhai, X., Unterthiner,T., Dehghani,M.,Minderer,M.,Heigold,G.,Gelly,S.,et al.,2020.An image is worth 16xl6 words: Transformers for image recognition at scale.arXiv preprint arXiv:2010.11929.
Fan, S., Liang, X.,Huang,W., Zhang, V.J., Pang, Q., He, X.,Li, L., Zhang, C., 2022. Real-time defects detection for apple sorting using NIR cameras with pruning-based YOLOV4 network. Comput. Electron. Agric. 193, 106715.
Heo,B.，Kim,J.,Yun, S.，Park，H.，Kwak，N.,Choi,J.Y.，2019. A comprehensive overhaul of feature distillation. In: Proceedings of the IEEE/CVF International Conference on Computer Vision. pp. 1921-1930.
Hinton,G.,Vinyals,O.,Dean,J.,2015.Distilling the knowledge in a neural network. arXiv preprint arXiv:1503.02531.
Holder, C.J., Shafique,M.,2022. On efficient real-time semantic segmentation: a survey. arXiv preprint arXiv:2206.08605.
```

#### Chunk #107 — `chunk-9174528d-1d34-4e81-b65d-6ba460010595`

- **score**: 0.062
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Holder, C.J., Shafique,M.,2022. On efficient real-time semantic segmentation: a survey. arXiv preprint arXiv:2206.08605.
Hou,J., Liang,L.,Wang, Y.， 2O2o.Volatile composition changes in navel orange at different growth stages by HS-SPME-GC-MS. Food Res.Int.136,109333.
Ismail,N., Malik, O.A., 2022. Real-time visual inspection system for grading fruits sing computer vision and deep learning techniques. Inf. Process. Agricult. 9 (1), 24-37.
Kirillov,A.，Mintun,E.，Ravi,N.，Mao,H.，Rolland,C.，Gustafson,L.，Xiao,T., Whitehead,S.,Berg,A.C.,Lo,W.-Y.,etal.,2023.Segment anything.arXiv preprint arXiv:2304.02643.
Li,Y.,Hu,J.,Wen,Y.,Evangelidis,G.,Salahi,K.,Wang,Y.,Tulyakov,S.,Ren,J., 2022.Rethinking vision transformers for MobileNet size and speed.arXiv preprint arXiv:2212.08059.
Liang, X., Jia, X.,Huang,W., He, X.,Li,L.,Fan, S., Li, J., Zhao, C., Zhang, C., 2022. Real-time grading of defect apples using semantic segmentation combination with a pruned YOLO V4 network. Foods 11 (19), 3150.
```

#### Chunk #108 — `chunk-3ddb00ee-e92e-4f6c-9da9-60a314dc2c08`

- **score**: 0.053
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Liu,Y.，Chen，K.,Liu,C.,Qin，Z., Luo，Z.，Wang,J.，2019. Structured knowledge distillation for semantic segmentation. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp. 2604-2613.
Liu, Z.,Lin, Y.， Cao, Y.， Hu, H,Wei, Y.， Zhang,Z., Lin,S.,Guo, B.， 2021. Swin transformer: Hierarchical vision transformer using shifted windows. In: Proceedings of the IEEE/CVF International Conference on Computer Vision. pp.10012-10022.
Liu,T.，Yang，X.，Chen,C.，2022．Normalized feature distillation for semantic segmentation. arXiv preprint arXiv:2207.05256.
Nithya,R., Santhi, B.， Manikandan,R., Rahimi, M., Gandomi, A.H., 2022. Computer vision system for mango fruit defect detection using deep convolutional neural network. Foods 11 (21), 3483.
Oktay,O.,Schlemper,J.,Folgoc,L.L.,Lee,M.,Heinrich,M.,Misawa,K.,Mori,K., McDonagh,S.ammerla,N.Y.,ainz,B.tal.8.Atentionu-netLearing where to look for the pancreas.arXiv preprint arXiv:1804.03999.
```

#### Chunk #109 — `chunk-bc2e285b-baae-4561-9e89-231b85f2405d`

- **score**: 0.044
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Oktay,O.,Schlemper,J.,Folgoc,L.L.,Lee,M.,Heinrich,M.,Misawa,K.,Mori,K., McDonagh,S.ammerla,N.Y.,ainz,B.tal.8.Atentionu-netLearing where to look for the pancreas.arXiv preprint arXiv:1804.03999.
Orsic,M., Kreso,L,Bevandic,P. Segvic,S., 2019.In defense of pre-trained imagenet architectures for real-time semantic segmentation of road-driving images. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp.12607-12616.
Paszke,A., Chaurasia,A., Kim, S.,Culurciello,E.,2Ol6. Enet: A deep neural network architecture for real-time semantic segmentation.arXiv preprint arXiv:l6o6.02147.
Poudel,R.P., Liwicki,S., Cipolla,R., 2019.Fast-SCNN: Fast semantic segmentation network. arXiv preprint arXiv:1902.04502.
Rong,D.，Rao, X.， Ying, Y.， 2O17a. Computer vision detection of surface defect on oranges by means of a sliding comparison window local segmentation algorithm. Comput. Electron. Agric.137, 59-68.
```

#### Chunk #110 — `chunk-8a61a540-f514-419c-a256-27a416e691f5`

- **score**: 0.035
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Rong,D.，Rao, X.， Ying, Y.， 2O17a. Computer vision detection of surface defect on oranges by means of a sliding comparison window local segmentation algorithm. Comput. Electron. Agric.137, 59-68.
Rong, D., Ying, Y.,Rao, X., 2017b. Embedded vision detection of defective orange by fast adaptive lightness correction algorithm. Comput. Electron. Agric.138, 48-59.
Ronneberger, O., Fischer, P., Brox, T., 2015. U-net: Convolutional networks for biomedical image segmentation. In: Medical Image Computing and Computer-Assisted Intervention-MICCAI 2015:18th International Conference,Munich， Germany, October 5-9,2015, Proceedings,Part I Vol.18.Springer, pp.234-241.
Roy, K., Chaudhuri, S.S., Pramanik, S., 2021. Deep learning based real-time industrial framework for roten and fresh fruit detection using semantic segmentation. Microsyst. Technol. 27, 3365-3375.
```

#### Chunk #111 — `chunk-0abe067f-c508-49f7-8466-de6fd41e2c2d`

- **score**: 0.027
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Roy, K., Chaudhuri, S.S., Pramanik, S., 2021. Deep learning based real-time industrial framework for roten and fresh fruit detection using semantic segmentation. Microsyst. Technol. 27, 3365-3375.
Sandler,M.， Howard,A., Zhu， M.， Zhmoginov,A., Chen, L.-C.，2018.Mobilenetv2: Inverted residuals and linear bottlenecks.In: Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. pp. 4510-4520.
Sifre,L.，Mallat, S.,2o14.Rigid-motion scattering for texture classification.arXiv preprint arXiv:1403.1687.
Soltani Firouz, M., Sardari, H.,2022.Defect detection in fruit and vegetables by using machine vision systems and image processing. Food Eng. Rev. 14 (3), 353-379.
Sun,X.，Li,G.，Xu，S.，202O．Fastidious attention network for navel orange segmentation.arXiv preprint arXiv:2003.11734.
Tripathi, M.K., Maktedar, D.D., 2020.A role of computer vision in fruits and vegetables among various horticulture products of agriculture fields: A survey. Inf. Process. Agricult. 7 (2), 183-203.
```

#### Chunk #112 — `chunk-5da1c352-7766-4d36-b048-39b51d22f7de`

- **score**: 0.018
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Tripathi, M.K., Maktedar, D.D., 2020.A role of computer vision in fruits and vegetables among various horticulture products of agriculture fields: A survey. Inf. Process. Agricult. 7 (2), 183-203.
Wang,H., Cao, P.,Wang, J., Zaiane, O.R., 2022. Uctransnet: rethinking the skip connections in u-net from a channel-wise perspective with transformer. In: Proceedings of the AAAI Conference on Artificial Intelligence. Vol. 36.No.3. pp. 2441-2449.
Wang，H.，Mou, Q.，Yue,Y.， Zhao,H.,2020.Research on detection technology of various fruit disease spots based on mask R-CNN. In: 2O2O IEEE International Conference on Mechatronics and Automation. ICMA, IEEE, pp.1083-1087.
Xiang，Z.，Chen，X.,Qian,C.，He,K.，Xiao，X.，2020.Determination of volatile flavors in fresh navel orange by multidimensional gas chromatography quadrupole time-of-flight mass spectrometry. Anal. Lett. 53 (4), 614-626.
```

#### Chunk #113 — `chunk-24f1202d-65fe-4ebd-83c7-62f90ff19651`

- **score**: 0.009
- **section_id**: `section-7fec891d-4040-4f16-b87d-0d71f371f80c`
- **chunk_type**: text

**Chunk 完整文本**

```
Yao,J., Qi,J., Zhang,J.,Shao,H., Yang,J.,Li, X.,2021. A real-time detection algrithm for Kiwifruit defects based on YOLOv5. Electronics 10 (14), 1711.
Yu,W.,Luo,M., Zhou, P., Si, C., Zhou, Y.,Wang, X., Feng, J.,Yan, S., 2022. Metaformer is actually what you need for vision. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp. 10819-10829.
Yu,C.，Wang，J.，Peng，C.，Gao，C.，Yu，G.，Sang，N.，2018.Bisenet: Bilateral segmentation network for real-time semantic segmentation. In: Proceedings of the European Conference on Computer Vision. ECCV, pp.325-341.
Zhao,H., Shi, J., Qi, X.,Wang, X., Jia, J., 2017. Pyramid scene parsing network. In: Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. pp. 2881-2890.
```

### 2.3 Document → Element（按页码排序）

- **返回数量**: 131
- **耗时**: 26.1ms

**Element 类型分布**: equation: 7, image: 11, table: 6, text: 107

#### Element #1 — `element-72827224-142b-4d12-a3b7-356173dec71f`

- **type**: text
- **page_index**: 0
- **element_index**: 0

**文本内容**

```
Original papers 
```

#### Element #2 — `element-b5b9789e-f52e-4620-8fc0-b2bc19e8f0fb`

- **type**: text
- **page_index**: 0
- **element_index**: 1

**文本内容**

```
FastSegFormer: A knowledge distillation-based method for real-time semantic segmentation of surface defects in navel oranges 
```

#### Element #3 — `element-d1c005e1-012f-4a66-8598-98d5d0391829`

- **type**: text
- **page_index**: 0
- **element_index**: 2

**文本内容**

```
Xiongjiang Caia,b, Yun Zhua,b,\*, Shuwen Liuab, Zhiyue $\mathrm { Y u ^ { a , b } }$ , Youyun Xu c 
```

#### Element #4 — `element-6280d121-c1d0-42c7-bac7-dcf5f5857ac9`

- **type**: text
- **page_index**: 0
- **element_index**: 3

**文本内容**

```
aSchool of Physicsand Electronic Information, Gannan Normal University,Ganzhou,341ooo,China   
b National Navel Orange Enginering Research Center,China   
NationdlEgctdofeocs 
```

#### Element #5 — `element-84492d78-8744-4422-8468-9bb509cbba0a`

- **type**: text
- **page_index**: 0
- **element_index**: 4

**文本内容**

```
ARTICLEINFO 
```

#### Element #6 — `element-26cb6a3b-9e88-4d0c-8cc4-429a99ff7802`

- **type**: text
- **page_index**: 0
- **element_index**: 5

**文本内容**

```
ABSTRACT 
```

#### Element #7 — `element-fe37ed3f-a257-4810-bfe6-01b28857ed51`

- **type**: text
- **page_index**: 0
- **element_index**: 6

**文本内容**

```
Dataset link: https://github.com/caixiongjiang /FastSegFormer, https://github.com/caixiongji ang/FastSegFormer-pyqt 
```

#### Element #8 — `element-b691228b-df32-4877-993a-92ee1f1e62a5`

- **type**: text
- **page_index**: 0
- **element_index**: 7

**文本内容**

```
Keywords:   
Semantic segmentation   
FastSegFomer   
Lightweight model   
Navel orange   
Defect detection 
```

#### Element #9 — `element-11e3b616-30bf-483e-a861-65848802c64d`

- **type**: text
- **page_index**: 0
- **element_index**: 8

**文本内容**

```
Navel oranges are valued citrus fruits with a strong market presence,and detecting defects is crucial in their sorting due to common diseases and abnormalities during growth and transport.Deep learning,particularly semantic segmentation,is revolutionizing the fruit sorting industry by overcoming the limitations of traditional defect detection and enhancing the accuracy of clasifying complex defects in navel oranges.The FastSegFormer network,enabling real-time fruit defect detection,addresss this challnge with our introduced Multi-scale Pyramid (MSP)module for its architecture and a semi-resolution reconstruction branch post-feature fusion. We suggested a multi-resolution knowledge distillation strategy to further increase the network's segmentation accuracy.We developed a navel orange defectsegmentationdataset,trained,and evaluated our FastSegFormer-E model, designed for memory-constrained devices.It outperforms ENet by $3 . 1 5 \%$ ,achievinga mIoU of $8 8 . 7 8 \%$ on the test set.The FastSegFormer-P model,tailored for high-speed detection,was tested on the mid-range RTX3060 graphics card, surpassing ENet by $3 . 7 \%$ with a mIoU of $8 9 . 3 3 \%$ and reaching 108 frames/s. The results demonstrate that the FastSegFormer-E model atains enhanced detection accuracy with reduced memory usage,whereas the FastSegFormer-P model stands out by striking an optimal balance between top-tierdetection accuracy and rapid processing speed.Deploying the algorithm system on the same platform as pipeline sorting, 20 frame/s was achieved ona Jetson Nano with very low computational power.The model significantly improves the detection of subtle and intricate edge defects,achieving real-time speeds. Our proposed algorithm enhances thefineness offruit sorting,resolves the limitation of existing algorithms that apply to a narrow range of fruit sorting scenarios,and provides an efficient and accurate solution for large-scale navel orange defect detection. 
```

#### Element #10 — `element-b01ed00f-4668-47de-8a9c-03fab1524ffe`

- **type**: text
- **page_index**: 0
- **element_index**: 9

**文本内容**

```
1.Introduction 
```

#### Element #11 — `element-77a56b28-cf82-4f0b-b6db-6e196b8f6df6`

- **type**: text
- **page_index**: 0
- **element_index**: 10

**文本内容**

```
Grading fruits and vegetables by size,weight,shape,color,and maturity is essential for quality sorting,differentiating product grades, setting prices,and adding value for consumers (Allwood et al., 2021). Efficient fruit quality assessment and sorting ensure consumer satisfaction,reduce food waste,and streamline marketing for these fresh, tasty products.Navel oranges,identifiable by their distinct navel,are sweet, juicy,and rich in fiber and vitamin C (Hou et al., 2O2O; Xiang et al., 2020).Production of navel oranges includes sorting,which is moving from conventional machine learning to deep learning.Fruit sorting has gone from being mechanically operated to being automated thanks to the creation and marketing of the traditional vision system (Tripathi and Maktedar, 2O2O).With heightened fruit quality standards, better living conditions,and increased expectations,modern visual sorting systems are now honed for precise sorting. 
```

#### Element #12 — `element-2d3769ae-2d71-4a2b-b2e9-55dcd26d6d29`

- **type**: text
- **page_index**: 0
- **element_index**: 11

**文本内容**

```
Fruit undergoes picking,handling, storage,and transportation from harvest to market,processes that entail considerable losses.As a perishable commodity, fruit faces challenges in post-harvest loss reduction, which currently constitutes the majority $( 8 6 \% )$ of overall fruit losses globally (Soltani Firouz and Sardari, 2O22). Fruit quality mainly declines due to diseases,defects,and decay,with navel oranges often suffering from ulcers,sunburn，wind scarring,and oil cell damage, each with unique and complex traits. Initially,separating defective from healthy fruit relied on combining classic image segmentation with traditional machine learning techniques. The morphology and appearance aspects of fruits are used to manually create feature extraction techniques,which are subsequently used to distinguish fruits using conventional classification algorithms (Rong et al., 2Ol7a). This kind of feature extraction approach necessitates in-depth prior knowledge, has low generalization and extraction accuracy,and frequently manifests as missed detection.However,deep learning,especially convolutional neural networks (CNNs),has overcome these drawbacks,providing substantially higher accuracy than traditional machine learning approaches. 
```

#### Element #13 — `element-9967a63e-e01d-4589-b7e3-67ca9895caf7`

- **type**: image
- **page_index**: 1
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig.1.Image collection and image processing of navel orange defects. 
```

#### Element #14 — `element-2e506550-eaad-4188-bbe2-685e2a81c2ba`

- **type**: text
- **page_index**: 1
- **element_index**: 1

**文本内容**

```
With the continuous advancement in computer computational capabilities,deep learning has emerged as the prevailing approach for fruit defect detection.Currently,systems for detecting fruit defects mostly use image classification methods based on deep learning.Azizah et al.(2Ol7) utilized a digital camera to take pictures of mangosteens and used a simple convolutional neural network (CNN) to identify defective fruits. De Luna et al. (2O19) classified tomato defects using the traditional networks VGG16,InceptionV3,and ResNet50,with the VGGl6 model achieving the maximum classification accuracy of $9 8 . 7 5 \%$ .With an accuracy of $9 8 . 5 \%$ ,Nithya et al. (2022) developed a deep learning vision system to identify mango defects.The empirical findings demonstrated that deep learning-based vision systems exhibit significantly superior accuracy compared to conventional machine vision methods.However,the image classification technology is unable to distinguish between different kinds of defects in a single image, pinpoint where defects are located,or otherwise meet the demands of fine sorting (Ismail and Malik, 2022) 
```

#### Element #15 — `element-0bf1ae73-6615-454c-adfb-e4c62ed0e830`

- **type**: text
- **page_index**: 1
- **element_index**: 2

**文本内容**

```
Target detection models and semantic segmentation models with a higher number of parameters compared to classification models are gradually being employed in fruit defect detection as graphics cards' processing capacity increases.The problem of the variety of defects in a single image that is difficult to recognize is resolved by the target detection approach,which locates faults and classifies them using rectangular boxes.Wang et al. (2O2O) strengthened the fusion of horizontal features,enhanced the feature pyramid module (FPM) based on the Mask R-CNN network,and performed defect detection for apples,oranges,peaches,and pears,respectively. The mean average accuracy (mAP) of detection reached $9 6 . 1 4 \%$ ， $9 5 . 9 5 \%$ ， $9 6 . 6 8 \%$ ，and $9 5 . 8 4 \%$ ．A strong generalizability model was established for defect detection of round fruits.In addition to identifying and classifying the defects, the semantic segmentation method separates each pixel in the image,which makes it easier to discover complicated edge features. With a mloU of 86.6 percent, Roy et al. (202l) presented an improved UNet architecture for distinguishing between fresh and rotting fruits. These studies broaden fruit defect detection to more scenarios,but none of them take into account how well the models function when deployed in large-scale applications. 
```

#### Element #16 — `element-d0d1c12c-9fd3-4559-8386-23a10c2c0669`

- **type**: text
- **page_index**: 1
- **element_index**: 3

**文本内容**

```
A critical factor enabling the broad implementation of defect detection models is their capacity to consistently achieve real-time detection performance while maintaining a high level of detection accuracy. Studies on target detection and semantic segmentation-based real-time detection of fruit defects are scarce.To enable real-time detection of kiwi fruit, Yao et al.(2O2l) integrated the Squeeze-and-Excitation (SE) layer into YOLOv5.Fan et al. (2022) reduced the number of channels and network depth in the YOLOv4 network while capturing photos of Apple-defective objects with the NIR camera.The network model is 8.82 megabytes (MB) in size,and it only takes $8 . 3 6 \mathrm { m } s$ to detect a single image,while mAP grows by $1 . 9 2 \%$ Liang et al. (2022) used a pallet apple defect detection scenario to introduce the small segmentation network BiSeNetV2 and used the pruned YOLOv4 to help with the issue of the segmentation network erroneously segmenting fruit stems. Despite using two networks,the strategy of merging the two ways for detection still offers a high detection speed that surpasses most segmentation networks. 
```

#### Element #17 — `element-dc909d76-e1a9-42f1-be4d-2081a5c8a72a`

- **type**: text
- **page_index**: 1
- **element_index**: 4

**文本内容**

```
Combining the results of the aforementioned investigations, existing fruit defect detection techniques face challenges in their adaptability to fine-sorting requirements.Furthermore,a majority of the target detection and semantic segmentation methods,despite fulfilling the necessary criteria, lack scalability for large-scale deployment. We proposed the real-time segmentation network FastSegFormer for navel orange defect detection.We made some changes to the PPM structure (Zhao et al.,2017),suggested adding the MSP module to the feature extraction stage,and created a branch for semi-resolution input images that performs edge feature recovery after feature fusion.Finally,it was suggested to use a multi-resolution knowledge distillation strategy to improve the fruit defect segmentation model's segmentation performance while keeping the model's size and inference speed constant.Deploying the model in a very low computational power edge computing device,the Jetson Nano,reached 2O fps,which has great potential for real detection speed.The proposed model offers aremarkable capability for accurately detecting fruit defects within intricate scenarios while simultaneously enhancing the detection speed of the inspection system.Consequently,it exhibits adaptability for widespread deployment in large-scale navel orange sorting lines. 
```

#### Element #18 — `element-9afc6b1e-3c2a-4ad9-9ef6-636515475511`

- **type**: text
- **page_index**: 2
- **element_index**: 0

**文本内容**

```
2.Materials and methods 
```

#### Element #19 — `element-93113f4a-fde9-4ba0-9534-e4efc479b6cb`

- **type**: text
- **page_index**: 2
- **element_index**: 1

**文本内容**

```
2.1.Image acquisition and dataset construction 
```

#### Element #20 — `element-8bc43a87-8ab7-45ae-8989-b77d3d32311f`

- **type**: text
- **page_index**: 2
- **element_index**: 2

**文本内容**

```
In fruit sorting operations prioritizing security，scalability,and portability,edge computing stands out. To align with the assembly line's velocity,the segmentation model is required to process a minimum of 30 images per second. The Jetson Xavier NX is a top choice for such tasks,offering robust 21 TOPS of INT8 computing power and 16 GB of memory,which ensures quick and reliable image processing capabilities.Therefore,model optimization should be implemented to improve inference speed and reduce resource consumption.Additionally,efficient data management strategies are also crucial for handling large volumes of training and test data effectively. 
```

#### Element #21 — `element-a72065bf-b20a-4701-a0c0-d4ec89091f25`

- **type**: text
- **page_index**: 2
- **element_index**: 3

**文本内容**

```
As seen in Fig.1(a),we created a straightforward navel orange image acquisition device. The system comprises an autonomous rotating display stand and an industrial camera model UC3o,with the camera connected to a computer for some automated functions.Consistent and stable white LED light sources are positioned on the camera side, as well as on the left and right sides of the navel orange.The light source is positioned at the same height as the camera,ensuring that they are aligned flush with each other. The following is the image acquisition procedure: (i) A navel orange fruit is placed on a rotating display stand with a rotation speed of 4 s per revolution. (ii) A script on the computer directs the camera to take 30 photographs evenly spaced throughout the following 4 s. (ii) Replace the navel orange and repeat the aforementioned procedures after choosing 5 images at uniform intervals. 
```

#### Element #22 — `element-890f0015-ac7f-40b0-b4cc-9e52ce3fc613`

- **type**: text
- **page_index**: 2
- **element_index**: 4

**文本内容**

```
In Ganzhou City, Jiangxi Province, China's Xinfeng Town, we gathered pictures of navel oranges with defects during October and November 2022.All of our fruit comes from orchard picking,and navel oranges are currently in the middle of their harvest.With a resolution of $2 5 9 2 \times 1 9 4 4 ~ \mathrm { p x }$ ,1448 photos of the three defects of wind scarring, ulcers,and sunburn were collected to simultaneously detect several defects.As seen in Fig.1(b),after batch cropping every image and setting the resolution back to $5 1 2 \times 5 1 2 \ \mathrm { p x }$ ,the Labelme tool is used to begin labeling the pictures. 
```

#### Element #23 — `element-80f3a84d-f9c5-4269-8c2d-3acf90c82d64`

- **type**: text
- **page_index**: 2
- **element_index**: 5

**文本内容**

```
In a 6:2:2 division of the 1448 labeled navel orange defect photos, 868 were used as the training set,29O as the validation set,and 290 as the test set. To identify defects in navel oranges,we employed data augmentation to imitate conditions like uneven lighting and highspeed motion blur in an industrial assembly line.The following are the strategies for data enhancement: (i) Geometric transformations, including random rotation, random cropping, horizontal specular flip, and vertical specular flip.(ii) Modifications to the pixel distribution, such as brightness modification, Gaussian blur, and image sharpening. We used the Imgaug toolbox to automatically construct the mask for the added photos to reduce the burden associated with annotating defect masks.Fig.2 displays the modifications to the image and mask caused by some of the image-enhancing techniques.The extended navel orange defect dataset comprises a total of 4344 photos,comprising 2604 images in the training set, 87O images in the validation set, and 870 images in the test set.We randomly applied a single technique to each image twice. 
```

#### Element #24 — `element-d01065f9-1135-4730-bedc-755b3e20651e`

- **type**: text
- **page_index**: 2
- **element_index**: 6

**文本内容**

```
The pixel ratios of the three defects in the dataset of 4344 images are approximately equal,which effectively addresses feature imbalance and enhances the model's ability to capture detailed information and global features across different-scale images. It also mitigates training bias and ensures consistent performance across varied scales. 
```

#### Element #25 — `element-1e88637a-84e2-4015-90e9-0969f88b9735`

- **type**: text
- **page_index**: 2
- **element_index**: 7

**文本内容**

```
2.2.UNet model 
```

#### Element #26 — `element-11df2eae-e3da-474b-9c83-0dd3471d002b`

- **type**: text
- **page_index**: 2
- **element_index**: 8

**文本内容**

```
UNet was created to enhance the ability to segment intricate features at the borders of medical picture segmentation.With a distinctive hierarchical structure,it is a symmetric encoder and decoder design that retains more spatial features of the image (Ronneberger et al., 2015). The encoder includes some convolutional filters and some maximum pooling layers,starting from the input image and downsampling 2 times at a time,and increasing the number of convolutional filters to 2 times the original,the decoder process is the opposite,with upsampling accomplished by bilinear interpolation.UNet's network architecture is deep,and its highly distinctive skip connection both prevents overfitting and preserves image details well. 
```

#### Element #27 — `element-f3e5c41c-dd82-403b-8b75-2dabc16d5da8`

- **type**: text
- **page_index**: 2
- **element_index**: 9

**文本内容**

```
2.3.FastSegFormer model 
```

#### Element #28 — `element-ed4cf710-3ff7-4612-a19e-b75f57bf29d8`

- **type**: text
- **page_index**: 2
- **element_index**: 10

**文本内容**

```
Sunburn,ulcers,and wind scarring are the three most prevalent defects in navel oranges.According to Fig.1(c),each of the three defects has unique characteristics. Large dark patches are seen in sunburn, round black and brown cavities are visible inulcers,and diverse colors and different shapes with intricate edge characteristics are visible in wind scars.The UNet architecture is more suited for reconstructing complex and variable defect characteristics,but the arduous process of upsampling recovered images adds more parameters and lengthens inference time,making deployment much more challenging.A critical question is how to simplify the model while maintaining its capacity to recognize intricate characteristics. 
```

#### Element #29 — `element-8f886b21-c849-414c-bbc4-32dad8ab2926`

- **type**: text
- **page_index**: 2
- **element_index**: 11

**文本内容**

```
Holder and Shafique (2022) studied some well-known real-time segmentation networks,and found that there are primarily two methods for achieving real-time network inference: one involves pairing high-resolution images with very small network models,and the other involves pairing lower image resolution with more intricate network structures.Low-resolution, fast industrial cameras are frequently purchased to save money since fruit assembly lines demand exceptionally high defect detection efficiencies.We used a lower-resolution network structure model to account for this circumstance,bringing down the input resolution of the photos to $2 2 4 \times 2 2 4 \ : \mathrm { p x }$ 
```

#### Element #30 — `element-8d8c7c50-8405-42dc-bcf6-15614e1ef4c5`

- **type**: text
- **page_index**: 2
- **element_index**: 12

**文本内容**

```
Researchers frequently employ convolutions with low channel counts or less computationally intensive structures to develop lightweight segmentation networks.ENet (Paszke et al.,2O16) comprises a relatively large encoder and a simple decoder.The network utilizes standard $3 \times 3$ convolutions,asymmetric $5 \times 5$ convolutions,and similar techniques.However,the compact network structure and a limited number of convolutional channels enable a reduced parameter count.Fast-SCNN (Poudel et al., 2O19) takes advantage of depthwise separable convolution (Ds Conv） and utilizes standard convolutions witha reduced number of channels.This strategy enables the network to increase its depth and capture global information efficiently,without compromising computational resources. BiSeNet (Yu et al., 2O18) and SwiftNet (Orsic et al.,2O19) utilize a two-branch structure for feature extraction: one branch extracts contextual information,while the other focuses on spatial information.The features from both branches are subsequently fused.Our network combines two features: the first branch extracts features and incorporates earlier representations for feature fusion,while the second branch performs simple image sampling for eficient image reconstruction,preserving details without excessive parameters. 
```

#### Element #31 — `element-770e96fc-641c-4154-a17a-29bc27fd19ec`

- **type**: image
- **page_index**: 3
- **element_index**: 0

**图片描述**

```
[图片标题]
  ig re 
```

#### Element #32 — `element-c5ed517a-5089-4cae-bf5d-15a565782e6e`

- **type**: text
- **page_index**: 3
- **element_index**: 1

**文本内容**

```
Fig.3 depicts the FastSegFormer network design. First,we performed image downsampling during the encoding stage using the Pool-Former and EfficientFormerV2 backbone networks.The network moves on to feature extraction after the backbone network.We presented the Linear Bottleneck (LB) module from the MobileNetV2 network (Sandler et al.,2O18) and designed the Multi-scale Pyramid (MSP) module,a multi-scale information extractor,in its place.The LB module achieves feature map compression or condensation by reducing the number of channels through dimensionality reduction.This operation effectively filters out redundant information and low-level features,preserving important and high-level feature information. The MSP module captures contextual information by employing multi-scale convolutions to enhance the model's ability to perceive objects at various scales. The high-level features are then combined with the low-level features from the intermediate output of the backbone network's shallow output during the decoding stage,and we employ some DS Conv modules (Sifre and Mallat, 2Ol4) to lessen the computing burden of the model.Finally,we added an image reconstruction branch,which takes the semi-resolution image input, adds fusion features by convolution, and then upsamples the image.This branch is primarily designed to compensate for the loss of early high-resolution detailed features in the deeper feature extraction phase of the network.This guarantees the model's small weight while maintaining the properties of UNet employing skip connections.With only a little increase in the number of parameters,it has been demonstrated that the image reconstruction branch can significantly improve the model's performance,particularly when it comes to the detection of fine-grained complex features.Batch Normalization and Rectified Linear Unit (ReLU) are performed after all convolutions to speed up model training. 
```

#### Element #33 — `element-efcba382-acb0-4a7c-81cb-b68f612aef12`

- **type**: text
- **page_index**: 3
- **element_index**: 2

**文本内容**

```
2.3.1.Backbone network 
```

#### Element #34 — `element-07b60812-a658-4441-a491-52564dbef57a`

- **type**: text
- **page_index**: 3
- **element_index**: 3

**文本内容**

```
A backbone network can be used for feature extraction and finetuning,and it usually has two options at present,one is a CNN network, and the other is the Transformer network.For the lightweight segmentation model, the parameters and computation of the backbone network determine the overall size of the network.The traditional CNN lightweight backbone network has a small number of parameters but weak feature extraction capability,and many special convolutions are not conducive to hardware implementation, such as DS Conv (Sandler et al.,2O18).For tasks with certain requirements of detailed information,multi-scale information extraction is important,but using multi-scale convolution in the early period of the network when the feature map is large will greatly increase the number of parameters.Transformer differs from CNN in that it processes the whole image at the same time,focusing more on global information and having better feature extraction capability (Dosovitskiy et al.,2020). For hardware,Transformer's internal self-attention mechanism is very time-consuming and Transformer's lightweight can make a huge difference.Yu et al.(2O22） replaces the self-attentive mechanism in Transformer with a simple multi-layer perceptron (MLP)and found that it also worked,and they called this module PoolFormer.Li etal.(2022) replaces Transformer with Pool mixer in the early stages of the network, which greatly reduces the number of parameters and maintains good performance. 
```

#### Element #35 — `element-330e11db-ac42-4de2-9a95-05c0e8a02f7e`

- **type**: text
- **page_index**: 3
- **element_index**: 4

**文本内容**

```
The transformer structure-based lightweight backbones PoolFormer and EfficientFormerV2 both better collect global contextual data. PoolFormer-S12 and EfficientFormerV2-SO are the two minimal versions of the series network that we have selected. 
```

#### Element #36 — `element-03152751-068c-4179-83d8-5c0b5f1f15b7`

- **type**: text
- **page_index**: 3
- **element_index**: 5

**文本内容**

```
2.3.2.Feature extraction 
```

#### Element #37 — `element-dba28aaf-e3fc-483f-8e77-94e71223c0d7`

- **type**: text
- **page_index**: 3
- **element_index**: 6

**文本内容**

```
We initially reduced the number of picture channels to 256 using point-by-point convolution to decrease the overhead in the feature extraction stage.MobileNetV2 introduced the inverted residual block LB,which expands the feature map before compressing it,reversing the common practice of reducing and then expanding features (Sandler et al.,2O18). The LB module,depicted in Fig.4, first increases the number of channels in the feature map by three times,then passes them through a second depthwise (DW) convolution and ReLU, before compressing the number of channels and adds a residual connection. 
```

#### Element #38 — `element-e554f841-6456-4d90-879a-0051ef4dce0a`

- **type**: text
- **page_index**: 3
- **element_index**: 7

**文本内容**

```
The pyramid pooling module (PPM) is an efficient multicore pooling layer,and the output feature maps of these pooling layers are connected along the channel dimension to form a multiscale representation of the input feature maps (Zhao et al., 2Ol7). Pooling is computationally simple,but more information is lost,based on which an MSP module is designed. Fig.5 depicts the MSP module's structural layout. In the MSP module, the $_ \mathrm { ~ 1 ~ \times ~ 1 ~ }$ ， $3 \times 3$ ， $5 \times 5$ ，and $7 \times 7$ convolutions are employed,with each one being followed by a ${ \bf 1 } \times { \bf 1 }$ convolution, feature map stitching,and a $1 \times 1$ convolution to turn back the number of channels of the input picture.We perform padding in the feature map's multi-scale convolution to better preserve the edge information at low resolution.This makes sure that the feature maps are the same size both before and after input,and it reduces computation by changing the number of channels after multi-scale convolution to 1/4 of the original size. 
```

#### Element #39 — `element-0f261453-a34e-4ce0-95c6-5aa86e626e47`

- **type**: text
- **page_index**: 3
- **element_index**: 8

**文本内容**

```
2.3.3.Image reconstruction branch 
```

#### Element #40 — `element-6244eda9-752d-4316-8fe1-5bd0c925f3a3`

- **type**: text
- **page_index**: 3
- **element_index**: 9

**文本内容**

```
The detailed features of the image steadily disappear as the number of network levels increases.Wang et al. (2O22) used an experiment to show that the lost spatial resolution of downsampling can be recovered by using a skip connection at the start of UNet. To employ this feature, an image reconstruction branch from the input image with a halfresolution resolution is first added to the network,then the feature 
```

#### Element #41 — `element-52ec736c-7e56-4a0b-b384-2c7b32ffe056`

- **type**: image
- **page_index**: 4
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig.3.Architecture of the FastSegFormer model. 
```

#### Element #42 — `element-5916e6ed-ceec-4431-b7b9-1aaf24be97f7`

- **type**: image
- **page_index**: 4
- **element_index**: 1

**图片描述**

```
[图片标题]
  Fig.4.Linear Botleneck. 
```

#### Element #43 — `element-0791ef7f-6a0a-44fb-b754-0c112481da84`

- **type**: image
- **page_index**: 4
- **element_index**: 2

**图片描述**

```
[图片标题]
  Fig.5.The structure of the Multi-scale Pyramid module. 
```

#### Element #44 — `element-a74b89ba-24d3-4d4f-9b5a-cb18c3e12924`

- **type**: image
- **page_index**: 5
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig.6.The architecture of proposed knowledge distillation method. 
```

#### Element #45 — `element-cce922be-4f68-4b9b-8f6c-314860207caf`

- **type**: text
- **page_index**: 5
- **element_index**: 1

**文本内容**

```
fusion results are added,and finally,the resolution of the input image is restored using convolution and upsampling.We find it amazing that increasing the amount of computing very litle improves the ability to recognize details. 
```

#### Element #46 — `element-a5c40e29-168e-4c91-a269-b1fdacf416ba`

- **type**: text
- **page_index**: 5
- **element_index**: 2

**文本内容**

```
2.4.Knowledge distillation 
```

#### Element #47 — `element-2a0c62c4-0789-44ce-a251-0b4f1420cfda`

- **type**: text
- **page_index**: 5
- **element_index**: 3

**文本内容**

```
Larger,more capable models can act as teachers thanks to a novel transfer learning strategy called knowledge distillation,which enables student models to independently learn the data distribution of the teacher's network.Without adding to the computational load,models can learn richer feature representation,and with the correct methodology,student models may even outperform teacher models (Heo et al., 2019).The overall approach to knowledge distillation is shown in Fig.6.We employed offline distillation,the parameters of the teacher model are trained in advance and are not changed throughout the distillation process.We learned the feature maps of the intermediate output of the teacher model in addition to distilling the model's output results. 
```

#### Element #48 — `element-c2793dfa-27a7-4cff-b6d3-e3c20c86734e`

- **type**: text
- **page_index**: 5
- **element_index**: 4

**文本内容**

```
2.4.1.Multi-resolution input distillation method 
```

#### Element #49 — `element-f46ffc13-2f69-4f0d-b3fb-d542b3124748`

- **type**: text
- **page_index**: 5
- **element_index**: 5

**文本内容**

```
The teacher model in the general knowledge distillation approach is an extended version of the student model with the same input resolution to facilitate teaching (Heo et al., 2O19; Liu et al., 2019). We think that the data distribution or“knowledge”obtained from the teacher model,not the teacher model itself,is what knowledge distillation learns.The teacher model's input resolution was increased to improve distillation,as shown in Fig.6,and the top-performing UNet series model was chosen for the teacher model. The overall design of the teacher model replaces the feature extraction of the UNet model with Swin-Tiny's backbone network (Liu et al.,2021) and adds a potent cascading attention mechanism called Attention Gate (AG) (Oktay et al., 2018) before skipping connections.By sampling all of the instructor model's outputs,the issue of a non-uniform feature map size caused by varying input resolutions is resolved. Using pointby-point convolution,the student model is also converted to have the same amount of channels as the teacher model.The following is the distillation procedure: 
```

#### Element #50 — `element-0f3f1607-4071-4ded-9bb4-74f80175e265`

- **type**: text
- **page_index**: 5
- **element_index**: 6

**文本内容**

```
(i) After achieving the best accuracy when training the complex model using $5 1 2 \times 5 1 2 \ \mathrm { p x }$ images,store the parameters. (ii) To avoid backpropagation,the instructor model loads the previously saved parameters and locks them.The $2 2 4 \times 2 2 4$ px images are used to train the student model,which is then iterated through the segmentation loss function and the distillation loss function. (ii) Take note that the backbone network's pre-trained parameters must be locked for 5O training epochs before being unlocked if distillation and fine-tuning are carried out simultaneously to maintain the fine-tuning effect. 
```

#### Element #51 — `element-7b5c967e-37ce-467a-944f-f63f363707fc`

- **type**: text
- **page_index**: 5
- **element_index**: 7

**文本内容**

```
2.5. Loss function 
```

#### Element #52 — `element-db2f8931-5f88-4926-8705-6a35fc883dd8`

- **type**: text
- **page_index**: 5
- **element_index**: 8

**文本内容**

```
The Cross entropy (CE) loss function is used between the predicted results of the model and the labels and is calculated as follows: 
```

#### Element #53 — `element-aeff05ab-c510-487f-8ace-d8573dbd667b`

- **type**: equation
- **page_index**: 5
- **element_index**: 9

**Element 内容**

```
{'text': '$$\nL _ { c e } = - \\sum _ { i = 1 } ^ { c } y _ { i } \\log ( q _ { i } )\n$$', 'text_format': 'latex'}
```

#### Element #54 — `element-258d6b9a-3a6c-457f-b6d7-5787b1129934`

- **type**: text
- **page_index**: 5
- **element_index**: 10

**文本内容**

```
where $q _ { i }$ represents the probability of the ith category of pixels, $y _ { i }$ represents the true label of the ith category of pixels,and $c$ represents the number of categories. 
```

#### Element #55 — `element-c4219af7-8aee-42ab-b12c-76be063a2aec`

- **type**: text
- **page_index**: 5
- **element_index**: 11

**文本内容**

```
After adding the knowledge distillation method,we introduce the feature distillation loss function for the intermediate feature maps and use the logits distillation loss function for the model output results. As in the method described in Section 2.4.1,the size and number of channels of the feature maps of the complex and simple networks have been transformed to be the same before performing the calculations. 
```

#### Element #56 — `element-4b1ea36c-136e-42be-84c1-65d001e1f431`

- **type**: text
- **page_index**: 5
- **element_index**: 12

**文本内容**

```
Logits distillation.The logits distillation takes a common approach (Hinton et al.,2O15):using the category probability of the output results of the complex model as a soft target. To this,we add the calculation of the mean square error of the output pixels between the complex and simple networks. 
```

#### Element #57 — `element-c8e8411b-e71d-45f2-b2ee-5c74a07d18af`

- **type**: text
- **page_index**: 6
- **element_index**: 0

**文本内容**

```
The logits distillation loss function is given as follows: 
```

#### Element #58 — `element-6f571551-38af-4537-87f7-f02ac04209ae`

- **type**: equation
- **page_index**: 6
- **element_index**: 1

**Element 内容**

```
{'text': '$$\nL _ { l o g i t s } = \\frac { 1 } { W _ { s } \\times H _ { s } } ( k _ { 1 } t ^ { 2 } \\sum _ { i \\in R } \\mathrm { K L } ( q _ { i } ^ { s } , q _ { i } ^ { t } ) + ( 1 - k _ { 1 } ) \\sum _ { i \\in R } \\mathrm { M S E } ( p _ { i } ^ { s } , p _ { i } ^ { t } ) )\n$$', 'text_format': 'latex'}
```

#### Element #59 — `element-a7a6a2da-19b7-480c-b886-e80fbbf4203d`

- **type**: text
- **page_index**: 6
- **element_index**: 2

**文本内容**

```
where $q _ { i } ^ { s }$ represents the class probability of the ith pixel output from the simple network S, $q _ { i } ^ { t }$ represents the class probability of the ith pixel output from the complex network T,KL(-) represents Kullback-Leibler divergence, $p _ { i } ^ { s }$ represents the ith pixel output from the simple network S, $p _ { i } ^ { t }$ represents the ith pixel output from the complex network T,MSE(-) represents the mean square error calculation, $\boldsymbol { R } = \{ 1 , 2 , \dots , W _ { s } \times H _ { s } \}$ represents all pixels,and $t$ represents the temperature coefficient. In this experiment, $t = 2$ ， $k _ { 1 } = 0 . 5$ 
```

#### Element #60 — `element-085aa845-cb20-4ff1-8cac-2bfd21481f59`

- **type**: text
- **page_index**: 6
- **element_index**: 3

**文本内容**

```
Normalized feature distillation.Feature distillation transfers knowledge by minimizing the distance between complex and simple networks in the feature space.Before calculating the distance,it is usually necessary to convert the hidden features of complex and simple networks into a form that can be easily transferred (Heo et al.,2019). We introduce a streamlined approach to distillation, termed normalized distillation.This technique involves standardizing the width and height dimensions as part of a feature transformation between intricate and straightforward network architectures (Liu et al.,2022).We then compute the Euclidean distance between these normalized features to formulate a loss function expressly for normalized feature distillation (NFD). 
```

#### Element #61 — `element-8e320f0d-f588-46e8-9095-49a77121b3a2`

- **type**: text
- **page_index**: 6
- **element_index**: 4

**文本内容**

```
The NFD loss function is given as follows: 
```

#### Element #62 — `element-2e8b84d7-bf8a-4dfa-8c6e-84501f61a885`

- **type**: equation
- **page_index**: 6
- **element_index**: 5

**Element 内容**

```
{'text': '$$\nL _ { n } ^ { N F D } = \\sum _ { i = 1 } ^ { n } \\frac { 1 } { W _ { s } \\times H _ { s } } L _ { 2 } ( \\mathrm { N o r m a l } ( F _ { i } ^ { t } ) , \\mathrm { N o r m a l } ( F _ { i } ^ { s } ) )\n$$', 'text_format': 'latex'}
```

#### Element #63 — `element-b5911486-7957-4039-bbe1-f778539cd95f`

- **type**: text
- **page_index**: 6
- **element_index**: 6

**文本内容**

```
where $n$ represents the number of intermediate feature maps, $W _ { s }$ and $H _ { s }$ represent the height and width of the simple model feature map, $L _ { 2 } ( \cdot )$ represents the Euclidean calculation of the feature maps, $F _ { i } ^ { t }$ represents the ith feature map generated by the complex network T, $F _ { i } ^ { s }$ represents the ith feature map generated by the simple network S, Normal represents the normalization of the feature maps on $( W , H )$ the Normal(·) in Eq. (3) is given as follows: 
```

#### Element #64 — `element-c2068935-2461-4b64-97ad-e4590d8bc17f`

- **type**: equation
- **page_index**: 6
- **element_index**: 7

**Element 内容**

```
{'text': '$$\n\\bar { F } = \\frac { 1 } { \\sigma } ( F - u )\n$$', 'text_format': 'latex'}
```

#### Element #65 — `element-00cf0902-42d6-448d-b6d7-669049c4743d`

- **type**: text
- **page_index**: 6
- **element_index**: 8

**文本内容**

```
where $F$ represents the original feature map, $\bar { F }$ represents the feature transform,and $\boldsymbol { u }$ and $\sigma$ represent the mean and standard deviation of the features. 
```

#### Element #66 — `element-b16be222-ffa4-4917-b643-79bf123c3cf7`

- **type**: text
- **page_index**: 6
- **element_index**: 9

**文本内容**

```
Using knowledge distillation for training,the following is our total loss function: 
```

#### Element #67 — `element-46e239e9-ad22-42fe-a4ff-f6ff154a956c`

- **type**: equation
- **page_index**: 6
- **element_index**: 10

**Element 内容**

```
{'text': '$$\n\\begin{array} { r } { L o s s = L _ { c e } + \\lambda _ { 1 } L _ { l o g i t s } + \\lambda _ { 2 } L _ { n } ^ { N F D } } \\end{array}\n$$', 'text_format': 'latex'}
```

#### Element #68 — `element-0360274e-e39c-4b59-ad27-70ae2cb229f5`

- **type**: text
- **page_index**: 6
- **element_index**: 11

**文本内容**

```
where $\lambda _ { 1 }$ is set to $0 . 5 , \ \lambda _ { 2 }$ is set to 5.When $\lambda _ { 1 }$ is equal to O.5 and $\lambda _ { 2 }$ is equal to 5,the values of the feature distillation loss and logits distillation loss are comparable to $L _ { c e }$ 
```

#### Element #69 — `element-954534d4-dde4-48ef-b349-9d63d2f44d67`

- **type**: text
- **page_index**: 6
- **element_index**: 12

**文本内容**

```
2.6. Training and test 
```

#### Element #70 — `element-03342c66-af91-4490-a6c3-e682eca9b545`

- **type**: text
- **page_index**: 6
- **element_index**: 13

**文本内容**

```
2.6.1.Network structures 
```

#### Element #71 — `element-2d87891a-eb74-419d-a5de-0a3e7bbbca2f`

- **type**: text
- **page_index**: 6
- **element_index**: 14

**文本内容**

```
In this paper,we built the FastSegFormer model and created two models,dubbed FastSegFormer-P and FastSegFormer-E,based on the PoolFormer-S12 backbone and EfcientFormerV2-S0 backbone,respectively,to uncover two detection strategies with high detection speed and low memory.Both models were put through ablation studies to examine the impact of the MSP module and the image reconstruction branch: (i) Baseline model: The MSP module is replaced with PPM and the image reconstruction branch is eliminated based on the FastSeg-Former model.(ii) The MSP module is used in place of the PPMbased on the baseline model.(iii) The article's FastSegFormer model. Some additional tests on image enhancement were also added to the ablation experiments of the model structures. 
```

#### Element #72 — `element-dc32a138-3868-452f-845f-7ea8aaa5132d`

- **type**: text
- **page_index**: 6
- **element_index**: 15

**文本内容**

```
We also contrasted the benefit of distillation in FastSegFomer with the impact of fine-tuning.Different weights were applied to feature distillation and logits distillation for both models,aiming to explore the roles of distillation strategies. 
```

#### Element #73 — `element-456c9f97-6221-4532-ae01-c2c248d564a2`

- **type**: text
- **page_index**: 6
- **element_index**: 16

**文本内容**

```
We used several well-nown lightweight models (ENet, BiSeNet, Fast-SCNN, SwiftNet,FANet, and PIDNet) for training and testing at an input resolution of $2 2 4 \times 2 2 4$ to assess the functionality and inference speed of FastSegFormer.The distillation-boosted FastSegFormer model is employed here,and the training setup is the same as FastSegFormer, see Section 2.6.2 for more information. 
```

#### Element #74 — `element-a29bdd0a-a3d1-4e2b-a7e6-be19fa6395d6`

- **type**: text
- **page_index**: 6
- **element_index**: 17

**文本内容**

```
2.6.2. Training setup 
```

#### Element #75 — `element-32b8070e-017a-43e9-bb75-b8c75df4045b`

- **type**: text
- **page_index**: 6
- **element_index**: 18

**文本内容**

```
Using Pytorch 1.12.1 and CUDA 10.2,all models in this study were trained in a 64-bit Windows 1O environment. For training,we choose the Adam optimizer,and its internal momentum parameter is set to O.9.The learning rate was managed using a warm-up and the cosine annealing process.For model training and model inference speed testing,a computer equipped with an Intel Core i5-10500 $@ 3 . 1 0$ GHz processor,16 GB of RAM,and a GeForce RTX306O graphics card was employed. For normal training, the input image resolution is $2 2 4 \times 2 2 4$ ， and the batch size is 32.For distillation training,the image resolution is $5 1 2 \times 5 1 2$ ,and the batch size is 6.All model training times were set to 1000 epochs,and the maximum baseline learning rate $( B L R _ { m a x } )$ was set to O.oool.To adapt the network to different mini-batches,we set the adaptive adjustment of the learning rate,Eq.(6) is its definition. 
```

#### Element #76 — `element-381583f3-4e7c-48ff-acda-85cb81f4dafc`

- **type**: equation
- **page_index**: 6
- **element_index**: 19

**Element 内容**

```
{'text': '$$\n\\begin{array} { r l r } & { } & { M a x { L R } = m i n ( m a x ( \\frac { B S \\times B L R _ { m a x } } { 1 6 } , 1 \\times 1 0 ^ { - 4 } ) , 1 \\times 1 0 ^ { - 4 } ) } \\\\ & { } & { M i n { L R } = m i n ( m a x ( \\frac { B S \\times B L R _ { m i n } } { 1 6 } , 1 \\times 1 0 ^ { - 6 } ) , 1 \\times 1 0 ^ { - 6 } ) } \\\\ & { } & { B L R _ { m i n } = 0 . 0 1 B L R _ { m a x } ~ } \\end{array}\n$$', 'text_format': 'latex'}
```

#### Element #77 — `element-4b7e9c83-5c5b-40fd-b95b-cf66befd7460`

- **type**: text
- **page_index**: 6
- **element_index**: 20

**文本内容**

```
where $M a x L R$ and MinLR denote adaptive maximum learning rate and adaptive minimum learning rate，respectively.BS denotes the batch size,and $B L R$ denotes the benchmark learning rate. 
```

#### Element #78 — `element-9354476d-a031-4561-b093-40e998964cfe`

- **type**: text
- **page_index**: 6
- **element_index**: 21

**文本内容**

```
2.6.3.Model evaluation metrics 
```

#### Element #79 — `element-2df8f77d-c7fd-4ffc-aaf8-b4b280921db1`

- **type**: text
- **page_index**: 6
- **element_index**: 22

**文本内容**

```
In this paper, the model performance is evaluated comprehensively in terms of both detection performance and deployment performance. The metrics of detection performance are mean pixel accuracy (mPA), mean precision (mPrecision),intersection over union (IoU),and mean intersection over union (mIoU).The metrics that reflect the deployment performance are model parameters (Params/M),computation (GFLOPs),and model segmentation speed (Speed/FPS).The model metrics are given as follows: 
```

#### Element #80 — `element-0f418094-8a9c-4752-9f06-d5c4f05d5962`

- **type**: equation
- **page_index**: 6
- **element_index**: 23

**Element 内容**

```
{'text': '$$\n\\begin{array} { l } { m P A = \\displaystyle \\frac { 1 } { c + 1 } \\sum _ { i = 0 } ^ { c } \\frac { T P + T N } { T P + T N + F P + F N } } \\\\ { m P r e c i s i o n = \\displaystyle \\frac { 1 } { c + 1 } \\sum _ { i = 0 } ^ { c } \\frac { T P } { T P + F P } } \\\\ { I o U = \\displaystyle \\frac { T P } { T P + F P + F N } } \\\\ { m I o U = \\displaystyle \\frac { 1 } { c + 1 } \\sum _ { i = 0 } ^ { c } \\frac { T P } { T P + F P + F N } } \\end{array}\n$$', 'text_format': 'latex'}
```

#### Element #81 — `element-9a52fcdd-04b8-4f54-bd91-c98388932b3a`

- **type**: text
- **page_index**: 6
- **element_index**: 24

**文本内容**

```
where $T P$ means True Positive,which is the number of pixels correctly classified, $F P$ means False Positive,which is the number of pixels incorrectly classified, $T N$ means True Negative,which is the number of pixels correctly classified as other classes,and $F N$ means False Negative,the number of pixels incorrectly classified as other classes. $c$ means the number of pixel categories except for the background. 
```

#### Element #82 — `element-f51543e5-2ad0-44bf-b5e4-fa2753343af8`

- **type**: text
- **page_index**: 6
- **element_index**: 25

**文本内容**

```
Every five epochs during training,the model calculates the mIoU of the validation set and saves the parameters to better assess its segmentation capabilities.The parameters with the highest mIoU after training are utilized to evaluate the test set and to determine the model's performance. 
```

#### Element #83 — `element-458a5f6c-daa1-41e5-a35d-ab774760c67f`

- **type**: image
- **page_index**: 7
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig.7.Accuracy (mIoU) variation curve of each model in the model structure ablation study. 
```

#### Element #84 — `element-5788c4f6-5f7d-4a5f-8063-bd76f638a158`

- **type**: image
- **page_index**: 7
- **element_index**: 1

**图片描述**

```
[图片标题]
  Fig.8.Line plots of the change in accuracy(mIoU) in the distilltion loss weighting parameter ablation study. $\lambda _ { 1 }$ represents the weight of Logits loss and $\lambda _ { 2 }$ represents the weigh of NFD loss.KD means knowledge distillation. 
```

#### Element #85 — `element-85fef9c4-545e-4b51-9892-9b948c6e6080`

- **type**: text
- **page_index**: 7
- **element_index**: 2

**文本内容**

```
3. Results and analysis 
```

#### Element #86 — `element-687d0259-ff41-4714-9fe9-439a56258bf8`

- **type**: text
- **page_index**: 7
- **element_index**: 3

**文本内容**

```
3.1．Ablation studies 
```

#### Element #87 — `element-73569fba-d892-4a8a-a176-80dfdab619ac`

- **type**: text
- **page_index**: 7
- **element_index**: 4

**文本内容**

```
On the self-created navel orange dataset,ablation studies and additional testing of data enhancement using FastSegFormer models with various structures.Data enhancement techniques,the addition of MSP and the inclusion of image reconstruction branches can all significantly improve accuracy compared to the validation set in Fig.7.Due to less convolutional computation being done for up-sampling following the fusing of semi-resolution picture inputs, the accuracy rise for the FastSegFormer model with image reconstruction branching is a little slower.While adding image details,this branch also disrupts the original global data,which must be fixed in later upsampling.We include a portion of the training time as a cost to lessen the rise in computation. It should be highlighted that the EfficientFormerV2-SO's architecture is considerably more complex than that of the PoolFormer-S12, featuring an intricate network of dense branch connections and sophisticated fusion structures. These elements are central to the training volatility encountered with the FastSegFormer-E model. 
```

#### Element #88 — `element-4b141679-824a-4f19-b910-1577fc046caa`

- **type**: text
- **page_index**: 7
- **element_index**: 5

**文本内容**

```
Tables 1 and 2 display the segmentation performance and deployment performance of several models used in the ablation investigation, respectively. Both image enhancement and fine-tuning techniques delivered significant segmentation performance gains.The mIoU and mPA of the model with the image reconstruction branches eliminated for the FastSegFormer-E model with the PPM module are $8 3 . 0 1 \%$ and $8 9 . 9 7 \%$ ， respectively. The model parameters and computation only increase by 
```

#### Element #89 — `element-c534b89c-00bb-4193-a818-af90eb73e701`

- **type**: text
- **page_index**: 7
- **element_index**: 6

**文本内容**

```
$0 . 5 2 \mathrm { ~ M ~ }$ and O.03 GFLOPs once the PPM is replaced with MSP,while the mIoU and mPA are improved by $0 . 8 7 \%$ and $0 . 7 6 \%$ ,respectively. The model parameters and computation only go up by $0 . 0 1 \mathrm { ~ M ~ }$ and 0.06 GFLOPs once the image reconstruction branch is included,and mIoU and mPA go up by $4 . 6 1 \%$ and $3 . 4 3 \%$ ,respectively.The mIoU and mPA of the model with the image reconstruction branches eliminated for the FastSegFormer-P model with the PPM module were $8 4 . 2 9 \%$ and $8 9 . 9 1 \%$ ,respectively.The model parameters and computation only increase by $1 . 3 2 \mathrm { ~ M ~ }$ and 0.O7 GFLOPs once PPMis replaced with MSP, while the mIoU and mPA are improved by $0 . 6 7 \%$ and $0 . 8 9 \%$ ，respectively. The model parameters and computation only go up by $0 . 0 2 \mathrm { ~ M ~ }$ and O.O7 GFLOPs once the image reconstruction branch is included, and the mIoU and mPA go up by $3 . 6 1 \%$ and $2 . 3 5 \%$ ,respectively.The addition of the image reconstruction branch considerably improves the IoU metrics of wound scarring defects and ulcer defects with complex edge features,demonstrating how effective this branch is at enhancing the model's recognition of complicated features. 
```

#### Element #90 — `element-7bf1e308-d12e-41e7-9edf-321ae141df3e`

- **type**: text
- **page_index**: 7
- **element_index**: 7

**文本内容**

```
Fig.8 illustrates the changes in segmentation accuracy of the model with different weights assigned to the distillation loss.The FastSegFormer-E model achieved peak segmentation performance, with the highest accuracy,at settings $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ .Notably,the model's segmentation accuracy falls below that of the no-distillation baseline when the individual distillation losses are excessively high or low.The FastSegFormer-P model attained its peak accuracy at the settings of $\lambda _ { 1 } = 0 . 5$ ， $\lambda _ { 2 } = 5$ ,and also at $\lambda _ { 1 } = 0 . 7 5$ ， $\lambda _ { 2 } = 7 . 5$ .Contrasting with FastSegFormer-E,the distillation process yielded predominantly beneficial outcomes for this model.The results from both models 
```

#### Element #91 — `element-3d13cae9-22bd-4238-ae49-51ebb4959d0e`

- **type**: table
- **page_index**: 8
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 1 Segmentic performance of different models in the model structure ablation study. 
[表格内容]
<table><tr><td rowspan="2">Model</td><td rowspan="2">mIoU (%)</td><td rowspan="2">mPA (%)</td><td colspan="4">IoU (%)</td></tr><tr><td>Background</td><td>Sunburn</td><td>Ulcer</td><td>Wind scarring</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB +W/PPM OD</td><td>79.84</td><td>85.12</td><td>98.93</td><td>83.19</td><td>77.28</td><td>60.34</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM ED</td><td>81.93</td><td>87.34</td><td>99.00</td><td>86.09</td><td>79.30</td><td>63.32</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† OD</td><td>82.74</td><td>88.32</td><td>99.03</td><td>87.76</td><td>79.88</td><td>65.43</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† ED</td><td>83.01</td><td>88.97</td><td>98.99</td><td>88.05</td><td>79.91</td><td>65.10</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>83.88</td><td>89.73</td><td>99.05</td><td>88.17</td><td>80.11</td><td>68.17</td></tr><tr><td>FastSegFormer-E(ours) †ED</td><td>88.49</td><td>93.16</td><td>99.35</td><td>89.29</td><td>87.40</td><td></td></tr><tr><td>FastSegFormer-P+</td><td></td><td></td><td></td><td></td><td></td><td>77.94</td></tr><tr><td>W/o IRB+W/ PPM OD</td><td>79.21</td><td>84.88</td><td>98.89</td><td>82.37</td><td>74.53</td><td></td></tr><tr><td>FastSegFormer-P +</td><td></td><td></td><td></td><td></td><td></td><td>59.89</td></tr><tr><td>W/o IRB+W/PPM ED</td><td>80.03</td><td>86.25</td><td>98.96</td><td>82.26</td><td>78.16</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>60.74</td></tr><tr><td>FastSegFormer-P + W/o IRB+W/PPM†OD</td><td>82.46</td><td>88.01</td><td>99.00</td><td>85.77</td><td>79.35</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.18</td></tr><tr><td>FastSegFormer-P + W/o IRB+ W/ PPM†ED</td><td>84.29</td><td>89.91</td><td>99.07</td><td>88.34</td><td>81.07</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.67</td></tr><tr><td>FastSegFormer-P+</td><td></td><td>90.80</td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>84.96</td><td></td><td>99.11</td><td>88.53</td><td>81.98</td><td>70.22</td></tr><tr><td>FastSegFormer-P(ours) † ED</td><td>88.57</td><td>93.15</td><td>99.35</td><td>89.34</td><td>87.50</td><td>78.09</td></tr></table>
[表格脚注]
  w/o:without.w/:with. IRB: Image reconstruction branch. †:Backbone network was pretrained in ImageNet-1K. OD: Original Datasets.ED:Enhanced Datasets. 
```

#### Element #92 — `element-1a43dca9-484c-45ce-b6cf-f3c9155ebea4`

- **type**: table
- **page_index**: 8
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 2 Deployment performance of different models in the model structure ablation study. 
[表格内容]
<table><tr><td>Model</td><td>Params(M)</td><td>GFLOPs</td><td>RTX3060 Speed(FPS)</td></tr><tr><td>FastSegFormer-E+W/o IRB+W/PPM</td><td>4.48</td><td>0.71</td><td>64</td></tr><tr><td>FastSegFormer-E +W/o IRB+W/MSP</td><td>5.00</td><td>0.74</td><td>62</td></tr><tr><td>FastSegFormer-E(ours)</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/PPM</td><td>13.53</td><td>2.56</td><td>117</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/MSP</td><td>14.85</td><td>2.63</td><td>112</td></tr><tr><td>FastSegFormer-P(ours)</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
[表格脚注]
  w/o:without. w/: with. IRB:Image reconstruction branch. 
```

#### Element #93 — `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`

- **type**: text
- **page_index**: 8
- **element_index**: 2

**文本内容**

```
demonstrate that overly high NFD distillation losses substantially diminish accuracy,whereas the impact of excessive logits distillation losses appears to be less detrimental. This discrepancy arises because a distillation loss that is too large for intermediate feature maps can rapidly deteriorate the representational information derived from the pre-training weights.On the other hand,logits positioned at the output of the model have a relatively lesser impact in this regard.For the FastSegFormer-E model,when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5 .$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 7 5$ ,as indicated by the red broken line.For the FastSegFormer-P model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 5$ ,as indicated by the green broken line.In conclusion,after careful evaluation,we have selected $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ as the definitive weights for our model. 
```

#### Element #94 — `element-75327a64-86e1-4355-b757-eb4714ebb44d`

- **type**: text
- **page_index**: 8
- **element_index**: 3

**文本内容**

```
The model's performance in the knowledge distillation ablation research is shown in Table 3.The suggested knowledge distillation strategy enhances the mIoU metrics on the FastSegFormer-E and FastSegFormer-P models by $0 . 7 3 \%$ and $1 . 2 8 \%$ ,respectively when the models are trained from scratch.The suggested knowledge distillation increases the mIoU metrics on the FastSegFormer-E and FastSegFormer-P models by $0 . 2 9 \%$ and $0 . 7 6 \%$ ，respectively,when the models are fine-tuned utilizing the parameters of the backbone network after ImageNet-1K pre-training.We find that multi-resolution knowledge distillation performs better than same-resolution knowledge distillation in a variety of situations.Larger resolutions retain more image detail,teacher models perform better,and more knowledge about the details is extracted.After knowledge distillation,FastSegFormer-E and FastSegFormer-P respectively reached $8 8 . 7 8 \%$ and $8 9 . 3 3 \%$ of mIoU,which is close to the mloU value of $9 0 . 5 3 \%$ of the teacher network despite the student network having a much smaller number of parameters and requiring less computation. 
```

#### Element #95 — `element-9bffed7a-5ec4-4965-967c-df6930a1399e`

- **type**: text
- **page_index**: 8
- **element_index**: 4

**文本内容**

```
3.2.Performance comparison of FastSegFormer and other segmentation models 
```

#### Element #96 — `element-ac2edf98-8eaf-41d4-b82f-d30e2b515bdf`

- **type**: text
- **page_index**: 8
- **element_index**: 5

**文本内容**

```
The segmentation and inference performance of the FastSegFormer model is thoroughly compared to those of other lightweight segmentation methods in Table 4.All models were tested in the same environment using the GeForce RTX3o6O training graphics card for inference. The model we created performed the best out of all models.Our FastSegFormer-P reaches real-time segmentation speed (1o8FPS) in terms of inference speed.Despite having minimal theoretical computations,ENet and FastSegFormer-E both have lengthy actual computation times. 
```

#### Element #97 — `element-215f889a-b739-43a0-a64f-272dd462a80c`

- **type**: text
- **page_index**: 8
- **element_index**: 6

**文本内容**

```
Fig.9 displays mIoU with the inference speed of models with mloU larger than 70,and Fig.1O plots mloU with the number of parameters for models with mIoU greater than 7O,both on the navel orange dataset (test set).Different series of models are plotted using various icons,and straight lines are used to connect models that are related.As depicted in Fig. 9,models located in the upper right quadrant of the graph outperform others.The proposed FastSegFormer-E model achieves a high accuracy rate,but its inference speed is on the slow side.On the other hand,the FastSegFormer-P model offers a better solution,providing both respectable speeds and high segmentation precision.Compared to our models,alternative lightweight options may operate faster but with significantly reduced accuracy in segmentation tasks.Fig.1O indicates that optimal models are positioned in the upper left corner,signifying lower parameter counts with high performance.FastSegFormer-P, although it attains the best segmentation performance,is hampered by its substantial parameter size.In contrast, FastSegFormer-E demonstrates high accuracy while being more memory-efficient, a significant advantage in memory-constrained environments. ENet, despite having the smallest number of parameters,still delivers robust segmentation performance,also making it an impressively efficient choice in this scenario.In conclusion,the proposed FastSegFormer-E model achieves excellent segmentation accuracy with memory constraints,and the FastSegFormer-P model achieves in the highest segmentation accuracy while ensuring detection speed. 
```

#### Element #98 — `element-3427ce8f-774a-4e23-8f81-19deb7e71cfc`

- **type**: table
- **page_index**: 9
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 3 Knowledge distillation and fine-tuning for ablation study. 
[表格内容]
<table><tr><td>Model</td><td>mIoU (%)</td><td>mPA (%)</td><td>mPrecison (%)</td><td>Params(M)</td><td>GFLOPs</td></tr><tr><td>Swin-T-Att-UNet (T-224) †</td><td>89.73</td><td>94.08</td><td>94.85</td><td>49.21</td><td>14.52</td></tr><tr><td>Swin-T-Att-UNet (T-512) †</td><td>90.53</td><td>94.65</td><td>95.20</td><td>49.21</td><td>77.80</td></tr><tr><td>FastSegFormer-E</td><td>86.51</td><td>91.63</td><td>93.53</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD</td><td>87.24</td><td>92.20</td><td>93.82</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2</td><td>87.38</td><td>92.35</td><td>93.83</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E†</td><td>88.49</td><td>93.16</td><td>94.32</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD†</td><td>88.68</td><td>92.97</td><td>94.75</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2†</td><td>88.78</td><td>93.33</td><td>94.48</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-P</td><td>84.15</td><td>89.44</td><td>92.84</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/ KD</td><td>84.77</td><td>90.12</td><td>92.91</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/KD2</td><td>85.43</td><td>90.64</td><td>93.20</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P†</td><td>88.57</td><td>93.15</td><td>94.42</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD†</td><td>88.94</td><td>93.25</td><td>94.77</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD2†</td><td>89.33</td><td>93.78</td><td>94.68</td><td>14.87</td><td>2.70</td></tr></table>
[表格脚注]
  T-224:Teacher model with $2 2 4 \times 2 2 4$ input size. T-512: Teacher model with $5 1 2 \times 5 1 2$ input size. w/:with. $\mathrm { K D } _ { 1 }$ :Knowledge distillation from T-224. $\mathrm { K D } _ { 2 }$ ：Knowledge distillation from T-512. $^ \dagger$ ：Backbone network was pretrained in ImageNet-1K. 
```

#### Element #99 — `element-6c71d0ea-1192-405e-b8c9-f8064af2aa01`

- **type**: table
- **page_index**: 9
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 4 Performance comparison between FastSegFormer and other lightweight models. 
[表格内容]
<table><tr><td>Model</td><td>Backbone</td><td>mIoU (%)</td><td>Params(M)</td><td>GFLOPs</td><td>FPS (RTX 3060)</td></tr><tr><td>FANet-18 †</td><td>ResNet-18</td><td>67.41</td><td>13.65</td><td>1.16</td><td>168</td></tr><tr><td>FANet-34†</td><td>ResNet-34</td><td>69.22</td><td>23.75</td><td>1.64</td><td>120</td></tr><tr><td>PIDNet-S Seg†</td><td>PIDNet-S</td><td>75.09</td><td>7.62</td><td>1.15</td><td>84</td></tr><tr><td>PIDNet-M Seg †</td><td>PIDNet-M</td><td>75.97</td><td>28.54</td><td>4.30</td><td>82</td></tr><tr><td>PIDNet-L Seg †</td><td>PIDNet-L</td><td>75.13</td><td>36.93</td><td>6.63</td><td>69</td></tr><tr><td>SwiftNet †</td><td>ResNet-18</td><td>78.69</td><td>11.79</td><td>2.49</td><td>242</td></tr><tr><td>Fast-SCNN</td><td>~</td><td>79.15</td><td>1.14</td><td>0.17</td><td>189</td></tr><tr><td>BiSeNet †</td><td>ResNet-18</td><td>82.37</td><td>13.23</td><td>2.84</td><td>193</td></tr><tr><td>ENet</td><td>~</td><td>85.63</td><td>0.36</td><td>0.46</td><td>71</td></tr><tr><td>FastSegFormer-E(ours) †</td><td>EfficientFormerV2-S0</td><td>88.78</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P(ours) †</td><td>PoolFormer-S12</td><td>89.33</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
[表格脚注]
  +: Backbone network pretrained in ImageNet-1K. 
```

#### Element #100 — `element-1160af36-f9a3-4032-816a-a8e5184631dd`

- **type**: text
- **page_index**: 9
- **element_index**: 2

**文本内容**

```
3.3.Segmentation results of diferent models on the test set 
```

#### Element #101 — `element-eb257ad4-20ca-4e10-a654-50674d13f122`

- **type**: text
- **page_index**: 9
- **element_index**: 3

**文本内容**

```
Results of the partial model for segmenting partial navel orange picture defects on the test set are shown in Fig.11.As seen in Fig.11, the FastSegFormer model can successfully segment defects in the challenging scenario of a simulated picking line scene.The segmentation outcome is quite similar to the label and recovers some label information. The results of Image I-III show that, in comparison to other models,the FastSegFormer model can differentiate the margins of small defects,more precisely segment wind scarring defects with complicated geometries,and distinguish similar defects.FastSegFormer still distinguishes minor defects better in Figure IV's blurred image.Figure V shows that all models have a similar capacity for segmenting defects for larger targets. 
```

#### Element #102 — `element-ad09b84f-71ac-4706-aba0-b03d51eb8130`

- **type**: text
- **page_index**: 9
- **element_index**: 4

**文本内容**

```
3.4.Defect detection system deployment 
```

#### Element #103 — `element-d0c5674a-8d90-4567-a115-df47b6b1b4d9`

- **type**: text
- **page_index**: 9
- **element_index**: 5

**文本内容**

```
To simulate the environment of an industrial picking line,which is expensive to deploy algorithms in,we used an edge computing device similar to it. Through Jiangxi Reemoon Technology Company, we learned that NVIDIA's Jetson platform is used for fruit industrial pipeline defect detection while using TensorRT hardware acceleration and DeepStream video stream processing framework.We used the platform's entry-level device,the Jetson Nano (4G),to deploy the navel orange defect detection system and tested the speed of detection,and we also deployed the system on the device used for training as a comparison. 
```

#### Element #104 — `element-7309d467-b6c1-448a-b735-cc8ffff579b8`

- **type**: text
- **page_index**: 9
- **element_index**: 6

**文本内容**

```
3.4.1. Deployment setup 
```

#### Element #105 — `element-b5b232b7-38c9-4663-8b7f-a4f6ffad9b61`

- **type**: text
- **page_index**: 9
- **element_index**: 7

**文本内容**

```
The system is deployed in the Ubuntu 18.04 environment using CUDA10.2, TensorRT 8.2,and DeepStream 6.0.1. Jetson Nano (4G) is equipped with an NVIDIA Maxwell GPU and ARM Cortex-A57MPCore processor with 4 GB of shared CPU and GPU memory.We converted the trained model files into ONNX files usingPython scripts and built TensorRT model serialization files for accelerated inference based on the Jetson Nano's hardware.The system additionally used the DeepStream video processing framework, which is paired with TensorRT technology and can only be used on NVIDIA's Jetson platform.As a comparison, the system is also deployed on the PC used for training the model,and the configuration information is given in Section 2.6.2. 
```

#### Element #106 — `element-a6d5db8f-0e5f-4908-983e-532ce95d575a`

- **type**: image
- **page_index**: 10
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig.9.Plotofperformanceagastiferencespeedofeachlgtweigtodel.FSiscalculatedontheGUX306witniputotif $2 2 4 \times 2 2 4$ 
```

#### Element #107 — `element-dbda2bb3-f890-4c73-b010-599479a890d9`

- **type**: image
- **page_index**: 10
- **element_index**: 1

**图片描述**

```
[图片标题]
  Fig.10.Plot of performance against parameters of each lightweight model. 
```

#### Element #108 — `element-bae3509e-e07f-4611-a2f9-4a5dfbddf4f6`

- **type**: text
- **page_index**: 10
- **element_index**: 2

**文本内容**

```
3.4.2. Detection speed 
```

#### Element #109 — `element-3d3d6b4f-b41d-4c01-af88-23e0bf626d44`

- **type**: text
- **page_index**: 10
- **element_index**: 3

**文本内容**

```
The detection latency of a single image determines the detection speed of the system，which includes pre-processing latency,model inference latency,and post-processing latency. Pre-processing includes image size conversion，image type conversion，etc. Post-processing time delay includes marking defect location,image size conversion, image stitching,etc.Therefore,the actual detection speed of the system is much smaller than the inference speed alone.Table 5 shows the detection speed of the system under different platforms. Using Deep-Stream,TensorRT,and semi-precision quantization techniques on a Jetson Nano device,our algorithmic detection system achieves nearly half the detection speed on a PC using only 1/27 of the PC computing power. The Jetson platform's uniform deployment framework has greatly amplified scalability, harnessing the robust capabilities of advanced Jetson devices to deliver remarkable detection rates.Within the commercial sector, the Jetson lineup,particularly the acclaimed Jetson Xavier NX,is the go-to for its extraordinary computational power.Furthermore,this highlights the adaptability and eficiency of the proposed algorithm,capable of facilitating real-time detection across diverse assembly line sorting operations. 
```

#### Element #110 — `element-16ced88a-a6cf-4e82-8ab4-09b76aec6d1c`

- **type**: text
- **page_index**: 10
- **element_index**: 4

**文本内容**

```
4.Discussion 
```

#### Element #111 — `element-366678d7-fe75-43c9-8e3c-716ef0b834d8`

- **type**: text
- **page_index**: 10
- **element_index**: 5

**文本内容**

```
4.1. Comparison with related work 
```

#### Element #112 — `element-94247e70-7a18-4cb5-b842-1718ab177185`

- **type**: text
- **page_index**: 10
- **element_index**: 6

**文本内容**

```
Table 6 compares our work with some already existing research work on fruit defect segmentation.Please take note that we retested portions of the work's speed using the RTX3o6O graphics card,and the details are consistent with the original paper.While the classification accuracy of traditional picture segmentation algorithms is quite high, the segmentation accuracy is low and the processing time delay is considerable (Rong et al., 2017a,b). Sun et al. (2020) only takes into account the segmentation performance of the model, and it is challenging to use the study's findings for extensive navel orange defect identification. To balance segmentation performance and inference speed, Liang et al.(2022) employs a lightweight detection network to assist with the lightweight segmentation network. Compared to conventional segmentation methods,the current study's scene application versatility is better,and its segmentation capability is more powerful and quick. It 
```

#### Element #113 — `element-bb8e79c8-0105-48ba-a3d8-9480c4aa0acc`

- **type**: image
- **page_index**: 11
- **element_index**: 0

**图片描述**

```
[图片标题]
  Fig (c) PIDNet-M.(d) BiSeNet.(e) ENet.(f) FastSegFormer-P (ours). 
```

#### Element #114 — `element-b335feac-a529-46fa-95f7-a5b2785dde19`

- **type**: table
- **page_index**: 11
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 5 Comparison of the detection speed of Jetson Nano and RTX3060. 
[表格内容]
<table><tr><td>Device</td><td>Video input</td><td>Inference input</td><td>Acceleration</td><td>Data type</td><td>Compute (TFLOPs)</td><td>Speed (FPS)</td></tr><tr><td>RTX3060</td><td>1920 × 1080</td><td>224× 224</td><td>~</td><td>FP32</td><td>12.74</td><td>33</td></tr><tr><td>RTX3060</td><td>1920×1080</td><td>224× 224</td><td>Multithreading</td><td>FP32</td><td>12.74</td><td>47</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>~</td><td>FP16</td><td>0.47</td><td>8</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>TensorRT</td><td>FP16</td><td>0.47</td><td>12</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224×224</td><td>DeepStream</td><td>FP16</td><td>0.47</td><td>20</td></tr></table>
[表格脚注]
  FP32:Inference with single-precision floating-point number. FP16:Inference with half-precision floating-point number. $\sim$ Inference with ONNXRuntime and do not use accelerations. Note:DeepStream includes TensorRT acceleration. 
```

#### Element #115 — `element-3ea59d16-a9af-4f9f-8f40-d945c8a25a8c`

- **type**: table
- **page_index**: 12
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 6 Performance of FastSegFormer and related works. 
[表格内容]
<table><tr><td rowspan="2">Work</td><td rowspan="2">Task</td><td rowspan="2">Detailed description</td><td colspan="3">Metrics</td></tr><tr><td>Accuracy (%)</td><td>mIoU (%)</td><td>Inference time (ms)</td></tr><tr><td>Rong et al. (2017a)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using means of sliding window local segmentation algorithm.</td><td>97</td><td>~</td><td>~</td></tr><tr><td>Rong et al. (2017b)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using fast adaptive lightness correction algorithm.</td><td>95.7</td><td>~</td><td>30</td></tr><tr><td rowspan="3">Sun et al. (2020)</td><td rowspan="3">Semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3">~</td><td rowspan="3">70.38</td><td rowspan="3">~</td></tr><tr><td>using FA-Net Input: 288 × 288</td></tr><tr><td>Number of pixel classification categories: 5</td></tr><tr><td rowspan="3">Liang et al. (2022)</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on apples using</td><td rowspan="3"></td><td rowspan="3">80.46</td><td rowspan="3">16.99(RTX3060)*</td></tr><tr><td>BiSeNetV2 with pruned YOLOv4 assisted.</td></tr><tr><td>Input: 416 × 416 Number of pixel classification categories: 3</td></tr><tr><td rowspan="3">Current work</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3"></td><td rowspan="3">89.33</td><td rowspan="3">9.26(RTX3060)</td></tr><tr><td>using FastSegFormer-P.</td></tr><tr><td>Input: 224× 224 Number of pixel classification categories: 4</td></tr></table>
[表格脚注]
  \~:Not applicable or not mentioned in the original paper. \*:Results of testing on our equipment according to the original details. 
```

#### Element #116 — `element-0eb58832-d322-4345-aa2a-896b9d903478`

- **type**: text
- **page_index**: 12
- **element_index**: 1

**文本内容**

```
provides advantages in terms of the combination of accuracy and speed compared to other segmentation models. 
```

#### Element #117 — `element-db2cf921-f175-4411-a774-f6fcbadfa27e`

- **type**: text
- **page_index**: 12
- **element_index**: 2

**文本内容**

```
4.2.Future research 
```

#### Element #118 — `element-cd21e7f8-355c-4789-89a4-03a2dbbea227`

- **type**: text
- **page_index**: 12
- **element_index**: 3

**文本内容**

```
Real-time defect identification is made possible by the FastSeg-Former model's precise defect detection capabilities and a good balance of accuracy and speed.The model is highly generalizable and has good adaptability when mimicking the intricate circumstances of a mock sorting line.Our model was able to achieve 1o8 frames/s at the mid-end GPU RTX306O with the present input resolution.The bloated backbone network is the reason why,as the image resolution gradually rises,the calculation of the model increases.We will think about either constructing a more effective backbone network or trimming the backbone network in terms of channels and depth to accommodate high-resolution inputs. This will speed up inference and save training resources by eliminating the dependence on pre-training resources of the ImageNet-1K dataset. 
```

#### Element #119 — `element-3f5308c9-e82b-4389-b4af-03f7ca2a13a8`

- **type**: text
- **page_index**: 12
- **element_index**: 4

**文本内容**

```
The advantage of a defect detection session taking place after harvesting is that it allows for quick identification in big volumes.However，when intelligent picking robots advance,the defect detection and picking segments will be merged.Future research will focus on segmenting and categorizing whole fruits with defects and whole fruits without defects in the orchard scene map,which is currently quite challenging. However,when new deep-learning training techniques, such as prompt engineering,are suggested, this challenge will gradually be addressed.The SAM model presents two innovative strategies for enhancing our approach to dataset annotation and model training (Kirillov et al., 2023). The first strategy focuses on streamlining the segmentation dataset annotation process through point cueing techniques,which are designed to guarantee precision and richness in the dataset details.The second strategy involves the integration of textual cues during the training process,enabling the model to dynamically adjust to the fluctuating lighting and climatic conditions encountered within orchard environments.These textual cues serve as a guide for the model, fostering an adaptable classification system responsive to a spectrum of environmental inputs. 
```

#### Element #120 — `element-7205ef15-d416-45c7-8781-af83714e959b`

- **type**: text
- **page_index**: 12
- **element_index**: 5

**文本内容**

```
5.Conclusion 
```

#### Element #121 — `element-27ec0b71-8657-4a63-b86f-92cb1ec717c0`

- **type**: text
- **page_index**: 12
- **element_index**: 6

**文本内容**

```
In this paper，we developed two segmentation models called FastSegFormer-E and FastSegFormer-P to quickly identify defects in big batches of navel oranges.To rebuild image detail for the deep network,we created the MSP module and added a semi-resolution image reconstruction branch following feature fusion.Our models are effective in identifying lesser defects and precisely segmenting complex edge defects in real-world complex settings.The segmentation accuracy of the model was further enhanced by the suggested multi-resolution knowledge distillation strategy without increasing model size and inference time.The proposed FastSegFormer-E achieves superior defect detection accuracy while maintaining low memory consumption, while the proposed FastSegFormer-P achieves the highest defect detection accuracy with high inference speed.The FastSegFormer-P model achieves a detection speed of 2O fps on a very low computing power device under the Jetson platform, suggesting that deploying the algorithm is very easy to achieve real-time detection.The proposed algorithm effectively overcomes the limitations of current commonly used methods in meeting the demands of precise sorting.Additionally,it successfully addresses the crucial requirement of real-time detection,an aspect where many existing segmentation algorithms for fruit defect detection fall short.Incorporating a smaller and faster backbone into the proposed network will enhance its ability to handle image inputs of various resolutions. Defect detection will be performed at the harvesting stage in the future,where the algorithm's adaptation to partial leaf occlusion becomes crucial. 
```

#### Element #122 — `element-2d42dbe5-924c-4dac-955b-94b3355dc504`

- **type**: text
- **page_index**: 12
- **element_index**: 7

**文本内容**

```
CRediT authorship contribution statement 
```

#### Element #123 — `element-8b5cc40b-5c00-4810-bdf5-40013e4f5bf6`

- **type**: text
- **page_index**: 12
- **element_index**: 8

**文本内容**

```
Xiongjiang Cai: Writing-review& editing,Writing-original draft, Visualization，Validation,Software,Project administration,Methodology,Investigation,Formal analysis,Data curation,Conceptualization. Yun Zhu: Supervision, Resources, Project administration, Funding acquisition,Formal analysis,Data curation.Shuwen Liu: Supervision,Software,Resources,Project administration, Investigation,Data curation.Zhiyue Yu: Supervision,Software,Project administration, Data curation. Youyun Xu: Resources, Project administration, Funding acquisition, Conceptualization. 
```

#### Element #124 — `element-9ec971fa-ac17-43c2-af80-7a5548b11ac0`

- **type**: text
- **page_index**: 13
- **element_index**: 0

**文本内容**

```
Declaration of competing interest 
```

#### Element #125 — `element-0e620d15-4ec0-44fe-a92c-f1bff23d47f2`

- **type**: text
- **page_index**: 13
- **element_index**: 1

**文本内容**

```
The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper. 
```

#### Element #126 — `element-67c2e549-3d61-41db-8543-c65cf43a1870`

- **type**: text
- **page_index**: 13
- **element_index**: 2

**文本内容**

```
Data availability 
```

#### Element #127 — `element-498d992f-6122-4c87-afce-23dab36a8780`

- **type**: text
- **page_index**: 13
- **element_index**: 3

**文本内容**

```
The data and code can be available in https://github.com/caix iongjiang/FastSegFormer. Code on edge computing device deployment and detection systems on PCs is available in https://github.com/ caixiongjiang/FastSegFormer-pyqt. 
```

#### Element #128 — `element-a36eef8d-3171-483e-81d9-5cc719e53f89`

- **type**: text
- **page_index**: 13
- **element_index**: 4

**文本内容**

```
Acknowledgments 
```

#### Element #129 — `element-5fd779b0-60f2-4420-81e2-afa71ac9724d`

- **type**: text
- **page_index**: 13
- **element_index**: 5

**文本内容**

```
This work was financially supported by the Key Research and Development Programs of Jiangxi Province (No.006124253059 and No. 006124252054). 
```

#### Element #130 — `element-82a60c2f-ce87-4ade-83a6-42de73c32c37`

- **type**: text
- **page_index**: 13
- **element_index**: 6

**文本内容**

```
References 
```

#### Element #131 — `element-4f953635-b6a9-45b5-ab38-94bdc5123bb4`

- **type**: text
- **page_index**: 13
- **element_index**: 7

**文本内容**

```
Allwood，J.W.，Gibon，Y.，Osorio，S.，Araujo，W.L.，Valarino，J.G.，Pétriacq，P., Moing, A., 2021. Developmental metabolomics to decipher and improve fleshy fruit quality. In: Advances in Botanical Research. Vol. 98. Elsevier, pp. 3-34.   
Azizah,L.M.， Umayah，S.F.，Riyadi， S.， Damarjati， C.， Utama, N.A.， 2017.Deep learning implementation using convolutional neural network in mangosteen surface defect detection. In: 2017 7th IEEE International Conference on Control System, Computing and Engineering. ICCSCE, IEEE, pp. 242-246.   
De Luna，R.G.，Dadios，E.P.，Bandala,A.A.，Vicerra，R.R.P.，2019. Tomato fruit image dataset for deep transfer learning-based defect detection. In: 2O19 IEEE International Conference on Cybernetics and Intelligent Systems (CIS) and IEEE Conference on Robotics, Automation and Mechatronics (RAM). IEEE, pp. 356-361.   
Dosovitskiy,A.,Beyer,L.,Kolesnikov,A.,Weissenborn,D., Zhai, X., Unterthiner,T., Dehghani,M.,Minderer,M.,Heigold,G.,Gelly,S.,et al.,2020.An image is worth 16xl6 words: Transformers for image recognition at scale.arXiv preprint arXiv:2010.11929.   
Fan, S., Liang, X.,Huang,W., Zhang, V.J., Pang, Q., He, X.,Li, L., Zhang, C., 2022. Real-time defects detection for apple sorting using NIR cameras with pruning-based YOLOV4 network. Comput. Electron. Agric. 193, 106715.   
Heo,B.，Kim,J.,Yun, S.，Park，H.，Kwak，N.,Choi,J.Y.，2019. A comprehensive overhaul of feature distillation. In: Proceedings of the IEEE/CVF International Conference on Computer Vision. pp. 1921-1930.   
Hinton,G.,Vinyals,O.,Dean,J.,2015.Distilling the knowledge in a neural network. arXiv preprint arXiv:1503.02531.   
Holder, C.J., Shafique,M.,2022. On efficient real-time semantic segmentation: a survey. arXiv preprint arXiv:2206.08605.   
Hou,J., Liang,L.,Wang, Y.， 2O2o.Volatile composition changes in navel orange at different growth stages by HS-SPME-GC-MS. Food Res.Int.136,109333.   
Ismail,N., Malik, O.A., 2022. Real-time visual inspection system for grading fruits sing computer vision and deep learning techniques. Inf. Process. Agricult. 9 (1), 24-37.   
Kirillov,A.，Mintun,E.，Ravi,N.，Mao,H.，Rolland,C.，Gustafson,L.，Xiao,T., Whitehead,S.,Berg,A.C.,Lo,W.-Y.,etal.,2023.Segment anything.arXiv preprint arXiv:2304.02643.   
Li,Y.,Hu,J.,Wen,Y.,Evangelidis,G.,Salahi,K.,Wang,Y.,Tulyakov,S.,Ren,J., 2022.Rethinking vision transformers for MobileNet size and speed.arXiv preprint arXiv:2212.08059.   
Liang, X., Jia, X.,Huang,W., He, X.,Li,L.,Fan, S., Li, J., Zhao, C., Zhang, C., 2022. Real-time grading of defect apples using semantic segmentation combination with a pruned YOLO V4 network. Foods 11 (19), 3150.   
Liu,Y.，Chen，K.,Liu,C.,Qin，Z., Luo，Z.，Wang,J.，2019. Structured knowledge distillation for semantic segmentation. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp. 2604-2613.   
Liu, Z.,Lin, Y.， Cao, Y.， Hu, H,Wei, Y.， Zhang,Z., Lin,S.,Guo, B.， 2021. Swin transformer: Hierarchical vision transformer using shifted windows. In: Proceedings of the IEEE/CVF International Conference on Computer Vision. pp.10012-10022.   
Liu,T.，Yang，X.，Chen,C.，2022．Normalized feature distillation for semantic segmentation. arXiv preprint arXiv:2207.05256.   
Nithya,R., Santhi, B.， Manikandan,R., Rahimi, M., Gandomi, A.H., 2022. Computer vision system for mango fruit defect detection using deep convolutional neural network. Foods 11 (21), 3483.   
Oktay,O.,Schlemper,J.,Folgoc,L.L.,Lee,M.,Heinrich,M.,Misawa,K.,Mori,K., McDonagh,S.ammerla,N.Y.,ainz,B.tal.8.Atentionu-netLearing where to look for the pancreas.arXiv preprint arXiv:1804.03999.   
Orsic,M., Kreso,L,Bevandic,P. Segvic,S., 2019.In defense of pre-trained imagenet architectures for real-time semantic segmentation of road-driving images. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp.12607-12616.   
Paszke,A., Chaurasia,A., Kim, S.,Culurciello,E.,2Ol6. Enet: A deep neural network architecture for real-time semantic segmentation.arXiv preprint arXiv:l6o6.02147.   
Poudel,R.P., Liwicki,S., Cipolla,R., 2019.Fast-SCNN: Fast semantic segmentation network. arXiv preprint arXiv:1902.04502.   
Rong,D.，Rao, X.， Ying, Y.， 2O17a. Computer vision detection of surface defect on oranges by means of a sliding comparison window local segmentation algorithm. Comput. Electron. Agric.137, 59-68.   
Rong, D., Ying, Y.,Rao, X., 2017b. Embedded vision detection of defective orange by fast adaptive lightness correction algorithm. Comput. Electron. Agric.138, 48-59.   
Ronneberger, O., Fischer, P., Brox, T., 2015. U-net: Convolutional networks for biomedical image segmentation. In: Medical Image Computing and Computer-Assisted Intervention-MICCAI 2015:18th International Conference,Munich， Germany, October 5-9,2015, Proceedings,Part I Vol.18.Springer, pp.234-241.   
Roy, K., Chaudhuri, S.S., Pramanik, S., 2021. Deep learning based real-time industrial framework for roten and fresh fruit detection using semantic segmentation. Microsyst. Technol. 27, 3365-3375.   
Sandler,M.， Howard,A., Zhu， M.， Zhmoginov,A., Chen, L.-C.，2018.Mobilenetv2: Inverted residuals and linear bottlenecks.In: Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. pp. 4510-4520.   
Sifre,L.，Mallat, S.,2o14.Rigid-motion scattering for texture classification.arXiv preprint arXiv:1403.1687.   
Soltani Firouz, M., Sardari, H.,2022.Defect detection in fruit and vegetables by using machine vision systems and image processing. Food Eng. Rev. 14 (3), 353-379.   
Sun,X.，Li,G.，Xu，S.，202O．Fastidious attention network for navel orange segmentation.arXiv preprint arXiv:2003.11734.   
Tripathi, M.K., Maktedar, D.D., 2020.A role of computer vision in fruits and vegetables among various horticulture products of agriculture fields: A survey. Inf. Process. Agricult. 7 (2), 183-203.   
Wang,H., Cao, P.,Wang, J., Zaiane, O.R., 2022. Uctransnet: rethinking the skip connections in u-net from a channel-wise perspective with transformer. In: Proceedings of the AAAI Conference on Artificial Intelligence. Vol. 36.No.3. pp. 2441-2449.   
Wang，H.，Mou, Q.，Yue,Y.， Zhao,H.,2020.Research on detection technology of various fruit disease spots based on mask R-CNN. In: 2O2O IEEE International Conference on Mechatronics and Automation. ICMA, IEEE, pp.1083-1087.   
Xiang，Z.，Chen，X.,Qian,C.，He,K.，Xiao，X.，2020.Determination of volatile flavors in fresh navel orange by multidimensional gas chromatography quadrupole time-of-flight mass spectrometry. Anal. Lett. 53 (4), 614-626.   
Yao,J., Qi,J., Zhang,J.,Shao,H., Yang,J.,Li, X.,2021. A real-time detection algrithm for Kiwifruit defects based on YOLOv5. Electronics 10 (14), 1711.   
Yu,W.,Luo,M., Zhou, P., Si, C., Zhou, Y.,Wang, X., Feng, J.,Yan, S., 2022. Metaformer is actually what you need for vision. In: Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. pp. 10819-10829.   
Yu,C.，Wang，J.，Peng，C.，Gao，C.，Yu，G.，Sang，N.，2018.Bisenet: Bilateral segmentation network for real-time semantic segmentation. In: Proceedings of the European Conference on Computer Vision. ECCV, pp.325-341.   
Zhao,H., Shi, J., Qi, X.,Wang, X., Jia, J., 2017. Pyramid scene parsing network. In: Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. pp. 2881-2890. 
```

### 2.4 Section → Chunk（Section: `section-0d1df367-e998-4cf3-b27b-103b4e8ecb6e`）

- **返回数量**: 0
- **耗时**: 3.0ms

### 2.5 Chunk → Element（Chunk: `chunk-03e812b7-f087-478f-903c-642002f8c97c`）

- **返回数量**: 1
- **耗时**: 6.5ms

#### Element #1 — `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`

- **type**: text
- **page_index**: 8
- **element_index**: 2

**文本内容**

```
demonstrate that overly high NFD distillation losses substantially diminish accuracy,whereas the impact of excessive logits distillation losses appears to be less detrimental. This discrepancy arises because a distillation loss that is too large for intermediate feature maps can rapidly deteriorate the representational information derived from the pre-training weights.On the other hand,logits positioned at the output of the model have a relatively lesser impact in this regard.For the FastSegFormer-E model,when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5 .$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 7 5$ ,as indicated by the red broken line.For the FastSegFormer-P model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 5$ ,as indicated by the green broken line.In conclusion,after careful evaluation,we have selected $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ as the definitive weights for our model. 
```

### 2.6 Document → Element（仅 TABLE 类型）

- **返回数量**: 6
- **耗时**: 10.1ms

#### Element #1 — `element-3d13cae9-22bd-4238-ae49-51ebb4959d0e`

- **type**: table
- **page_index**: 8
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 1 Segmentic performance of different models in the model structure ablation study. 
[表格内容]
<table><tr><td rowspan="2">Model</td><td rowspan="2">mIoU (%)</td><td rowspan="2">mPA (%)</td><td colspan="4">IoU (%)</td></tr><tr><td>Background</td><td>Sunburn</td><td>Ulcer</td><td>Wind scarring</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB +W/PPM OD</td><td>79.84</td><td>85.12</td><td>98.93</td><td>83.19</td><td>77.28</td><td>60.34</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM ED</td><td>81.93</td><td>87.34</td><td>99.00</td><td>86.09</td><td>79.30</td><td>63.32</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† OD</td><td>82.74</td><td>88.32</td><td>99.03</td><td>87.76</td><td>79.88</td><td>65.43</td></tr><tr><td>FastSegFormer-E +</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/PPM† ED</td><td>83.01</td><td>88.97</td><td>98.99</td><td>88.05</td><td>79.91</td><td>65.10</td></tr><tr><td>FastSegFormer-E+</td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>83.88</td><td>89.73</td><td>99.05</td><td>88.17</td><td>80.11</td><td>68.17</td></tr><tr><td>FastSegFormer-E(ours) †ED</td><td>88.49</td><td>93.16</td><td>99.35</td><td>89.29</td><td>87.40</td><td></td></tr><tr><td>FastSegFormer-P+</td><td></td><td></td><td></td><td></td><td></td><td>77.94</td></tr><tr><td>W/o IRB+W/ PPM OD</td><td>79.21</td><td>84.88</td><td>98.89</td><td>82.37</td><td>74.53</td><td></td></tr><tr><td>FastSegFormer-P +</td><td></td><td></td><td></td><td></td><td></td><td>59.89</td></tr><tr><td>W/o IRB+W/PPM ED</td><td>80.03</td><td>86.25</td><td>98.96</td><td>82.26</td><td>78.16</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>60.74</td></tr><tr><td>FastSegFormer-P + W/o IRB+W/PPM†OD</td><td>82.46</td><td>88.01</td><td>99.00</td><td>85.77</td><td>79.35</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.18</td></tr><tr><td>FastSegFormer-P + W/o IRB+ W/ PPM†ED</td><td>84.29</td><td>89.91</td><td>99.07</td><td>88.34</td><td>81.07</td><td></td></tr><tr><td></td><td></td><td></td><td></td><td></td><td></td><td>68.67</td></tr><tr><td>FastSegFormer-P+</td><td></td><td>90.80</td><td></td><td></td><td></td><td></td></tr><tr><td>W/o IRB+W/MSP†ED</td><td>84.96</td><td></td><td>99.11</td><td>88.53</td><td>81.98</td><td>70.22</td></tr><tr><td>FastSegFormer-P(ours) † ED</td><td>88.57</td><td>93.15</td><td>99.35</td><td>89.34</td><td>87.50</td><td>78.09</td></tr></table>
[表格脚注]
  w/o:without.w/:with. IRB: Image reconstruction branch. †:Backbone network was pretrained in ImageNet-1K. OD: Original Datasets.ED:Enhanced Datasets. 
```

#### Element #2 — `element-1a43dca9-484c-45ce-b6cf-f3c9155ebea4`

- **type**: table
- **page_index**: 8
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 2 Deployment performance of different models in the model structure ablation study. 
[表格内容]
<table><tr><td>Model</td><td>Params(M)</td><td>GFLOPs</td><td>RTX3060 Speed(FPS)</td></tr><tr><td>FastSegFormer-E+W/o IRB+W/PPM</td><td>4.48</td><td>0.71</td><td>64</td></tr><tr><td>FastSegFormer-E +W/o IRB+W/MSP</td><td>5.00</td><td>0.74</td><td>62</td></tr><tr><td>FastSegFormer-E(ours)</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/PPM</td><td>13.53</td><td>2.56</td><td>117</td></tr><tr><td>FastSegFormer-P+W/o IRB+W/MSP</td><td>14.85</td><td>2.63</td><td>112</td></tr><tr><td>FastSegFormer-P(ours)</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
[表格脚注]
  w/o:without. w/: with. IRB:Image reconstruction branch. 
```

#### Element #3 — `element-3427ce8f-774a-4e23-8f81-19deb7e71cfc`

- **type**: table
- **page_index**: 9
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 3 Knowledge distillation and fine-tuning for ablation study. 
[表格内容]
<table><tr><td>Model</td><td>mIoU (%)</td><td>mPA (%)</td><td>mPrecison (%)</td><td>Params(M)</td><td>GFLOPs</td></tr><tr><td>Swin-T-Att-UNet (T-224) †</td><td>89.73</td><td>94.08</td><td>94.85</td><td>49.21</td><td>14.52</td></tr><tr><td>Swin-T-Att-UNet (T-512) †</td><td>90.53</td><td>94.65</td><td>95.20</td><td>49.21</td><td>77.80</td></tr><tr><td>FastSegFormer-E</td><td>86.51</td><td>91.63</td><td>93.53</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD</td><td>87.24</td><td>92.20</td><td>93.82</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2</td><td>87.38</td><td>92.35</td><td>93.83</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E†</td><td>88.49</td><td>93.16</td><td>94.32</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-Ew/KD†</td><td>88.68</td><td>92.97</td><td>94.75</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-E w/KD2†</td><td>88.78</td><td>93.33</td><td>94.48</td><td>5.01</td><td>0.80</td></tr><tr><td>FastSegFormer-P</td><td>84.15</td><td>89.44</td><td>92.84</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/ KD</td><td>84.77</td><td>90.12</td><td>92.91</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P w/KD2</td><td>85.43</td><td>90.64</td><td>93.20</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-P†</td><td>88.57</td><td>93.15</td><td>94.42</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD†</td><td>88.94</td><td>93.25</td><td>94.77</td><td>14.87</td><td>2.70</td></tr><tr><td>FastSegFormer-Pw/KD2†</td><td>89.33</td><td>93.78</td><td>94.68</td><td>14.87</td><td>2.70</td></tr></table>
[表格脚注]
  T-224:Teacher model with $2 2 4 \times 2 2 4$ input size. T-512: Teacher model with $5 1 2 \times 5 1 2$ input size. w/:with. $\mathrm { K D } _ { 1 }$ :Knowledge distillation from T-224. $\mathrm { K D } _ { 2 }$ ：Knowledge distillation from T-512. $^ \dagger$ ：Backbone network was pretrained in ImageNet-1K. 
```

#### Element #4 — `element-6c71d0ea-1192-405e-b8c9-f8064af2aa01`

- **type**: table
- **page_index**: 9
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 4 Performance comparison between FastSegFormer and other lightweight models. 
[表格内容]
<table><tr><td>Model</td><td>Backbone</td><td>mIoU (%)</td><td>Params(M)</td><td>GFLOPs</td><td>FPS (RTX 3060)</td></tr><tr><td>FANet-18 †</td><td>ResNet-18</td><td>67.41</td><td>13.65</td><td>1.16</td><td>168</td></tr><tr><td>FANet-34†</td><td>ResNet-34</td><td>69.22</td><td>23.75</td><td>1.64</td><td>120</td></tr><tr><td>PIDNet-S Seg†</td><td>PIDNet-S</td><td>75.09</td><td>7.62</td><td>1.15</td><td>84</td></tr><tr><td>PIDNet-M Seg †</td><td>PIDNet-M</td><td>75.97</td><td>28.54</td><td>4.30</td><td>82</td></tr><tr><td>PIDNet-L Seg †</td><td>PIDNet-L</td><td>75.13</td><td>36.93</td><td>6.63</td><td>69</td></tr><tr><td>SwiftNet †</td><td>ResNet-18</td><td>78.69</td><td>11.79</td><td>2.49</td><td>242</td></tr><tr><td>Fast-SCNN</td><td>~</td><td>79.15</td><td>1.14</td><td>0.17</td><td>189</td></tr><tr><td>BiSeNet †</td><td>ResNet-18</td><td>82.37</td><td>13.23</td><td>2.84</td><td>193</td></tr><tr><td>ENet</td><td>~</td><td>85.63</td><td>0.36</td><td>0.46</td><td>71</td></tr><tr><td>FastSegFormer-E(ours) †</td><td>EfficientFormerV2-S0</td><td>88.78</td><td>5.01</td><td>0.80</td><td>61</td></tr><tr><td>FastSegFormer-P(ours) †</td><td>PoolFormer-S12</td><td>89.33</td><td>14.87</td><td>2.70</td><td>108</td></tr></table>
[表格脚注]
  +: Backbone network pretrained in ImageNet-1K. 
```

#### Element #5 — `element-b335feac-a529-46fa-95f7-a5b2785dde19`

- **type**: table
- **page_index**: 11
- **element_index**: 1

**表格内容**

```
[表格标题]
  Table 5 Comparison of the detection speed of Jetson Nano and RTX3060. 
[表格内容]
<table><tr><td>Device</td><td>Video input</td><td>Inference input</td><td>Acceleration</td><td>Data type</td><td>Compute (TFLOPs)</td><td>Speed (FPS)</td></tr><tr><td>RTX3060</td><td>1920 × 1080</td><td>224× 224</td><td>~</td><td>FP32</td><td>12.74</td><td>33</td></tr><tr><td>RTX3060</td><td>1920×1080</td><td>224× 224</td><td>Multithreading</td><td>FP32</td><td>12.74</td><td>47</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>~</td><td>FP16</td><td>0.47</td><td>8</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224× 224</td><td>TensorRT</td><td>FP16</td><td>0.47</td><td>12</td></tr><tr><td>Jetson Nano</td><td>1280 × 720</td><td>224×224</td><td>DeepStream</td><td>FP16</td><td>0.47</td><td>20</td></tr></table>
[表格脚注]
  FP32:Inference with single-precision floating-point number. FP16:Inference with half-precision floating-point number. $\sim$ Inference with ONNXRuntime and do not use accelerations. Note:DeepStream includes TensorRT acceleration. 
```

#### Element #6 — `element-3ea59d16-a9af-4f9f-8f40-d945c8a25a8c`

- **type**: table
- **page_index**: 12
- **element_index**: 0

**表格内容**

```
[表格标题]
  Table 6 Performance of FastSegFormer and related works. 
[表格内容]
<table><tr><td rowspan="2">Work</td><td rowspan="2">Task</td><td rowspan="2">Detailed description</td><td colspan="3">Metrics</td></tr><tr><td>Accuracy (%)</td><td>mIoU (%)</td><td>Inference time (ms)</td></tr><tr><td>Rong et al. (2017a)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using means of sliding window local segmentation algorithm.</td><td>97</td><td>~</td><td>~</td></tr><tr><td>Rong et al. (2017b)</td><td>Traditional segmentation algorithm</td><td>Detection of surface defect on oranges using fast adaptive lightness correction algorithm.</td><td>95.7</td><td>~</td><td>30</td></tr><tr><td rowspan="3">Sun et al. (2020)</td><td rowspan="3">Semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3">~</td><td rowspan="3">70.38</td><td rowspan="3">~</td></tr><tr><td>using FA-Net Input: 288 × 288</td></tr><tr><td>Number of pixel classification categories: 5</td></tr><tr><td rowspan="3">Liang et al. (2022)</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on apples using</td><td rowspan="3"></td><td rowspan="3">80.46</td><td rowspan="3">16.99(RTX3060)*</td></tr><tr><td>BiSeNetV2 with pruned YOLOv4 assisted.</td></tr><tr><td>Input: 416 × 416 Number of pixel classification categories: 3</td></tr><tr><td rowspan="3">Current work</td><td rowspan="3">Real-time semantic segmentation</td><td>Detection of surface defect on navel oranges</td><td rowspan="3"></td><td rowspan="3">89.33</td><td rowspan="3">9.26(RTX3060)</td></tr><tr><td>using FastSegFormer-P.</td></tr><tr><td>Input: 224× 224 Number of pixel classification categories: 4</td></tr></table>
[表格脚注]
  \~:Not applicable or not mentioned in the original paper. \*:Results of testing on our equipment according to the original details. 
```

---

## 3. ContextWindow — 滑动窗口上下文扩充

- **锚点 Chunk**: `chunk-759dacbc-8108-4684-8881-6add0ca29285`
- **所属 Section**: `section-6fb76703-aba0-4b5d-a3db-6b2921a76831`
- **Section 内 Chunk 总数**: 12
- **锚点在 Section 中的位置**: 第 7 个 (未排序)

### 3.1 BOTH 方向 (window_size=3)

- **返回数量**: 4
- **耗时**: 40.0ms

#### Chunk #1 — `chunk-76dd468c-e85f-49b3-9536-9285c27598ef`

- **score**: 0.750
- **chunk_type**: text
- **page_index (首 Element)**: 0
- **element_index (首 Element)**: 10
- **备注**: 相邻 Chunk

**Chunk 完整文本**

```
Grading fruits and vegetables by size,weight,shape,color,and maturity is essential for quality sorting,differentiating product grades, setting prices,and adding value for consumers (Allwood et al., 2021). Efficient fruit quality assessment and sorting ensure consumer satisfaction,reduce food waste,and streamline marketing for these fresh, tasty products.Navel oranges,identifiable by their distinct navel,are sweet, juicy,and rich in fiber and vitamin C (Hou et al., 2O2O; Xiang et al., 2020).Production of navel oranges includes sorting,which is moving from conventional machine learning to deep learning.Fruit sorting has gone from being mechanically operated to being automated thanks to the creation and marketing of the traditional vision system (Tripathi and Maktedar, 2O2O).With heightened fruit quality standards, better living conditions,and increased expectations,modern visual sorting systems are now honed for precise sorting.
```

#### Chunk #2 — `chunk-3fa506ec-9b6b-48fa-8405-59f335159d70`

- **score**: 0.750
- **chunk_type**: text
- **page_index (首 Element)**: 0
- **element_index (首 Element)**: 11
- **备注**: 相邻 Chunk

**Chunk 完整文本**

```
，wind scarring,and oil cell damage, each with unique and complex traits. Initially,separating defective from healthy fruit relied on combining classic image segmentation with traditional machine learning techniques. The morphology and appearance aspects of fruits are used to manually create feature extraction techniques,which are subsequently used to distinguish fruits using conventional classification algorithms (Rong et al., 2Ol7a). This kind of feature extraction approach necessitates in-depth prior knowledge, has low generalization and extraction accuracy,and frequently manifests as missed detection.However,deep learning,especially convolutional neural networks (CNNs),has overcome these drawbacks,providing substantially higher accuracy than traditional machine learning approaches.
```

#### Chunk #3 — `chunk-e85fef9e-e924-4f74-ad31-965dfb2ac4c5`

- **score**: 0.500
- **chunk_type**: image
- **image_file**: `df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`
- **page_index (首 Element)**: 1
- **element_index (首 Element)**: 0
- **备注**: 相邻 Chunk

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

#### Chunk #4 — `chunk-437c6137-40b1-4839-a942-9449a0134f5f`

- **score**: 0.250
- **chunk_type**: text
- **page_index (首 Element)**: 1
- **element_index (首 Element)**: 1
- **备注**: 相邻 Chunk

**Chunk 完整文本**

```
With the continuous advancement in computer computational capabilities,deep learning has emerged as the prevailing approach for fruit defect detection.Currently,systems for detecting fruit defects mostly use image classification methods based on deep learning.Azizah et al.(2Ol7) utilized a digital camera to take pictures of mangosteens and used a simple convolutional neural network (CNN) to identify defective fruits. De Luna et al. (2O19) classified tomato defects using the traditional networks VGG16,InceptionV3,and ResNet50,with the VGGl6 model achieving the maximum classification accuracy of $9 8 . 7 5 \%$ .With an accuracy of $9 8 . 5 \%$ ,Nithya et al. (2022) developed a deep learning vision system to identify mango defects.The empirical findings demonstrated that deep learning-based vision systems exhibit significantly superior accuracy compared to conventional machine vision methods.However,the image classification technology is unable to distinguish between different kinds of
```

### 3.2 PREV 方向 (window_size=2)

- **返回数量**: 1
- **耗时**: 37.2ms

#### Chunk #1 — `chunk-76dd468c-e85f-49b3-9536-9285c27598ef`

- **score**: 0.667
- **chunk_type**: text
- **page_index (首 Element)**: 0
- **element_index (首 Element)**: 10
- **备注**: 相邻 Chunk

**Chunk 完整文本**

```
Grading fruits and vegetables by size,weight,shape,color,and maturity is essential for quality sorting,differentiating product grades, setting prices,and adding value for consumers (Allwood et al., 2021). Efficient fruit quality assessment and sorting ensure consumer satisfaction,reduce food waste,and streamline marketing for these fresh, tasty products.Navel oranges,identifiable by their distinct navel,are sweet, juicy,and rich in fiber and vitamin C (Hou et al., 2O2O; Xiang et al., 2020).Production of navel oranges includes sorting,which is moving from conventional machine learning to deep learning.Fruit sorting has gone from being mechanically operated to being automated thanks to the creation and marketing of the traditional vision system (Tripathi and Maktedar, 2O2O).With heightened fruit quality standards, better living conditions,and increased expectations,modern visual sorting systems are now honed for precise sorting.
```

### 3.3 NEXT 方向 (window_size=2)

- **返回数量**: 2
- **耗时**: 38.8ms

#### Chunk #1 — `chunk-3fa506ec-9b6b-48fa-8405-59f335159d70`

- **score**: 0.667
- **chunk_type**: text
- **page_index (首 Element)**: 0
- **element_index (首 Element)**: 11
- **备注**: 相邻 Chunk

**Chunk 完整文本**

```
，wind scarring,and oil cell damage, each with unique and complex traits. Initially,separating defective from healthy fruit relied on combining classic image segmentation with traditional machine learning techniques. The morphology and appearance aspects of fruits are used to manually create feature extraction techniques,which are subsequently used to distinguish fruits using conventional classification algorithms (Rong et al., 2Ol7a). This kind of feature extraction approach necessitates in-depth prior knowledge, has low generalization and extraction accuracy,and frequently manifests as missed detection.However,deep learning,especially convolutional neural networks (CNNs),has overcome these drawbacks,providing substantially higher accuracy than traditional machine learning approaches.
```

#### Chunk #2 — `chunk-e85fef9e-e924-4f74-ad31-965dfb2ac4c5`

- **score**: 0.333
- **chunk_type**: image
- **image_file**: `df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`
- **image_path**: `default/users/caixj-test/sessions/session_20260227093838_5b3d729b/parsed/file-c57649a6-7eac-49bc-b285-991ef1af14c6/images/df2d7931e3d11e94337abf5cec4a9a8c23443c1e47965a4e7af624ede8e1a191.jpg`
- **page_index (首 Element)**: 1
- **element_index (首 Element)**: 0
- **备注**: 相邻 Chunk

**Chunk 内容（图片）**

```
[图片类型 Chunk] 文本内容为空，图片存储在对象存储中
```

---

## 4. RollUp — 跨粒度上溯

### 4.1 Element → Chunk（锚点: `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`）

- **返回数量**: 2
- **耗时**: 7.5ms

#### Chunk #1 — `chunk-03e812b7-f087-478f-903c-642002f8c97c`

- **score**: 1.000
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 5$ ,as indicated by the green broken line.In conclusion,after careful evaluation,we have selected $\lambda _ { 1 } = 0 . 5$ and $\lambda _ { 2 } = 5$ as the definitive weights for our model.
```

#### Chunk #2 — `chunk-8a302e8b-9a24-41b4-a71c-bd4d00e10734`

- **score**: 1.000
- **section_id**: `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`
- **chunk_type**: text

**Chunk 完整文本**

```
demonstrate that overly high NFD distillation losses substantially diminish accuracy,whereas the impact of excessive logits distillation losses appears to be less detrimental. This discrepancy arises because a distillation loss that is too large for intermediate feature maps can rapidly deteriorate the representational information derived from the pre-training weights.On the other hand,logits positioned at the output of the model have a relatively lesser impact in this regard.For the FastSegFormer-E model,when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5 .$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at $\lambda _ { 1 } = 0 . 7 5$ ,as indicated by the red broken line.For the FastSegFormer-P model, when holding the $\lambda _ { 2 }$ value constant, the optimal average is attained at $\lambda _ { 2 } = 5$ ,and conversely,with a fixed $\lambda _ { 1 }$ value,the peak average is observed at
```

### 4.2 Element → Section（锚点: `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`）

- **返回数量**: 1
- **耗时**: 8.4ms

#### Section #1 — `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`

- **document_id**: `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`
- **text_level**: 1

**Section 标题/内容**

```
3.1．Ablation studies 
```

### 4.3 Element → Document（锚点: `element-673e6940-b53a-4726-b1a7-b3af90e6f7ca`）

- **返回数量**: 1
- **耗时**: 3.7ms

#### Document — `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`

- **title**: (无)

**文档摘要**

```
(无摘要)
```

### 4.4 Chunk → Section（锚点: `chunk-03e812b7-f087-478f-903c-642002f8c97c`）

- **返回数量**: 1
- **耗时**: 7.2ms

#### Section #1 — `section-c6a71a9a-a631-45fc-81e2-3ac1c2fcaf64`

- **document_id**: `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`
- **text_level**: 1

**Section 标题/内容**

```
3.1．Ablation studies 
```

### 4.5 Chunk → Document（锚点: `chunk-03e812b7-f087-478f-903c-642002f8c97c`）

- **返回数量**: 1
- **耗时**: 3.5ms

#### Document — `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`

- **title**: (无)

**文档摘要**

```
(无摘要)
```

### 4.6 Section → Document（锚点: `section-0d1df367-e998-4cf3-b27b-103b4e8ecb6e`）

- **返回数量**: 1
- **耗时**: 3.7ms

#### Document — `document-a3e95586-5b03-447b-81a7-d1e12ff7cc6d`

- **title**: (无)

**文档摘要**

```
(无摘要)
```


> **跳过**: Link → Chunk（图谱相关，不在本次测试范围）

---

## 5. 一致性验证 — DrillDown ↔ RollUp 双向校验

DrillDown: Document → 34 个 Section

所有 Section 上溯均回到原始 Document (验证了 5 个)

---

