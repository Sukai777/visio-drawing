# 四级 RF LNA：完整重绘案例

本案例对应仓库首页展示的参考图，包含输入匹配、四级晶体管、上下偏置网络、电流复用、R-L-C 反馈、LR 与 RC 支路。

## 文件

| 文件 | 内容 |
| --- | --- |
| [reference.png](reference.png) | 使用者提供的参考图片 |
| [source.json](source.json) | 从源图记录的 79 个元件、49 组网络、连接点与文字清单 |
| [model.json](model.json) | 区域局部坐标下的可复用绘图模型 |
| [build_model.py](build_model.py) | 生成上述模型的辅助脚本；运行会更新同目录 model.json |
| [output/RF_LNA.vsdx](output/RF_LNA.vsdx) | 可编辑的原生 Visio 图纸 |
| [output/RF_LNA.png](output/RF_LNA.png) | 重绘预览 |
| [output/RF_LNA.svg](output/RF_LNA.svg) | 矢量导出 |
| [output/RF_LNA.pdf](output/RF_LNA.pdf) | 单页 PDF |
| [output/RF_LNA.verification.json](output/RF_LNA.verification.json) | 保存文件的检查报告与哈希 |
| [output/visual-review.json](output/visual-review.json) | 三个区域的视觉复核记录 |
| [output/transform-tests.json](output/transform-tests.json) | 首轮绘制中代表性元件的移动、旋转和镜像测试结果 |

## 本次检查结果

- 元件清单及 49 组预期网络检查通过。
- 保存文件中的 324 个线段端点吸附记录检查通过，测得端点误差为 0。
- VSDX 不包含用来替代整幅图的嵌入位图。
- 首轮对 M₀₁、M₀₂、M₃、C₁、L₂ 和 TL₁₃ 做了移动、旋转、镜像及恢复测试。后续调整为文字位置、色块圆角和 VDD 端标记。
- 三个区域均进行了原图对照；保守文字边界与元件边界的少数重叠提示，经放大确认未造成实际笔画遮挡，处理原因记录在视觉复核文件中。

这些数值对应仓库中附带的图纸。重新生成后，Visio 文件哈希会变化，必须为新文件重新复核，不能复用已发布的视觉审核结论。

## 复现

在装有 Visio、PowerShell 7 和 Python/Pillow 的 Windows 环境中，从仓库根目录运行：

```powershell
pwsh -NoProfile -File ./examples/rf-lna/rebuild.ps1 -Python 'C:/实际路径/python.exe' -TestTransforms
```

默认写入仓库下 `.build/rf-lna`，保留本目录的已发布图纸。脚本先为本机重新记录源图证据锁，再使用仓库中的渲染器绘图。

生成后，请打开 `.build/rf-lna/RF_LNA.review` 中每个区域的 `*-compare.png`。按照 [视觉复核说明](../../references/visual-review.md) 完成新文件的审核，再运行：

```powershell
& 'C:/实际路径/python.exe' ./scripts/drawing.py finalize `
  --vsdx ./.build/rf-lna/RF_LNA.vsdx `
  --compiled ./.build/rf-lna/RF_LNA.compiled.json `
  --review ./.build/rf-lna/visual-review.json
```

如需修改 `source.json` 的判读结论，请先重新查看相应源图区，并记录修改原因。使用新的 `-OutputDirectory` 保存新的证据锁，保留旧版本。

## 判读要点

C₂/C₅/C₁₃ 是接地支路；M₃ 上方为源极；C₇—R₁₄—TL₁₃ 构成一条串联支路；R₉ 接入 TL₆ 下方。这些关系经过当前图片的放大核对，不能由相邻元件位置或背景色块直接推断。

原图的小跨线弧在重绘中采用无连接点的交叉线表达；两条线在电气网络中保持分离。原生线圈和接地符号的笔画风格与原图有少量差异。
