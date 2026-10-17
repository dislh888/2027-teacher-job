# 合肥·上海 2027届数学教师招聘导航（每日自动发现）

适用个人背景：数学师范本科、计算数学硕士、2027届、教师资格证仅通过笔试。原有 33 条人工整理的招聘岗位保留不动；搜索产生的新链接**只标记“待核实”**，不是已确认符合条件的岗位。

## 5 分钟上线（GitHub Pages）

1. 已经创建公开仓库 `dislh888/2027-teacher-job`（主分支 `main`）。
2. 将这个文件夹内的 **`.github/`、`data/`、`scripts/`、`site/` 和 `README.md`** 一起上传到仓库**根目录**（重要：不要只上传 `site/index.html`，也不要在根目录外多包一层文件夹）。`.github` 是隐藏目录，上传时注意保留。
3. 打开 GitHub 仓库：**Settings → Pages → Build and deployment → Source → GitHub Actions**。
4. 打开 **Actions → 每日招聘检索与网站发布 → Run workflow**，选 main 后运行一次。
5. 完成后在 **Settings → Pages** 查看网页网址，形如 `https://你的用户名.github.io/2027-teacher-job/`。
6. 确认仓库 **Settings → Actions → General → Workflow permissions** 允许写入（Read and write permissions），否则自动提交数据可能失败。GitHub Pages 发布还需允许 Actions 权限。

## 定时规则和更新含义

- `daily.yml` 在北京时间每天**12:20**计划执行（UTC 04:20），GitHub 的 schedule 有时会**延迟或跳过**。可在 Actions 中查看运行日志，必要时手动 Run workflow。
- 每次通过 Bing 搜索 RSS 和 Google News RSS 检查关于上海/合肥的 2027 数学教师招聘线索（不是互联网所有网站的保证覆盖）。查到的新职位线索自动去重后加入“新发现·待核实”分区，不进入 A/B“资格匹配”专区。
- 原始33条于 **2026-10-17** 核验/整理。新 RSS 线索来自自动发现，不代表已核实招聘公告内容、学校属性、学历门槛、教资要求、编制、报名截止或投递入口。
- 页面显示最近任务运行时间、RSS 成功/失败的源数及新增数量；RSS 全部失败时会警告（并保留旧数据）。
- 已明确截止的岗位默认隐藏，可勾选显示；没有明确截止日期的旧岗位**不能因此判断仍在招聘**。
- 收藏与已投递进度在本地浏览器 localStorage，换设备/浏览器不会自动同步。页面开启后点击“↻ 检查新信息”会拉取最新数据。

## 项目结构

```
.github/workflows/daily.yml  # GitHub Actions 定时搜集并发布
scripts/update_jobs.py        # 搜集/筛选/去重 Python 脚本（标准库，不需要密钥）
data/jobs_curated.json        # 原有33条人工整理的招聘岗位（永久分离）
data/candidates.json          # 机器搜索新线索（自动增量）
site/index.html               # 招聘导航网页
site/data/latest.json         # 网页实时拉取的数据（每日重建）
```

## 本地测试与手动运行

```bash
python3 scripts/update_jobs.py
python3 -m http.server 8000 --directory site
```

浏览器访问 `http://localhost:8000`。脚本使用公开 RSS，无需第三方 API 密钥，但相关站点可能限制抓取，导致无结果。建议以后持续增加权威招聘入口、学校官网 RSS/公告渠道，并对新发现岗位做人工审核后再升级到 A/B/C。

## 注意事项

- RSS 搜索结果可能误报、重复，第三方网站可能过期；**不保证每天都有新岗位**，也不保证覆盖所有相关公告。
- 代码**不能自动决定你是否符合招聘资格**，尤其是教资面试/合格证明与“仅通过笔试”的差别。正式投递请以教育局/学校最新公告及联系答复为准。
- 不要向公开仓库提交个人身份证、简历、邮箱密码、API 密钥等敏感信息。
- 如果仓库被禁用或 GitHub Actions 的定时工作流被自动禁用，需重新启用，并检查 Actions 历史记录。