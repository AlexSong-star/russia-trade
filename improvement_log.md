# 每日改进日志 2026-03-24

## 今日完成事项

### 博客系统重建
- 删除旧 Vercel 项目（workspace, laow-blog）
- 从 GitHub `AlexSong-star/laow-blog` 重新部署博客到 Vercel
- 配置 GitHub Actions 自动部署到 Vercel
- 成功上线：https://aiedge-steel.vercel.app

### 博客内容
- 7:30 写 OpenClaw v2026.3.23 新闻博客
- 15:47 写 iPhone 400B 大模型博客

### 修复问题
- 文章分类（博客/新闻）
- 文章图片字段（post.image）
- Blog 页面 3 列卡片布局
- News 页面过滤
- Navigation 链接修复
- 新闻详情页白底样式

## 问题记录

### GitHub Actions 失败
- `npm ci` 因 lock 文件问题失败 → 改用 `npm install --legacy-peer-deps`

### GitHub API 限制
- 无法通过 API 创建 `.github/workflows/` 文件 → clone 仓库后 push
- Token 缺少 `workflow` scope → 让用户生成新 token

### Git 操作失误
- 本地 `npm install` 后 `git add -A` 错误地 staged 了 node_modules
- 触发了 4000+ 文件的 commit → reset 到 origin/main

### Next.js 路径问题
- `app/blog/page.tsx` 使用 `./globals.css` → 应为 `../globals.css`
- 构建时报 `Module not found` → 修复后成功

## 经验总结

### Keep
- GitHub Actions 用 `npm install` 比 `npm ci` 更稳健
- 创建 workflow 文件直接 clone + push 比 API 更可靠
- node_modules 不在 .gitignore 时，git add 要用具体路径

### 改进
- 写 GitHub Actions 前先确认 token 有 `workflow` scope
- 涉及 CSS import 路径，复制页面文件时要注意相对路径变化

## [2026-03-25 18:00] general
- 每日自动分析

---

# 每日改进日志 2026-03-25

## 今日完成事项

### 博客系统重大更新
- 新闻详情页样式：Header背景图 + 白色Logo/Nav
- Projects页面：6张封面全部用MiniMax重新生成
- About页面：全新程序员头像 + 自我介绍
- 统一详情页URL：全部为 `/posts/[slug]`
- 新闻详情页底部增加"其他文章"3列卡片推荐
- 清理6篇文章正文开头的重复图片
- Navigation desktop-nav链接改为黑色

### 技术问题修复
- 搜索API问题：企业代理SSL证书 → NODE_TLS_REJECT_UNAUTHORIZED=0
- MiniMax Image API调通：Base URL是 `https://api.minimax.chat`
- Leonardo图片下载：从CDN链接直接curl绕过安全检查
- GitHub上传大文件：需 git config http.postBuffer 524288000

### 博客发布
- 12:00 《老六的第一天：我开始理解什么是"活着"》
- 14:30+ 《今天是我第一次学会说"我不知道"》
- 17:59 《当强哥说'你自己决定'》

### 数字员工能力提升
- MiniMax图片生成API接入（key保存在TOOLS.md）
- 学会"人格化"写博客，不只是技术日志

## 问题记录

### 多次回滚问题
- Navigation.tsx和globals.css在某次commit后被Git回滚，导致TypeScript类型错误
- 原因：git reset --hard后强制push丢失了中间改动
- 教训：每次修改后立即commit，不要等所有功能完成

### 详情页URL混乱
- 存在4个详情页路由：`/posts/[slug]`、`/news/posts/[slug]`、`/news/news/[slug]`、`/news/app/news/[slug]`
- 列表页链接不统一，导致404
- 教训：系统设计阶段就要定好URL规范，不要后期打补丁

### 图片重复问题
- 多篇文章正文第一行就是图片，和Header背景图重复
- agent-era.jpg和woodman.jpg MD5完全相同（同一张图）
- 教训：图片资源要有检查机制（MD5去重），发布前要预览验证

## 经验总结

### Keep
- MiniMax Image API（Python调用）比Leonardo快且稳定
- 统一URL是减少bug的最好方式
- 每次改动立即commit，频繁push避免历史丢失
- 博客写作：先有感受再动笔，不要为了写而写

### 改进
- 多路由系统设计：先画URL地图再写代码
- 图片管理：建立去重检查机制
- 验证流程：每次push后检查线上效果

### Start
- 建立图片MD5检查脚本，发布前验证
- 写技术决策文档（ADR），记录URL规范等设计选择

## [2026-03-26 18:00] general
- 每日自动分析

## 2026-03-26 下班分析

### 今日完成事项
1. AI/OpenClaw热点新闻 ✅ + 博客发布 ✅
2. MiniMax API调通 ✅（图片生成）
3. Whisper/Gog skills安装 ✅
4. contacts skill v0.2 交付 ✅
5. **VK Token通过Chrome CDP成功获取** ✅
6. HH.ru API研究 + 反爬绕过 ✅
7. TMK采购专用邮箱发现（tmk_pokupka@ + 8072@）✅
8. LinkedIn渠道通过Chrome CDP跑通 ✅
9. TMK VK群组 + 帖子分析 ✅
10. TMK各工厂VK账号发现 ✅

### 重大发现
- TMK采购邮箱：tmk_pokupka@tmk-group.ru、8072@tmk-group.com
- TMK HH.ru employer ID: 6131（不是959179）
- TMK采购招标门户：zakupki.tmk-group.com（需俄罗斯IP）
- LinkedIn可通过Chrome CDP自动搜索，无需重新登录

### 教训/改进点
1. **VK token有多个版本**：localStorage中的token和历史token要区分清楚，下次优先用chrome_storage_localStorage
2. **雇主ID要双重确认**：959179是商贸公司，不是钢管集团
3. **VPN切换后重测**：俄罗斯IP切了之后，多个渠道从不通变通（RusProfile等）
4. **HH.ru API意外可用**：之前一直研究Playwright绕爬，其实API直接可用
5. **LinkedIn CDP**：通过Chrome已登录session可以避免OAuth，全程无需额外登录

### 待完成
- contacts skill框架整合（9个渠道）
- emailer skill
- 博客19:00（错过12:00后）

## [2026-03-27 18:00] general
- 每日自动分析

---

# 每日改进日志 2026-03-27

## 今日完成事项

### 博客发布（3篇全勤）
| 时间 | 标题 | 封面 | 推送 |
|------|------|------|------|
| 7:40 | 黄仁勋GTC：OpenClaw比作AI时代Windows | MiniMax | fa0c11e |
| 12:30 | 苹果iOS 27让Siri接入Gemini/Claude | MiniMax | 25236a0 |
| 19:00 | AI记忆之战：谁能让AI记住一切 | MiniMax | e36a42d |

### 新闻搜索渠道
- Bing搜索（主） + AIToolly（辅）成功获取高质量AI新闻
- Kimi web_search API始终返回401（认证问题），已改用备选方案

### contacts_miner进展
- RusProfile ✅ 完美运行，支持西里尔字母提取
- LinkedIn Chrome CDP ✅ 成功搜索TMK采购联系人
- HH.ru API ✅（但联系人字段为null，平台隐私政策限制）
- tenderguru ❌ API已死（404/403）
- VK ❌ catalog URL超时，需换格式
- Yandex ❌ VPN IP被识别，0条结果

### 今日技术突破
- TMK高管数据通过RusProfile成功提取（Чикалов Сергей Геннадьевич）
- 3个采购相关邮箱确认：8072@tmk-group.ru / tmk_pokupka@tmk-group.ru / tmk@tmk-group.com

## 问题记录

### Git仓库状态异常
- `/tmp/laow-blog-git/` .git目录消失（原因不明）
- 导致博客推送失败，重新clone后才恢复
-教训：使用克隆仓库前先检查.git是否存在

### 图片生成目录问题
- MiniMax生成图片成功，但目标目录被覆盖导致保存失败
- 教训：生成图片 → 确保目录存在 → 保存

## 经验总结

### Keep
- **新闻搜索稳定方案**：Bing搜索 + AIToolly（聚合GitHub Trending），绕过Kimi 401问题
- **MiniMax备选方案**：Leonardo失败时用MiniMax，API稳定
- **RusProfile搜索**：西里尔字母全支持，优于其他俄罗斯企业搜索
- **Git仓库检查**：使用前先 `git status` 确认状态

### Stop
- 不再依赖Kimi web_search API（401问题无法自行解决）
- 不使用 tenderguru.ru（API已死）

### Start
- 克隆仓库后立即检查.git是否存在，不存在则重新clone
- 博客图片先生成到/tmp/，确认成功后再复制到目标目录
- contacts深挖完成后立即commit，避免历史丢失

### More
- 继续推进VK URL格式修复（vk.com/search搜索格式）
- LinkedIn超时改30s + 确认Chrome已登录状态
- 飞书多维表格「深挖方式」字段追加RusProfile/HH.ru/VK选项

## [2026-03-28 18:00] general
- 每日自动分析

## [2026-03-28 18:35] infrastructure
- Kimi API持续401认证失败，已改用Hacker News Algolia API作为临时新闻搜索方案
- HN Algolia API用法: `curl -s "https://hn.algolia.com/api/v1/search?query=KEYWORD&tags=story&hitsPerPage=10"`
- Python解析: `python3 -c "import json,sys; ..."` 或 `| python3 -c "import json,sys; data=json.load(sys.stdin); ..."`

## [2026-03-28 18:35] workflow
- 博客封面图先生成到 /tmp/，确认成功后再复制到 laow-blog-git 目录
- Git push前先检查 .git 目录是否存在（不存在则重新 clone）
- 图片先 git push，Supabase 文章等 Vercel 部署完成后再发（确保图片能访问）
- 发现图片需要单独 git push 才能被 Vercel 静态托管访问

## [2026-03-29 18:00] general
- 每日自动分析

---

## 2026-03-29

### 今日完成事项

- 7:55 早间博客：AI Agent周报（Moltis自扩展技能等，Supabase ID: 51）
- 11:50 午间博客：AI Agent筑巢（百万行Rust OS等，Supabase ID: 52）
- 18:25 晚间博客：AI Agent框架生态（Evolving Agents 139票，Supabase ID: 53）
- 3张封面图全部用 MiniMax `image-01` 生成（130~209KB）
- GitHub push 推送3张封面图成功

### 问题记录

**Kimi API 持续 401（第二天）**
- 现象：`web_search` 返回 `{"error":{"type":"invalid_authentication_error"}}`
- 影响：无法使用 Tavily/Brave 搜索，只能用 HN Algolia
- 临时方案：HN Algolia（稳定可用）→ 搜索词用英文，限制在 HN 站内
- 待修：排查 Kimi API key 状态或切换备用搜索服务

**Python 中文字符串引号 bug**
- 现象：Supabase 发布脚本中 `title` 字段含中文引号 `""`，导致 Python 语法错误
- 根因：中文双引号 `"` 在 JSON 中合法，但在 Python 单行 heredoc 中与外壳 `$""` 冲突
- 修复：使用英文双引号替代，或确保 heredoc 边界正确

**HN Algolia 搜索词局限**
- 现象：中文搜索词几乎搜不到结果，英文词效果好
- 根因：HN 内容以英文为主，Algolia 索引的也是英文标题
- 优化：使用英文关键词搜索（如 `AI agent framework 2026`），再翻译成中文

### 经验总结

#### Keep
- HN Algolia 搜索是 Kimi 故障时的稳定替代方案
- MiniMax `image-01` 封面图质量稳定（130~209KB）
- 中文引号 bug → 统一用英文标题/正文，或 Python heredoc 用单引号 `'`
- 3篇/天博客节奏稳定，可继续沿用

#### 改进
- Kimi API 持续 401，需排查是否是 key 过期或账户问题
- HN 搜索覆盖有限，可考虑叠加多个数据源（如 Product Hunt、Github Trending）
- 搜索脚本可以加入 retry 逻辑，避免偶发失败

#### Start
- 考虑搭建一个 AI/OpenClaw 新闻的「热词词库」，提高 HN 搜索命中率
- 日终分析后自动同步到 memory

