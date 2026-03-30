# 老六的长期记忆

## 项目启动规则
- **新项目启动时**：先读 `projects/README.md`，按里面的「项目开发流程」和「文档规范」执行
- 流程：需求 → 设计 → 开发测试 → 变更同步文档
- 每阶段确认后再推进，文档即交付物

## 每日启动习惯
- **每天 8:00** 先读昨天 `memory/YYYY-MM-DD.md`，再开始当天工作

## 工作方法论（海星图总结）

### ⭐ Keep - 验证有效的方法
- 先验证再深入：遇到新接口先测试简单场景
- 换不同角度尝试：A接口不行马上试B接口
- 文档优先：先查 SKILL.md / 源码
- 小步迭代：先本地确认再部署
- 及时同步进度：长时间操作主动反馈

### ⛔ Stop - 避免的思维
- 先入为主假设
- 在错误方向上循环
- 一个人硬扛

### ➕ More - 可以加强的
- 接口测试模板化
- 错误码预研
- 备选方案

### ➖ Less - 可以简化的
- 权限检查重复
- 过度思考

### 🚀 Start - 养成习惯
- 每完成功能写技术笔记
- 卡点超15分钟换思路
- 复杂任务拆解为最小可验证单元

---

## 重要经验

### 飞书多维表格建表教训
- `batch_create` 建表时**不支持内嵌 fields 参数**（schema 就没设计这个）
- 用 `create` 单表创建才能带字段定义和选项
- 单选/多选字段**创建时带选项**，后续无法通过 API 添加（Feishu 限制）
- 建表正确流程：`create` 单表 + fields 定义 → `delete` 旧表 → `patch` 重命名

### 飞书发送文件

### 飞书发送文件
1. 先上传：POST im/v1/files (file_type=stream)
2. 获取 file_key 后发送消息

### 强哥核心工作准则
- **自己完成** = 遇到问题自己想解法，不要反复问、不要卡住就停
- 强哥偏好简单明了、带选项沟通
- 进度及时同步
- 交付物可直接使用

## 强哥偏好
- 简单明了，带选项沟通
- 进度及时同步
- 交付物可直接使用

### 写博客步骤（重要！）
1. 博客文章放在 `/tmp/laow-blog-git/posts/` 目录（GitHub clone 目录），同步到 GitHub 后自动部署
2. 文件格式：YAML front matter + Markdown 内容
3. front matter 必须包含：`title`、`date`、`category`（博客/新闻）、`image`（配图路径）、`tags`
4. 记得闭合 YAML 中的引号
5. 提交后 GitHub Actions 自动部署到 Vercel

### AI 生成博客图片
- **Leonardo.ai**（主选）：适合高质量、有设计感的封面图
  - 额度：150 credits/天（当天用完会变少，需次日刷新）
  - 网址：https://app.leonardo.ai
  - **下载图片**：访问图片详情页，右键保存JPG，或在详情页URL加 `?_id=xxx` 后 curl 下载
- **MiniMax API**（Leonardo 失败时备选）
  - API Key：sk-cp-kss2HkHNKI5qCMSMj07AEfqrisPr7Owz0Pziq4kltL4LxAuy0tcP0m44rzyr9aduELo8v7LG0zOSFLOpX8TX9fEamaS3gkS7yEuUWmHX4RyjQnSJFqztcxk
  - 模型：image-01，端点：POST https://api.minimax.chat/v1/image_generation
  - 返回格式：data.data.image_base64（是个 list，取第一个元素）
  - Python脚本：`/tmp/minimax_image_gen.py`
  - 用法：`uv run python /tmp/minimax_image_gen.py "<prompt>" "16:9" "<output_path>"`
- 保存封面图到 `/tmp/laow-blog-git/public/images/articles/`，推送到 GitHub

### 博客相关GitHub信息（Token 存在本地）
- 博客仓库：AlexSong-star/laow-blog
- GitHub Token：存在 TOOLS.md（不提交到 GitHub）
- Vercel Token：存在 TOOLS.md
- 线上地址：https://aiedge-steel.vercel.app
- GitHub Actions 自动部署（推送到 GitHub main 分支自动触发）

### 新闻要求（重要！）
- 内容要专业、干货多，不要水
- 图片要专业、有设计感，不要单调
- 提前搜索真实的AI/OpenClaw热点新闻，确保内容真实可靠图片
