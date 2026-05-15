# DeepSeek Token Monitor

DeepSeek Token 余额与用量监控悬浮窗，支持登录、余额查询、用量统计、主题切换和快捷键唤起。

## 技术清单

- Python 3
- Tkinter / ttk：桌面窗口界面
- urllib / json / ssl：DeepSeek 接口请求
- threading：后台刷新数据
- keyboard：全局快捷键，未安装时不影响主功能
- PyInstaller：打包 Windows 可执行文件

## 运行方式

```bash
pip install keyboard
python deepseek_token_monitor.py
```

程序会在本地生成 `config.json` 保存登录配置。

## 打包流程

安装打包工具：

```bash
pip install pyinstaller keyboard
```

使用现有配置打包：

```bash
pyinstaller DeepSeekTokenMonitor.spec
```

或重新生成可移植打包配置：

```bash
pyinstaller --onefile --windowed --name DeepSeekTokenMonitor deepseek_token_monitor.py
```

打包完成后，可执行文件位于：

```text
dist/DeepSeekTokenMonitor.exe
```
