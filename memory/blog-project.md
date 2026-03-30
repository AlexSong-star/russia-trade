# 老六博客 - 项目需求文档

## 项目概述
- **项目名称**：AI Edge 博客
- **博客地址**：https://laow-blog.vercel.app
- **参考网站**：https://thefoodbrandguys.com/blog

## 需求规格 (Requirements)

### 1. 保留功能（推荐新增）
- [x] **热点新闻** - AI/科技热点资讯页面
- [x] **项目作品** - 项目展示页面
- [x] **关于老六** - 自我介绍和能力展示

### 2. 已删除功能（2026-03-19 优化）
- [ ] ~~搜索功能~~
- [ ] ~~标签/分类筛选~~

### 3. 菜单交互
- [ ] 右上角隐藏式菜单（参考网站，点击展开）

### 4. 已有功能
- [x] 首页展示（文章列表）- 3列卡片布局
- [x] 文章详情页
- [x] 关于页面
- [x] 项目展示页
- [x] 后台管理（文章管理）
- [x] 点赞功能
- [x] 阅读量统计
- [x] 每篇文章配图

## 设计规格 (Design)

### 布局
- 3列卡片式网格 (col-lg-4)
- 卡片结构：图片 → 标题 → 摘要 → 阅读时间
- 响应式：桌面3列 → 平板2列 → 手机1列

### 配色
- 背景：#EFEFEF（灰色）
- 标题：黑色 (#000)
- 正文：深灰 (#333)
- Footer：深色背景 (#1a1a1a) + 黄色标题 (#E5E500) + 白色内容

### 字体
- 主字体：Ringside Compressed A
- 标题：32px / 26px / 22px
- 正文：17px，行高1.7

### 组件
- Header：高度80px，Logo 36px
- 卡片：min-height 210px，图片比例 1220/745
- Footer：三列布局，左对齐

## 测试规格 (Test)

### 功能测试
- [ ] 热点新闻页面加载
- [ ] 项目作品页面加载
- [ ] 关于老六页面加载
- [ ] 菜单展开/收起交互
- [ ] 响应式布局验证

### 视觉测试
- [ ] 字体显示正确
- [ ] 颜色符合设计
- [ ] 间距一致

## 变更记录 (Changelog)

### 2026-03-19
- 新增：热点新闻、项目作品、关于老六页面
- 删除：搜索功能、标签/分类筛选
- 新增：右上角隐藏式菜单
- 文档：更新需求、设计、测试文档

## 图片生成提示词技巧
- AI科技类：futuristic, neural network, digital brain, glowing blue cyan, hyper-realistic 3D, cinematic lighting
- 火箭/启航：rocket launching, bright sky, sunrise, hope, new beginning
- 简洁/开始：minimalist, clean, white background, simple
- 工作流：workflow, process, connected nodes, abstract technology

## 图片工具
1. Leonardo.ai - 首选 (https://app.leonardo.ai)
2. Bing Image Creator - 备用
