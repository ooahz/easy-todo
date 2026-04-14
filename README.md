# Easy Todo

现代化本地待办管理应用

![](https://s.ahzoo.cn/img/open/todo/todo.png)
## 功能特性

- 任务管理：新建、编辑、删除、标记完成
- 优先级设置：高 / 中 / 低
- 颜色标签：自定义任务颜色
- 自动延期：过期未完成任务自动延期到第二天
- 日期筛选：全部任务 / 今日任务 / 重要任务 / 已完成
- 浮窗模式：置顶显示当前页面任务列表，支持拖动和调整大小
- 主题切换：浅色 / 深色 / 跟随系统
- 数据导入导出：JSON 格式备份与恢复
- 开机自启：支持 Windows 开机自动启动

## 技术栈

- Python 3.9+
- PySide6
- QFluentWidgets
- SQLAlchemy

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包

目录模式（启动快）：

```bash
build.bat
```

单文件模式（方便分发）：

```bash
build_single.bat
```

## 项目结构

```
├── main.py              # 入口
├── config/              # 配置与常量
├── models/              # 数据模型
├── services/            # 业务逻辑
├── views/               # UI 视图
├── qss/                 # 主题样式表
├── assets/              # 图标资源
├── build.bat            # 打包脚本（目录模式）
├── build_single.bat     # 打包脚本（单文件模式）
└── LICENSE              # MIT License
```

## 许可证

[MIT License](LICENSE) © 2026 Ahzoo(十玖八柒), ahzoo.cn
