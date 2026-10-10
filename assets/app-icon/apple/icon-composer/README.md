# Icon Composer · 图标分层

[中文](#中文) · [English](#english)

## 中文

macOS 26 / iOS 26 起，推荐用 Xcode 自带的 Icon Composer 制作 `.icon` 文件，系统会统一加圆角和玻璃效果。

1. 打开 Icon Composer，新建图标。
2. 背景（Background）设为纯色 `#FFFFFF`。
3. 把 `layer-mark-black.svg` 拖进来作为前景层。它是 1024 × 1024 透明画布，标志已经居中、比例正确，不要再缩放。
4. 切到深色外观（Dark）：背景改为 `#000000`，前景填充改为 `#FFFFFF`（或换用 `layer-mark-white.svg`）。
5. 透明（Clear）和着色（Tinted）外观由系统根据前景层自动生成，检查一遍即可。
6. 存储为 `OpenInfinity.icon`，拖进 Xcode 工程，在 Target 的 App Icon 中选择它。
7. 先关掉阴影、高光、半透明等玻璃参数，确认图形没问题后再按需开启。

需要兼容 macOS 15 及更早版本时，另外使用 `../macos/` 里的 `.icns` 或 `AppIcon.appiconset`。

## English

From macOS 26 / iOS 26, build a `.icon` file in Xcode's Icon Composer; the system applies the shape and Liquid Glass.

1. Open Icon Composer and create a new icon.
2. Set the Background to a solid `#FFFFFF`.
3. Drop in `layer-mark-black.svg` as the foreground layer. It is a 1024 × 1024 transparent canvas with the mark already centred and sized — do not rescale it.
4. In the Dark appearance, set the background to `#000000` and the foreground fill to `#FFFFFF` (or use `layer-mark-white.svg`).
5. Clear and Tinted appearances are generated from the foreground; review them.
6. Save as `OpenInfinity.icon`, add it to the Xcode project and select it as the target's App Icon.
7. Keep shadows, specular highlights and translucency off until the artwork is approved.

For macOS 15 and earlier, also ship the `.icns` or `AppIcon.appiconset` from `../macos/`.
